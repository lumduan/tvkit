"""
Unit and integration tests for tvkit.auth.

Unit tests mock all external HTTP calls.
Integration tests use real TradingView credentials from a .env file and are
skipped automatically when the environment variables are not set.

Environment variables (set in .env or shell):
    TRADINGVIEW_USERNAME  — TradingView account email / username
    TRADINGVIEW_PASSWORD  — TradingView account password
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.auth import (
    AuthenticationError,
    AuthError,
    AuthManager,
    CapabilityProbeError,
    ProfileFetchError,
    TradingViewAccount,
    TradingViewCredentials,
)
from tvkit.auth.capability_detector import CapabilityDetector
from tvkit.auth.profile_parser import ProfileParser
from tvkit.auth.token_provider import LoginResult, TokenProvider

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SAMPLE_PROFILE: dict[str, Any] = {
    "id": 65880006,
    "username": "testuser",
    "auth_token": "abcdefgh1234567890",
    "is_pro": True,
    "pro_plan": "pro_premium",
    "badges": [{"name": "pro:pro_premium", "verbose_name": "Premium"}],
    "is_broker": False,
}

_SAMPLE_HTML_STRATEGY1 = (
    '<html><body><script>window.data = {"user":{"id":65880006,"username":"testuser",'
    '"auth_token":"abcdefgh1234567890","is_pro":true,"pro_plan":"pro_premium",'
    '"badges":[{"name":"pro:pro_premium"}],"is_broker":false}}</script></body></html>'
)

# Strategy 2: auth_token only inside a <script> block, not at top level
_SAMPLE_HTML_STRATEGY2 = (
    "<html><body>"
    '<script src="external.js"></script>'
    "<script>var x=1;</script>"
    '<script>var bootstrap={"auth_token":"tok","user":{"id":1,"username":"u",'
    '"auth_token":"abcdefgh1234567890","is_pro":false,"pro_plan":"",'
    '"badges":[],"is_broker":false}}</script>'
    "</body></html>"
)

# Strategy 3: window.__TV_DATA__ bootstrap container
_SAMPLE_HTML_STRATEGY3_CONTAINER = (
    '<html><body><script>window.__TV_DATA__ = {"user":{"id":2,"username":"u2",'
    '"auth_token":"abcdefgh99999999","is_pro":true,"pro_plan":"ultimate",'
    '"badges":[],"is_broker":false}}</script></body></html>'
)

_SAMPLE_HTML_USER_NULL = (
    '<html><body><script>window.__TV_DATA__ = {"user":null}</script></body></html>'
)
_SAMPLE_HTML_USER_EMPTY = (
    '<html><body><script>window.__TV_DATA__ = {"user":{}}</script></body></html>'
)
_SAMPLE_HTML_USER_NO_ID = (
    '<html><script>var d={"user":{"username":"u","auth_token":"tok","is_pro":false,'
    '"pro_plan":"","badges":[],"is_broker":false}}</script></html>'
)
_SAMPLE_HTML_USER_NO_USERNAME = (
    '<html><script>var d={"user":{"id":1,"auth_token":"tok","is_pro":false,'
    '"pro_plan":"","badges":[],"is_broker":false}}</script></html>'
)
_SAMPLE_HTML_NO_USER = "<html><body><script>var x = 1;</script></body></html>"


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_mock_response(
    status: int,
    text: str = "",
    cookies: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    jar: dict[str, str] = cookies or {}
    resp.cookies = MagicMock()
    resp.cookies.get = lambda key, default=None: jar.get(key, default)
    return resp


def _make_mock_session(
    stage1_status: int = 200,
    homepage_html: str = _SAMPLE_HTML_STRATEGY1,
) -> MagicMock:
    """Build a mock curl-cffi AsyncSession for the Stage 1→2 flow (no CSRF)."""
    session = AsyncMock()
    stage1_resp = _make_mock_response(stage1_status)
    stage2_resp = _make_mock_response(200, text=homepage_html)

    # Stage 1 = POST, Stage 2 = GET /
    session.get = AsyncMock(return_value=stage2_resp)
    session.post = AsyncMock(return_value=stage1_resp)
    session.close = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# TradingViewCredentials
# ---------------------------------------------------------------------------


class TestTradingViewCredentials:
    def test_anonymous_mode(self) -> None:
        creds = TradingViewCredentials()
        assert creds.is_anonymous is True
        assert creds.uses_direct_token is False
        assert creds.uses_credentials is False

    def test_credentials_mode(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        assert creds.is_anonymous is False
        assert creds.uses_credentials is True
        assert creds.uses_direct_token is False

    def test_direct_token_mode(self) -> None:
        creds = TradingViewCredentials(auth_token="mytoken123")
        assert creds.is_anonymous is False
        assert creds.uses_direct_token is True
        assert creds.uses_credentials is False

    def test_both_creds_and_token_raises(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            TradingViewCredentials(username="alice", password="secret", auth_token="tok")

    def test_username_only_raises(self) -> None:
        with pytest.raises(ValueError, match="together"):
            TradingViewCredentials(username="alice")

    def test_password_only_raises(self) -> None:
        with pytest.raises(ValueError, match="together"):
            TradingViewCredentials(password="secret")

    def test_password_not_in_repr(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        assert "secret" not in repr(creds)

    def test_auth_token_not_in_repr(self) -> None:
        creds = TradingViewCredentials(auth_token="supersecret")
        assert "supersecret" not in repr(creds)


# ---------------------------------------------------------------------------
# ProfileParser
# ---------------------------------------------------------------------------


class TestProfileParser:
    def test_strategy1_extracts_user(self) -> None:
        profile = ProfileParser.parse(_SAMPLE_HTML_STRATEGY1)
        assert profile["id"] == 65880006
        assert profile["username"] == "testuser"
        assert profile["auth_token"] == "abcdefgh1234567890"

    def test_strategy2_fallback(self) -> None:
        profile = ProfileParser.parse(_SAMPLE_HTML_STRATEGY2)
        assert profile["id"] == 1
        assert profile["auth_token"] == "abcdefgh1234567890"

    def test_strategy3_bootstrap_container(self) -> None:
        profile = ProfileParser.parse(_SAMPLE_HTML_STRATEGY3_CONTAINER)
        assert profile["id"] == 2
        assert profile["pro_plan"] == "ultimate"

    def test_all_strategies_fail_raises(self) -> None:
        with pytest.raises(ProfileFetchError, match="all 3 parsing strategies failed"):
            ProfileParser.parse(_SAMPLE_HTML_NO_USER)

    def test_user_null_raises(self) -> None:
        with pytest.raises(ProfileFetchError, match="null or not a dict"):
            ProfileParser.parse(_SAMPLE_HTML_USER_NULL)

    def test_user_empty_dict_raises(self) -> None:
        with pytest.raises(ProfileFetchError, match="user.id is missing"):
            ProfileParser.parse(_SAMPLE_HTML_USER_EMPTY)

    def test_user_missing_id_raises(self) -> None:
        with pytest.raises(ProfileFetchError, match="user.id is missing"):
            ProfileParser.parse(_SAMPLE_HTML_USER_NO_ID)

    def test_user_missing_username_raises(self) -> None:
        with pytest.raises(ProfileFetchError, match="user.username is missing"):
            ProfileParser.parse(_SAMPLE_HTML_USER_NO_USERNAME)

    def test_escaped_strings_do_not_break_extraction(self) -> None:
        html = (
            '<html><script>var d={"user":{"id":3,"username":"has\\"quote",'
            '"auth_token":"abcdefgh12345678","is_pro":false,"pro_plan":"",'
            '"badges":[],"is_broker":false}}</script></html>'
        )
        profile = ProfileParser.parse(html)
        assert profile["id"] == 3

    def test_empty_script_blocks_skipped(self) -> None:
        html = (
            '<html><script src="a.js"></script>'
            '<script src="b.js"></script>'
            '<script>var d={"user":{"id":99,"username":"skip_test",'
            '"auth_token":"abcdefgh99999990","is_pro":false,"pro_plan":"",'
            '"badges":[],"is_broker":false}}</script></html>'
        )
        profile = ProfileParser.parse(html)
        assert profile["id"] == 99

    def test_balanced_brace_extract_basic(self) -> None:
        text = 'start {"key": "value", "nested": {"a": 1}} end'
        result = ProfileParser._balanced_brace_extract(text, 6)
        assert result == '{"key": "value", "nested": {"a": 1}}'

    def test_balanced_brace_extract_no_brace_raises(self) -> None:
        with pytest.raises(ValueError, match="No opening brace"):
            ProfileParser._balanced_brace_extract("no braces here", 0)


# ---------------------------------------------------------------------------
# CapabilityDetector
# ---------------------------------------------------------------------------


class TestCapabilityDetector:
    @pytest.mark.parametrize(
        "plan, expected_bars, expected_tier",
        [
            ("", 5_000, "free"),
            ("pro", 10_000, "pro"),
            ("pro_plus", 10_000, "pro"),
            ("pro_premium", 20_000, "premium"),
            ("ultimate", 40_000, "ultimate"),
        ],
    )
    def test_exact_plan_mapping(self, plan: str, expected_bars: int, expected_tier: str) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan(plan, [])
        assert bars == expected_bars
        assert tier == expected_tier

    def test_badge_fallback_string_form(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("", ["pro:pro_premium"])
        assert bars == 20_000
        assert tier == "premium"

    def test_badge_fallback_dict_form(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan(
            "", [{"name": "pro:pro_premium", "verbose_name": "Premium"}]
        )
        assert bars == 20_000
        assert tier == "premium"

    def test_badge_fallback_ultimate(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("", [{"name": "pro:ultimate"}])
        assert bars == 40_000
        assert tier == "ultimate"

    def test_no_badge_gives_free(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("", [])
        assert bars == 5_000
        assert tier == "free"

    def test_unknown_slug_with_pro_heuristic(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("pro_essential", [])
        assert bars == 10_000
        assert tier == "pro"

    def test_unknown_slug_with_premium_heuristic(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("new_premium_plan", [])
        assert bars == 20_000
        assert tier == "premium"

    def test_unknown_slug_with_ultimate_heuristic(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("super_ultimate_v2", [])
        assert bars == 40_000
        assert tier == "ultimate"

    def test_completely_unknown_slug_gives_free_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="tvkit.auth.capability_detector"):
            bars, tier = CapabilityDetector.estimate_from_plan("enterprise_tier", [])
        assert bars == 5_000
        assert tier == "free"
        assert "enterprise_tier" in caplog.text

    def test_mixed_case_plan_normalized(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("PRO_PREMIUM", [])
        assert bars == 20_000
        assert tier == "premium"

    def test_pro_plan_takes_precedence_over_badges(self) -> None:
        bars, tier = CapabilityDetector.estimate_from_plan("ultimate", [{"name": "pro:pro"}])
        assert bars == 40_000
        assert tier == "ultimate"


# ---------------------------------------------------------------------------
# TradingViewAccount
# ---------------------------------------------------------------------------


class TestTradingViewAccount:
    def test_from_profile_populates_all_fields(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 20_000, "premium")
        assert account.user_id == 65880006
        assert account.username == "testuser"
        assert account.plan == "pro_premium"
        assert account.tier == "premium"
        assert account.is_pro is True
        assert account.is_broker is False
        assert account.max_bars == 20_000
        assert account.estimated_max_bars == 20_000
        assert account.probe_confirmed is False

    def test_probe_confirmed_defaults_false(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 5_000, "free")
        assert account.probe_confirmed is False

    def test_max_bars_mutable_estimated_immutable(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 10_000, "pro")
        account.max_bars = 9_500  # simulates probe update
        assert account.max_bars == 9_500
        assert account.estimated_max_bars == 10_000  # unchanged


# ---------------------------------------------------------------------------
# TokenProvider (unit — mocked curl-cffi)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTokenProvider:
    async def test_login_success(self) -> None:
        mock_session = _make_mock_session()
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                result = await provider.login()
        assert result.auth_token == "abcdefgh1234567890"
        assert result.user_profile["username"] == "testuser"

    async def test_login_raises_if_session_none(self) -> None:
        provider = TokenProvider("user", "pass")
        with pytest.raises(RuntimeError, match="async context manager"):
            await provider.login()

    async def test_handle_401_raises_if_session_none(self) -> None:
        provider = TokenProvider("user", "pass")
        with pytest.raises(RuntimeError, match="async context manager"):
            await provider.handle_401()

    async def test_handle_403_raises_if_session_none(self) -> None:
        provider = TokenProvider("user", "pass")
        with pytest.raises(RuntimeError, match="async context manager"):
            await provider.handle_403()

    async def test_http_401_raises_authentication_error(self) -> None:
        mock_session = _make_mock_session(stage1_status=401)
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                with pytest.raises(AuthenticationError, match="401"):
                    await provider.login()

    async def test_http_403_raises_authentication_error(self) -> None:
        mock_session = _make_mock_session(stage1_status=403)
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                with pytest.raises(AuthenticationError, match="403"):
                    await provider.login()

    async def test_http_500_raises_authentication_error(self) -> None:
        mock_session = _make_mock_session(stage1_status=500)
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                with pytest.raises(AuthenticationError, match="500"):
                    await provider.login()

    async def test_timeout_retries_once_then_raises(self) -> None:
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=TimeoutError())
        mock_session.close = AsyncMock()

        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                async with TokenProvider("user", "pass") as provider:
                    with pytest.raises(AuthenticationError, match="timed out"):
                        await provider.login()

        # POST called twice: initial attempt + exactly one retry
        assert mock_session.post.call_count == 2

    async def test_handle_401_loop_prevention(self) -> None:
        mock_session = _make_mock_session()
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                provider._relogin_in_progress = True
                with pytest.raises(AuthenticationError, match="Re-login loop"):
                    await provider.handle_401()

    async def test_handle_401_resets_flag_on_success(self) -> None:
        """_relogin_in_progress must be False after a successful handle_401."""
        mock_session = _make_mock_session()

        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                result = await provider.handle_401()

        assert result.auth_token == "abcdefgh1234567890"
        assert provider._relogin_in_progress is False

    async def test_handle_401_resets_flag_on_failure(self) -> None:
        """_relogin_in_progress must be False even when handle_401 fails."""
        mock_session = _make_mock_session(stage1_status=401)

        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                with pytest.raises(AuthenticationError):
                    await provider.handle_401()
                assert provider._relogin_in_progress is False

    async def test_handle_403_calls_full_login(self) -> None:
        mock_session = _make_mock_session()
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                with patch.object(provider, "login", new_callable=AsyncMock) as mock_login:
                    mock_login.return_value = LoginResult(
                        auth_token="newtoken12", user_profile=_SAMPLE_PROFILE
                    )
                    result = await provider.handle_403()
        assert result.auth_token == "newtoken12"
        mock_login.assert_called_once()

    async def test_token_refresh_flow_returns_new_token(self) -> None:
        """Simulate: initial login → 401 → handle_401 → new token returned."""
        mock_session = AsyncMock()
        stage2a_resp = _make_mock_response(200, text=_SAMPLE_HTML_STRATEGY1)
        stage2b_resp = _make_mock_response(200, text=_SAMPLE_HTML_STRATEGY1)
        mock_session.get = AsyncMock(side_effect=[stage2a_resp, stage2b_resp])
        mock_session.post = AsyncMock(return_value=_make_mock_response(200))
        mock_session.close = AsyncMock()

        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass") as provider:
                first = await provider.login()
                second = await provider.handle_401()

        assert first.auth_token == "abcdefgh1234567890"
        assert second.auth_token == "abcdefgh1234567890"
        # GET called twice: stage2 (login) + stage2 (handle_401)
        assert mock_session.get.call_count == 2

    async def test_session_closed_on_aexit(self) -> None:
        mock_session = _make_mock_session()
        with patch("tvkit.auth.token_provider.AsyncSession", return_value=mock_session):
            async with TokenProvider("user", "pass"):
                pass
        mock_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# AuthManager (unit — mocked TokenProvider)
# ---------------------------------------------------------------------------


def _mock_provider(login_result: LoginResult) -> MagicMock:
    """Return a fully mocked TokenProvider instance."""
    inst = AsyncMock()
    inst.login = AsyncMock(return_value=login_result)
    inst.__aenter__ = AsyncMock(return_value=inst)
    inst.__aexit__ = AsyncMock(return_value=None)
    return inst


@pytest.mark.asyncio
class TestAuthManager:
    async def test_anonymous_mode(self) -> None:
        async with AuthManager() as auth:
            assert auth.auth_token == "unauthorized_user_token"
            assert auth.account is None
            assert auth.token_provider is None
            assert auth._probe_task is None

    async def test_direct_token_mode(self) -> None:
        creds = TradingViewCredentials(auth_token="directtoken123")
        async with AuthManager(creds) as auth:
            assert auth.auth_token == "directtoken123"
            assert auth.account is None
            assert auth.token_provider is None
            assert auth._probe_task is None

    async def test_credentials_mode_populates_account(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        mock_result = LoginResult(auth_token="realtoken99", user_profile=_SAMPLE_PROFILE)

        with patch("tvkit.auth.auth_manager.TokenProvider") as MockProvider:
            MockProvider.return_value = _mock_provider(mock_result)
            async with AuthManager(creds) as auth:
                assert auth.auth_token == "realtoken99"
                assert auth.account is not None
                assert auth.account.username == "testuser"
                assert auth.account.tier == "premium"
                assert auth.account.max_bars == 20_000
                assert auth.token_provider is not None
                assert auth._probe_task is not None

    async def test_anonymous_mode_no_probe_task(self) -> None:
        async with AuthManager() as auth:
            assert auth._probe_task is None

    async def test_direct_token_no_probe_task(self) -> None:
        creds = TradingViewCredentials(auth_token="tok")
        async with AuthManager(creds) as auth:
            assert auth._probe_task is None

    async def test_aexit_cancels_probe_task(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        mock_result = LoginResult(auth_token="tok", user_profile=_SAMPLE_PROFILE)

        with patch("tvkit.auth.auth_manager.TokenProvider") as MockProvider:
            MockProvider.return_value = _mock_provider(mock_result)
            async with AuthManager(creds) as auth:
                task = auth._probe_task
                assert task is not None
            # After __aexit__, task must be done (cancelled or completed)
            assert task.done()

    async def test_aexit_closes_token_provider(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        mock_result = LoginResult(auth_token="tok", user_profile=_SAMPLE_PROFILE)

        with patch("tvkit.auth.auth_manager.TokenProvider") as MockProvider:
            mock_inst = _mock_provider(mock_result)
            MockProvider.return_value = mock_inst
            async with AuthManager(creds):
                pass
            mock_inst.close.assert_called_once()

    async def test_aexit_closes_provider_on_exception(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        mock_result = LoginResult(auth_token="tok", user_profile=_SAMPLE_PROFILE)

        with patch("tvkit.auth.auth_manager.TokenProvider") as MockProvider:
            mock_inst = _mock_provider(mock_result)
            MockProvider.return_value = mock_inst
            with pytest.raises(RuntimeError, match="test error"):
                async with AuthManager(creds):
                    raise RuntimeError("test error")
            # Provider must still be closed when an exception propagates
            mock_inst.close.assert_called_once()

    async def test_default_credentials_is_anonymous(self) -> None:
        auth = AuthManager()
        assert auth._credentials.is_anonymous is True

    async def test_token_provider_property_available_after_aenter(self) -> None:
        creds = TradingViewCredentials(username="alice", password="secret")
        mock_result = LoginResult(auth_token="tok", user_profile=_SAMPLE_PROFILE)

        with patch("tvkit.auth.auth_manager.TokenProvider") as MockProvider:
            MockProvider.return_value = _mock_provider(mock_result)
            async with AuthManager(creds) as auth:
                assert auth.token_provider is not None


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    def test_authentication_error_is_auth_error(self) -> None:
        assert issubclass(AuthenticationError, AuthError)

    def test_profile_fetch_error_is_auth_error(self) -> None:
        assert issubclass(ProfileFetchError, AuthError)

    def test_capability_probe_error_is_auth_error(self) -> None:
        assert issubclass(CapabilityProbeError, AuthError)

    def test_catch_all_with_auth_error(self) -> None:
        for err in [AuthenticationError("a"), ProfileFetchError("b"), CapabilityProbeError("c")]:
            assert isinstance(err, AuthError)

    def test_authentication_error_is_exception(self) -> None:
        assert issubclass(AuthenticationError, Exception)


# ---------------------------------------------------------------------------
# Integration tests — real TradingView credentials from .env
# ---------------------------------------------------------------------------

_TV_USERNAME = os.getenv("TRADINGVIEW_USERNAME", "")
_TV_PASSWORD = os.getenv("TRADINGVIEW_PASSWORD", "")
_HAS_REAL_CREDENTIALS = bool(_TV_USERNAME and _TV_PASSWORD)

_SKIP_REASON = (
    "TRADINGVIEW_USERNAME and TRADINGVIEW_PASSWORD not set — "
    "set them in .env to run real-credential integration tests"
)


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_REAL_CREDENTIALS, reason=_SKIP_REASON)
class TestRealTradingViewLogin:
    """
    Integration tests that perform a real TradingView login.

    Skipped unless TRADINGVIEW_USERNAME and TRADINGVIEW_PASSWORD are available
    in the environment (e.g. loaded from .env via python-dotenv or direnv).
    """

    async def test_real_login_returns_auth_token(self) -> None:
        """Full Stage 1→2 login returns a non-empty auth_token."""
        try:
            async with TokenProvider(_TV_USERNAME, _TV_PASSWORD) as provider:
                result = await provider.login()
        except AuthenticationError as e:
            msg = str(e)
            if "robot" in msg.lower() or "captcha" in msg.lower():
                pytest.skip(f"TradingView CAPTCHA triggered (rate-limited): {msg}")
            raise

        assert result.auth_token, "auth_token must be non-empty"
        assert len(result.auth_token) > 8, "auth_token length must exceed 8 chars"
        assert result.user_profile.get("id"), "user.id must be present"
        assert result.user_profile.get("username"), "user.username must be present"

    async def test_real_auth_manager_credentials_mode(self) -> None:
        """AuthManager with real credentials returns a populated account and valid token."""
        creds = TradingViewCredentials(username=_TV_USERNAME, password=_TV_PASSWORD)
        try:
            async with AuthManager(creds) as auth:
                assert auth.auth_token, "auth_token must be non-empty"
                assert auth.account is not None, "account must be populated"
                assert auth.account.user_id > 0
                assert auth.account.username
                assert auth.account.tier in ("free", "pro", "premium", "ultimate")
                assert auth.account.max_bars > 0
                assert auth.token_provider is not None
        except AuthenticationError as e:
            msg = str(e)
            if "robot" in msg.lower() or "captcha" in msg.lower():
                pytest.skip(f"TradingView CAPTCHA triggered (rate-limited): {msg}")
            raise

    async def test_real_anonymous_token_unchanged(self) -> None:
        """Anonymous mode always returns 'unauthorized_user_token'."""
        async with AuthManager() as auth:
            assert auth.auth_token == "unauthorized_user_token"
            assert auth.account is None
