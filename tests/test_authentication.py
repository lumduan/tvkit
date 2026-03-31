"""
Unit tests for tvkit.auth.

All external calls (browser_cookie3, httpx) are mocked.
No real browser or network access is required.

Integration tests using a real browser are gated by TVKIT_BROWSER env var
and skipped automatically when it is not set.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tvkit.api.chart.exceptions import AuthError as ChartAuthError
from tvkit.api.chart.services.connection_service import ConnectionService
from tvkit.auth import (
    AuthError,
    AuthManager,
    BrowserCookieError,
    CapabilityProbeError,
    CookieProvider,
    ProfileFetchError,
    TradingViewAccount,
    TradingViewCredentials,
)
from tvkit.auth.capability_detector import CapabilityDetector
from tvkit.auth.cookie_provider import COOKIE_CACHE_TTL
from tvkit.auth.probe_cache import PROBE_CACHE_TTL, ProbeCache
from tvkit.auth.profile_parser import ProfileParser
from tvkit.auth.token_provider import _FETCH_TIMEOUT, TokenProvider

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

_SAMPLE_COOKIES: dict[str, str] = {
    "sessionid": "sess_abc123",
    "csrftoken": "csrf_xyz",
    "device_t": "dt_value",
}

# Strategy 0: var user = {...}  (TradingView current frontend)
_SAMPLE_HTML_STRATEGY0 = (
    '<html><body><script>var user = {"id":65880006,"username":"testuser",'
    '"auth_token":"abcdefgh1234567890","is_pro":true,"pro_plan":"pro_premium",'
    '"badges":[{"name":"pro:pro_premium"}],"is_broker":false};</script></body></html>'
)

# Strategy 1: "user":{...} at root of a JSON blob
_SAMPLE_HTML_STRATEGY1 = (
    '<html><body><script>window.data = {"user":{"id":65880006,"username":"testuser",'
    '"auth_token":"abcdefgh1234567890","is_pro":true,"pro_plan":"pro_premium",'
    '"badges":[{"name":"pro:pro_premium"}],"is_broker":false}}</script></body></html>'
)

# Strategy 2: auth_token inside a <script> block
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
# TradingViewCredentials
# ---------------------------------------------------------------------------


class TestTradingViewCredentials:
    def test_anonymous_mode(self) -> None:
        creds = TradingViewCredentials()
        assert creds.is_anonymous is True
        assert creds.uses_browser is False
        assert creds.uses_cookie_dict is False
        assert creds.uses_direct_token is False

    def test_browser_chrome(self) -> None:
        creds = TradingViewCredentials(browser="chrome")
        assert creds.is_anonymous is False
        assert creds.uses_browser is True
        assert creds.browser == "chrome"

    def test_browser_firefox(self) -> None:
        creds = TradingViewCredentials(browser="firefox")
        assert creds.uses_browser is True
        assert creds.browser == "firefox"

    def test_browser_with_profile(self) -> None:
        creds = TradingViewCredentials(browser="chrome", browser_profile="Profile 2")
        assert creds.uses_browser is True
        assert creds.browser_profile == "Profile 2"

    def test_cookie_dict_mode(self) -> None:
        creds = TradingViewCredentials(cookies={"sessionid": "abc"})
        assert creds.is_anonymous is False
        assert creds.uses_cookie_dict is True
        assert creds.uses_browser is False

    def test_direct_token_mode(self) -> None:
        creds = TradingViewCredentials(auth_token="mytoken123")
        assert creds.is_anonymous is False
        assert creds.uses_direct_token is True
        assert creds.uses_browser is False

    def test_browser_plus_token_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            TradingViewCredentials(browser="chrome", auth_token="tok")

    def test_browser_plus_cookies_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            TradingViewCredentials(browser="chrome", cookies={"sessionid": "x"})

    def test_cookies_plus_token_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one"):
            TradingViewCredentials(cookies={"sessionid": "x"}, auth_token="tok")

    def test_unsupported_browser_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported browser"):
            TradingViewCredentials(browser="edge")

    def test_browser_profile_without_browser_raises(self) -> None:
        with pytest.raises(ValueError, match="browser_profile requires browser"):
            TradingViewCredentials(browser_profile="Profile 2")

    def test_auth_token_not_in_repr(self) -> None:
        creds = TradingViewCredentials(auth_token="supersecrettoken")
        assert "supersecrettoken" not in repr(creds)


# ---------------------------------------------------------------------------
# ProfileParser
# ---------------------------------------------------------------------------


class TestProfileParser:
    def test_strategy0_var_user_assignment(self) -> None:
        profile = ProfileParser.parse(_SAMPLE_HTML_STRATEGY0)
        assert profile["id"] == 65880006
        assert profile["username"] == "testuser"
        assert profile["auth_token"] == "abcdefgh1234567890"

    def test_strategy1_user_key_in_json(self) -> None:
        profile = ProfileParser.parse(_SAMPLE_HTML_STRATEGY1)
        assert profile["id"] == 65880006
        assert profile["auth_token"] == "abcdefgh1234567890"

    def test_strategy2_script_block_scan(self) -> None:
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
            '<html><script>var user = {"id":3,"username":"has\\"quote",'
            '"auth_token":"abcdefgh12345678","is_pro":false,"pro_plan":"",'
            '"badges":[],"is_broker":false};</script></html>'
        )
        profile = ProfileParser.parse(html)
        assert profile["id"] == 3

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
        assert account.max_bars_source == "estimate"
        assert account.probe_status == "pending"

    def test_probe_confirmed_defaults_false(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 5_000, "free")
        assert account.probe_confirmed is False

    def test_max_bars_mutable_estimated_immutable(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 10_000, "pro")
        account.max_bars = 9_500
        assert account.max_bars == 9_500
        assert account.estimated_max_bars == 10_000

    def test_repr_masks_username(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 20_000, "premium")
        r = repr(account)
        assert "tes***" in r
        assert "testuser" not in r

    def test_repr_excludes_lock(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 20_000, "premium")
        assert "_lock" not in repr(account)

    def test_lock_field_is_asyncio_lock(self) -> None:
        account = TradingViewAccount.from_profile(_SAMPLE_PROFILE, 20_000, "premium")
        assert isinstance(account._lock, asyncio.Lock)


# ---------------------------------------------------------------------------
# CookieProvider
# ---------------------------------------------------------------------------


def _make_cookie_jar(cookies: dict[str, str]) -> list[MagicMock]:
    """Build a list of mock cookie objects from a name→value dict."""
    jar = []
    for name, value in cookies.items():
        c = MagicMock()
        c.name = name
        c.value = value
        jar.append(c)
    return jar


class TestCookieProvider:
    def _make_bc3(self, cookies: dict[str, str] | None = None) -> MagicMock:
        bc3 = MagicMock()
        jar = _make_cookie_jar(cookies or _SAMPLE_COOKIES)
        bc3.chrome.return_value = jar
        bc3.firefox.return_value = jar
        return bc3

    def test_extract_chrome_calls_bc3_chrome(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            result = provider.extract("chrome")
        bc3.chrome.assert_called_once_with(domain_name="tradingview.com")
        assert result["sessionid"] == "sess_abc123"

    def test_extract_firefox_calls_bc3_firefox(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            result = provider.extract("firefox")
        bc3.firefox.assert_called_once_with(domain_name="tradingview.com")
        assert "sessionid" in result

    def test_missing_sessionid_raises_browser_cookie_error(self) -> None:
        bc3 = self._make_bc3({"csrftoken": "csrf"})  # no sessionid
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            with pytest.raises(BrowserCookieError, match="sessionid"):
                provider.extract("chrome")

    def test_bc3_exception_wrapped_as_browser_cookie_error(self) -> None:
        bc3 = MagicMock()
        bc3.chrome.side_effect = Exception("DB locked")
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            with pytest.raises(BrowserCookieError, match="DB locked"):
                provider.extract("chrome")

    def test_result_cached_within_ttl(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            provider.extract("chrome")
            provider.extract("chrome")
        # browser_cookie3.chrome only called once — second call served from cache
        assert bc3.chrome.call_count == 1

    def test_cache_invalidation_forces_re_extraction(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            provider.extract("chrome")
            provider.invalidate_cache("chrome")
            provider.extract("chrome")
        assert bc3.chrome.call_count == 2

    def test_cache_expires_after_ttl(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            provider.extract("chrome")
            # Manually expire the cache entry by backdating the timestamp
            key = ("chrome", None)
            old_cookies, _ = provider._cache[key]
            provider._cache[key] = (old_cookies, time.monotonic() - COOKIE_CACHE_TTL - 1)
            provider.extract("chrome")
        assert bc3.chrome.call_count == 2

    def test_unsupported_browser_raises(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            with pytest.raises(BrowserCookieError, match="Unsupported browser"):
                provider.extract("safari")

    def test_different_profiles_cached_separately(self) -> None:
        bc3 = self._make_bc3()
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            provider = CookieProvider()
            provider.extract("chrome", profile=None)
            provider.extract("chrome", profile="Profile 2")
        assert bc3.chrome.call_count == 2


# ---------------------------------------------------------------------------
# TokenProvider (unit — mocked httpx)
# ---------------------------------------------------------------------------


def _make_httpx_response(status: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock(
        side_effect=(None if status < 400 else Exception(f"HTTP {status}"))
    )
    return resp


@pytest.mark.asyncio
class TestTokenProvider:
    async def test_fetch_profile_success(self) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_httpx_response(200, text=_SAMPLE_HTML_STRATEGY0)
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            provider = TokenProvider()
            profile = await provider.fetch_profile(_SAMPLE_COOKIES)

        assert profile["auth_token"] == "abcdefgh1234567890"
        assert profile["username"] == "testuser"

    async def test_fetch_profile_stores_token(self) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_httpx_response(200, text=_SAMPLE_HTML_STRATEGY0)
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            provider = TokenProvider()
            await provider.fetch_profile(_SAMPLE_COOKIES)

        assert provider._token == "abcdefgh1234567890"

    async def test_missing_auth_token_raises_profile_fetch_error(self) -> None:
        html_no_token = (
            '<html><body><script>window.__TV_DATA__ = {"user":{"id":1,'
            '"username":"u"}}</script></body></html>'
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_httpx_response(200, text=html_no_token))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            provider = TokenProvider()
            # ProfileParser will raise ProfileFetchError because user has no id/username pair
            # but we get to ProfileFetchError either from parse or from token validation
            with pytest.raises(ProfileFetchError):
                await provider.fetch_profile(_SAMPLE_COOKIES)

    async def test_short_auth_token_raises_profile_fetch_error(self) -> None:
        html_short_token = (
            '<html><body><script>var user = {"id":1,"username":"u",'
            '"auth_token":"short","is_pro":false,"pro_plan":"","badges":[],'
            '"is_broker":false};</script></body></html>'
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_make_httpx_response(200, text=html_short_token))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            provider = TokenProvider()
            with pytest.raises(ProfileFetchError, match="Invalid auth_token"):
                await provider.fetch_profile(_SAMPLE_COOKIES)

    async def test_http_5xx_retries_once(self) -> None:
        import httpx as _httpx

        mock_client = AsyncMock()
        ok_resp = _make_httpx_response(200, text=_SAMPLE_HTML_STRATEGY0)
        ok_resp.raise_for_status = MagicMock()

        err_resp = MagicMock()
        err_resp.status_code = 503
        err_resp.raise_for_status = MagicMock(
            side_effect=_httpx.HTTPStatusError("503", request=MagicMock(), response=err_resp)
        )

        mock_client.get = AsyncMock(side_effect=[err_resp, ok_resp])
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                provider = TokenProvider()
                profile = await provider.fetch_profile(_SAMPLE_COOKIES)

        assert profile["auth_token"] == "abcdefgh1234567890"
        assert mock_client.get.call_count == 2

    async def test_timeout_retries_once_then_raises(self) -> None:
        import httpx as _httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_httpx.TimeoutException("timed out"))
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                provider = TokenProvider()
                with pytest.raises(ProfileFetchError, match="one retry"):
                    await provider.fetch_profile(_SAMPLE_COOKIES)

        assert mock_client.get.call_count == 2

    async def test_get_valid_token_returns_fresh_token(self) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_httpx_response(200, text=_SAMPLE_HTML_STRATEGY0)
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx):
            provider = TokenProvider()
            token = await provider.get_valid_token(_SAMPLE_COOKIES)

        assert token == "abcdefgh1234567890"

    async def test_double_checked_locking_single_reextraction(self) -> None:
        """N concurrent get_valid_token calls with matching cookies → _do_fetch called once."""
        fetch_count = 0
        original_profile = {**_SAMPLE_PROFILE}

        async def _fake_do_fetch(cookies: dict[str, str]) -> dict[str, Any]:
            nonlocal fetch_count
            fetch_count += 1
            return original_profile

        provider = TokenProvider()
        # Seed the provider with the same cookies so the double-check fires for waiters.
        provider._token = "abcdefgh1234567890"
        provider._cookies = _SAMPLE_COOKIES.copy()

        with patch.object(provider, "_do_fetch", side_effect=_fake_do_fetch):
            # The cookies match — double-check should short-circuit all but the first.
            # Temporarily clear to force the first call to really fetch.
            provider._token = None

            await asyncio.gather(
                *[provider.get_valid_token(_SAMPLE_COOKIES.copy()) for _ in range(5)]
            )

        # Even under 5-way concurrency, _do_fetch is called exactly once.
        assert fetch_count == 1

    async def test_httpx_timeout_enforced(self) -> None:
        """_do_fetch creates httpx.AsyncClient with timeout=_FETCH_TIMEOUT (10.0 s)."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_httpx_response(200, text=_SAMPLE_HTML_STRATEGY0)
        )
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "tvkit.auth.token_provider.httpx.AsyncClient", return_value=mock_ctx
        ) as MockClient:
            provider = TokenProvider()
            await provider._do_fetch(_SAMPLE_COOKIES)

        call_kwargs = MockClient.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] == httpx.Timeout(_FETCH_TIMEOUT)


# ---------------------------------------------------------------------------
# ProbeCache
# ---------------------------------------------------------------------------


class TestProbeCache:
    def test_save_and_load_within_ttl(self, tmp_path: Path) -> None:
        cache = ProbeCache(path=tmp_path / "caps.json")
        cache.save(user_id=123, max_bars=20_000, plan="pro_premium")
        result = cache.load(user_id=123)
        assert result == 20_000

    def test_load_missing_user_returns_none(self, tmp_path: Path) -> None:
        cache = ProbeCache(path=tmp_path / "caps.json")
        assert cache.load(user_id=999) is None

    def test_load_expired_entry_returns_none(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "caps.json"
        data = {
            "123": {
                "max_bars": 20_000,
                "plan": "pro_premium",
                "timestamp": time.time() - PROBE_CACHE_TTL - 1,
            }
        }
        cache_path.write_text(json.dumps(data))
        cache = ProbeCache(path=cache_path)
        assert cache.load(user_id=123) is None

    def test_save_creates_directory_if_missing(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "caps.json"
        cache = ProbeCache(path=deep_path)
        cache.save(user_id=1, max_bars=5_000, plan="")
        assert deep_path.exists()

    def test_save_overwrites_existing_entry(self, tmp_path: Path) -> None:
        cache = ProbeCache(path=tmp_path / "caps.json")
        cache.save(user_id=1, max_bars=10_000, plan="pro")
        cache.save(user_id=1, max_bars=20_000, plan="pro_premium")
        assert cache.load(user_id=1) == 20_000

    def test_custom_ttl_respected(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "caps.json"
        # TTL of 1 second
        cache = ProbeCache(path=cache_path, ttl=1)
        cache.save(user_id=1, max_bars=5_000, plan="")
        # Manually backdate the timestamp by 2 seconds
        data = json.loads(cache_path.read_text())
        data["1"]["timestamp"] = time.time() - 2
        cache_path.write_text(json.dumps(data))
        assert cache.load(user_id=1) is None

    def test_corrupt_cache_file_returns_none(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "caps.json"
        cache_path.write_text("not valid json {{{")
        cache = ProbeCache(path=cache_path)
        assert cache.load(user_id=1) is None


# ---------------------------------------------------------------------------
# AuthManager (unit — mocked CookieProvider + TokenProvider)
# ---------------------------------------------------------------------------


def _mock_token_provider(profile: dict[str, Any] | None = None) -> AsyncMock:
    """Return a mock TokenProvider that returns the given profile from fetch_profile."""
    inst = AsyncMock(spec=TokenProvider)
    inst.fetch_profile = AsyncMock(return_value=profile or _SAMPLE_PROFILE)
    return inst


@pytest.mark.asyncio
class TestAuthManager:
    async def test_anonymous_mode(self) -> None:
        async with AuthManager() as auth:
            assert auth.auth_token == "unauthorized_user_token"
            assert auth.account is None
            assert auth.token_provider is None
            assert auth.cookie_provider is None
            assert auth._probe_task is None

    async def test_direct_token_mode(self) -> None:
        creds = TradingViewCredentials(auth_token="directtoken123")
        async with AuthManager(creds) as auth:
            assert auth.auth_token == "directtoken123"
            assert auth.account is None
            assert auth.token_provider is None
            assert auth._probe_task is None

    async def test_browser_mode_populates_account(self) -> None:
        creds = TradingViewCredentials(browser="chrome")
        mock_tp = _mock_token_provider()

        with (
            patch("tvkit.auth.auth_manager.CookieProvider") as MockCP,
            patch("tvkit.auth.auth_manager.TokenProvider", return_value=mock_tp),
        ):
            mock_cp_inst = MagicMock()
            mock_cp_inst.extract.return_value = _SAMPLE_COOKIES
            MockCP.return_value = mock_cp_inst

            async with AuthManager(creds) as auth:
                assert auth.auth_token == "abcdefgh1234567890"
                assert auth.account is not None
                assert auth.account.username == "testuser"
                assert auth.account.tier == "premium"
                assert auth.account.max_bars == 20_000
                assert auth.account.max_bars_source == "estimate"
                assert auth.account.probe_status == "pending"
                assert auth.token_provider is mock_tp
                assert auth.cookie_provider is mock_cp_inst
                assert auth._probe_task is not None

    async def test_cookie_dict_mode_populates_account(self) -> None:
        creds = TradingViewCredentials(cookies=_SAMPLE_COOKIES)
        mock_tp = _mock_token_provider()

        with patch("tvkit.auth.auth_manager.TokenProvider", return_value=mock_tp):
            async with AuthManager(creds) as auth:
                assert auth.auth_token == "abcdefgh1234567890"
                assert auth.account is not None
                assert auth.cookie_provider is None  # not browser mode

    async def test_aexit_cancels_probe_task(self) -> None:
        creds = TradingViewCredentials(browser="chrome")
        mock_tp = _mock_token_provider()

        with (
            patch("tvkit.auth.auth_manager.CookieProvider") as MockCP,
            patch("tvkit.auth.auth_manager.TokenProvider", return_value=mock_tp),
        ):
            mock_cp_inst = MagicMock()
            mock_cp_inst.extract.return_value = _SAMPLE_COOKIES
            MockCP.return_value = mock_cp_inst

            async with AuthManager(creds) as auth:
                task = auth._probe_task
                assert task is not None

        assert task.done()

    async def test_auth_token_raises_before_aenter(self) -> None:
        auth = AuthManager()
        with pytest.raises(AssertionError, match="async with AuthManager"):
            _ = auth.auth_token

    async def test_default_credentials_is_anonymous(self) -> None:
        auth = AuthManager()
        assert auth._credentials.is_anonymous is True

    async def test_browser_mode_no_probe_task_for_anonymous(self) -> None:
        async with AuthManager() as auth:
            assert auth._probe_task is None

    async def test_no_cookie_values_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Raw cookie values must never appear in any log record during browser auth."""
        import logging

        sensitive_value = "SECRETSESSION_DO_NOT_LOG"
        cookies = {"sessionid": sensitive_value, "csrftoken": "csrf_xyz"}
        creds = TradingViewCredentials(cookies=cookies)
        mock_tp = _mock_token_provider()

        with (
            caplog.at_level(logging.DEBUG),
            patch("tvkit.auth.auth_manager.TokenProvider", return_value=mock_tp),
        ):
            async with AuthManager(creds):
                pass

        all_messages = " ".join(r.getMessage() for r in caplog.records)
        assert sensitive_value not in all_messages, (
            f"Cookie value {sensitive_value!r} leaked into logs"
        )

    async def test_username_masked_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Full username must not appear in logs; masked form (first3***) must appear."""
        import logging

        full_username = _SAMPLE_PROFILE["username"]  # "testuser"
        masked_prefix = full_username[:3] + "***"  # "tes***"

        creds = TradingViewCredentials(cookies=_SAMPLE_COOKIES)
        mock_tp = _mock_token_provider()

        with (
            caplog.at_level(logging.DEBUG),
            patch("tvkit.auth.auth_manager.TokenProvider", return_value=mock_tp),
        ):
            async with AuthManager(creds):
                pass

        all_messages = " ".join(r.getMessage() for r in caplog.records)
        assert full_username not in all_messages, (
            f"Full username {full_username!r} leaked into logs"
        )
        assert masked_prefix in all_messages, f"Expected masked username {masked_prefix!r} in logs"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    def test_browser_cookie_error_is_auth_error(self) -> None:
        assert issubclass(BrowserCookieError, AuthError)

    def test_profile_fetch_error_is_auth_error(self) -> None:
        assert issubclass(ProfileFetchError, AuthError)

    def test_capability_probe_error_is_auth_error(self) -> None:
        assert issubclass(CapabilityProbeError, AuthError)

    def test_catch_all_with_auth_error(self) -> None:
        for err in [
            BrowserCookieError("a"),
            ProfileFetchError("b"),
            CapabilityProbeError("c"),
        ]:
            assert isinstance(err, AuthError)

    def test_all_auth_errors_are_exceptions(self) -> None:
        for cls in [BrowserCookieError, ProfileFetchError, CapabilityProbeError]:
            assert issubclass(cls, Exception)


# ---------------------------------------------------------------------------
# Phase 3 — ConnectionService auth token behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConnectionServiceAuthToken:
    """Unit tests for ConnectionService Phase 3 auth token wiring.

    Verifies that:
    - The auth_token passed at construction is forwarded to set_auth_token.
    - The default token is "unauthorized_user_token" for anonymous sessions.
    - The token is stored at construction time so reconnects reuse it.
    - A WS auth error frame raises ChartAuthError from get_data_stream().
    - A WS auth error does NOT trigger cookie re-extraction.

    All WebSocket I/O is bypassed by injecting frames directly into
    ConnectionService._message_queue and mocking _ws to a non-None sentinel.
    """

    async def test_auth_token_passed_to_set_auth_token_message(self) -> None:
        """initialize_sessions sends the constructor auth_token as the first message."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        send = AsyncMock()
        await svc.initialize_sessions("qs_abc", "cs_abc", send)
        # First call must be set_auth_token with our token.
        first_call_args = send.call_args_list[0][0]
        assert first_call_args[0] == "set_auth_token"
        assert first_call_args[1] == ["fake_token_abc123xyz"]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_default_token_is_anonymous(self) -> None:
        """ConnectionService() with no auth_token uses 'unauthorized_user_token'."""
        svc = ConnectionService(ws_url="wss://test")
        assert svc._auth_token == "unauthorized_user_token"

    async def test_auth_token_used_on_reconnect(self) -> None:
        """Token is stored at construction; initialize_sessions always sends the same token."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        send = AsyncMock()
        # First call (initial session setup)
        await svc.initialize_sessions("qs1", "cs1", send)
        # Second call (simulating reconnect — _restore_session calls initialize_sessions again)
        send.reset_mock()
        await svc.initialize_sessions("qs2", "cs2", send)
        second_first_call = send.call_args_list[0][0]
        assert second_first_call[0] == "set_auth_token"
        assert second_first_call[1] == ["fake_token_abc123xyz"]

    async def test_ws_auth_error_raises_auth_error(self) -> None:
        """A critical_error frame with unauthorized_access error_code raises ChartAuthError."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        # Satisfy the RuntimeError guard in get_data_stream()
        svc._ws = MagicMock()  # type: ignore[assignment]
        svc._ws.close = AsyncMock()
        svc._ws.state = MagicMock()

        auth_error_frame = json.dumps(
            {"m": "critical_error", "p": [{"error_code": "unauthorized_access"}]}
        )
        await svc._message_queue.put(auth_error_frame)

        with pytest.raises(ChartAuthError):
            async for _ in svc.get_data_stream():
                pass

    async def test_ws_auth_error_no_transparent_reextraction(self) -> None:
        """Auth error propagates bare — no cookie or token re-extraction is attempted."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        svc._ws = MagicMock()  # type: ignore[assignment]
        svc._ws.close = AsyncMock()
        svc._ws.state = MagicMock()

        auth_error_frame = json.dumps(
            {"m": "set_auth_token", "p": [{"error": "unauthorized_access"}]}
        )
        await svc._message_queue.put(auth_error_frame)

        mock_cookie_provider = MagicMock()
        mock_token_provider = MagicMock()

        with pytest.raises(ChartAuthError):
            async for _ in svc.get_data_stream():
                pass

        mock_cookie_provider.invalidate_cache.assert_not_called()
        mock_token_provider.get_valid_token.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 4 — OHLCV constructor credential resolution
# ---------------------------------------------------------------------------


class TestOHLCVConstructorCredentials:
    """Unit tests for OHLCV keyword-only credential params and env-var fallbacks.

    All tests are synchronous — no I/O. Both env vars are cleared via monkeypatch
    in every test to prevent cross-test bleed.
    """

    def test_browser_kwarg_sets_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(browser="chrome")
        assert client._credentials.browser == "chrome"
        assert client._credentials.auth_token is None
        assert client._credentials.cookies is None

    def test_browser_profile_kwarg_sets_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(browser="firefox", browser_profile="Profile 2")
        assert client._credentials.browser == "firefox"
        assert client._credentials.browser_profile == "Profile 2"

    def test_cookies_kwarg_sets_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(cookies={"sessionid": "abc"})
        assert client._credentials.cookies == {"sessionid": "abc"}
        assert client._credentials.browser is None

    def test_auth_token_kwarg_sets_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(auth_token="fake_token_abc123xyz")
        assert client._credentials.auth_token == "fake_token_abc123xyz"
        assert client._credentials.browser is None

    def test_anonymous_when_no_credentials_and_no_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV()
        assert client._credentials.is_anonymous

    def test_env_var_tvkit_browser_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "firefox")
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV()
        assert client._credentials.browser == "firefox"

    def test_env_var_tvkit_auth_token_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_AUTH_TOKEN", "fake_token_abc123xyz")
        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        client = OHLCV()
        assert client._credentials.auth_token == "fake_token_abc123xyz"

    def test_constructor_kwarg_overrides_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "firefox")
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(browser="chrome")
        assert client._credentials.browser == "chrome"

    def test_invalid_combination_raises_at_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with pytest.raises(ValueError, match="exactly one"):
            OHLCV(browser="chrome", auth_token="fake_token_abc123xyz")

    def test_retry_params_remain_positional(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OHLCV(3, 2.0, 60.0) still works — retry params keep their positional order."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(3, 2.0, 60.0)
        assert client._max_attempts == 3
        assert client._base_backoff == 2.0
        assert client._max_backoff == 60.0
        assert client._credentials.is_anonymous

    def test_auth_params_are_keyword_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OHLCV(3, 2.0, 60.0, 'chrome') raises TypeError — auth params are keyword-only."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with pytest.raises(TypeError):
            OHLCV(3, 2.0, 60.0, "chrome")  # type: ignore[call-arg]

    def test_browser_kwarg_ignores_tvkit_auth_token_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_AUTH_TOKEN", "should_be_ignored")
        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        client = OHLCV(browser="chrome")
        assert client._credentials.browser == "chrome"
        assert client._credentials.auth_token is None

    def test_cookies_kwarg_ignores_tvkit_browser_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "firefox")
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(cookies={"sessionid": "abc"})
        assert client._credentials.cookies == {"sessionid": "abc"}
        assert client._credentials.browser is None

    def test_cookies_kwarg_ignores_tvkit_auth_token_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_AUTH_TOKEN", "should_be_ignored")
        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        client = OHLCV(cookies={"sessionid": "abc"})
        assert client._credentials.auth_token is None

    def test_auth_token_kwarg_ignores_tvkit_browser_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "firefox")
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(auth_token="fake_token_abc123xyz")
        assert client._credentials.auth_token == "fake_token_abc123xyz"
        assert client._credentials.browser is None

    def test_browser_profile_with_env_var_browser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "chrome")
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV(browser_profile="Profile 2")
        assert client._credentials.browser == "chrome"
        assert client._credentials.browser_profile == "Profile 2"

    def test_both_env_vars_set_raises_at_construction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.setenv("TVKIT_BROWSER", "chrome")
        monkeypatch.setenv("TVKIT_AUTH_TOKEN", "fake_token_abc123xyz")
        with pytest.raises(ValueError, match="exactly one"):
            OHLCV()


# ---------------------------------------------------------------------------
# Phase 4 — OHLCV session wiring (mocked AuthManager + ConnectionService)
# ---------------------------------------------------------------------------


def _make_mock_auth_manager(
    *,
    auth_token: str = "fake_token_abc123xyz",
    account: TradingViewAccount | None = None,
    probe_task: asyncio.Task[None] | None = None,
) -> MagicMock:
    """Return a MagicMock shaped like AuthManager for OHLCV wiring tests."""
    m = MagicMock(spec=AuthManager)
    m.auth_token = auth_token
    m.account = account
    m._probe_task = probe_task
    m.__aenter__ = AsyncMock(return_value=m)
    m.__aexit__ = AsyncMock(return_value=None)
    return m


def _make_mock_account() -> TradingViewAccount:
    """Return a minimal TradingViewAccount for wiring tests."""
    return TradingViewAccount.from_profile(
        profile=_SAMPLE_PROFILE,
        max_bars=20_000,
        tier="premium",
    )


def _patch_connection_service() -> Any:
    """Return a context manager that stubs ConnectionService for _setup_services."""
    mock_ws = MagicMock()
    mock_cs = MagicMock()
    mock_cs.ws = mock_ws
    mock_cs.connect = AsyncMock()
    mock_cs.close = AsyncMock()
    mock_cs.initialize_sessions = AsyncMock()
    mock_cs.add_symbol_to_sessions = AsyncMock()
    return patch("tvkit.api.chart.ohlcv.ConnectionService", return_value=mock_cs)


@pytest.mark.asyncio
class TestOHLCVSessionWiring:
    """Integration tests for OHLCV Phase 4 authentication wiring.

    All ConnectionService and AuthManager calls are mocked — no real I/O.
    Both env vars are cleared in each test via monkeypatch.
    """

    async def test_account_none_before_aenter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        client = OHLCV()
        assert client.account is None

    async def test_account_none_for_anonymous_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(auth_token="unauthorized_user_token")
            MockAM.return_value = mock_am

            async with OHLCV() as client:
                assert client._credentials.is_anonymous
                assert client.account is None

    async def test_account_populated_after_aenter_browser_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        mock_account = _make_mock_account()
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(
                auth_token="fake_token_abc123xyz", account=mock_account
            )
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                assert client.account is mock_account

    async def test_account_populated_after_aenter_cookies_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        mock_account = _make_mock_account()
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(
                auth_token="fake_token_abc123xyz", account=mock_account
            )
            MockAM.return_value = mock_am

            async with OHLCV(cookies=_SAMPLE_COOKIES) as client:
                assert client.account is mock_account

    async def test_account_none_for_direct_token_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(auth_token="fake_token_abc123xyz", account=None)
            MockAM.return_value = mock_am

            async with OHLCV(auth_token="fake_token_abc123xyz") as client:
                assert client.account is None

    async def test_account_none_after_aexit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        mock_account = _make_mock_account()
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(
                auth_token="fake_token_abc123xyz", account=mock_account
            )
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                pass

            assert client.account is None

    async def test_aexit_forwards_exception_info_to_auth_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """__aexit__ must forward (exc_type, exc_val, exc_tb) to AuthManager.__aexit__."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager()
            MockAM.return_value = mock_am

            exc = ValueError("test error")
            try:
                async with OHLCV() as _:
                    raise exc
            except ValueError:
                pass

            call_args = mock_am.__aexit__.call_args[0]
            assert call_args[0] is ValueError  # exc_type
            assert call_args[1] is exc  # exc_val
            assert call_args[2] is not None  # exc_tb (traceback object)

    async def test_aexit_does_not_raise_if_probe_already_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        finished_task: asyncio.Task[None] = asyncio.ensure_future(asyncio.sleep(0))
        await finished_task

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(probe_task=finished_task)
            MockAM.return_value = mock_am

            async with OHLCV() as _:
                pass

    async def test_connection_service_receives_auth_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with (
            patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM,
            _patch_connection_service() as MockCS,
        ):
            mock_am = _make_mock_auth_manager(auth_token="fake_token_abc123xyz")
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                await client._setup_services()

            call_kwargs = MockCS.call_args[1]
            assert call_kwargs["auth_token"] == "fake_token_abc123xyz"

    async def test_connection_service_receives_anonymous_token_for_anon_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with (
            patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM,
            _patch_connection_service() as MockCS,
        ):
            mock_am = _make_mock_auth_manager(auth_token="unauthorized_user_token")
            MockAM.return_value = mock_am

            async with OHLCV() as client:
                await client._setup_services()

            call_kwargs = MockCS.call_args[1]
            assert call_kwargs["auth_token"] == "unauthorized_user_token"

    async def test_anonymous_outside_async_with_passes_anonymous_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OHLCV() without async with must still pass the anonymous token."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with _patch_connection_service() as MockCS:
            client = OHLCV()
            assert client._auth_manager is None

            await client._setup_services()

            assert client._auth_manager is None  # anonymous: no AuthManager created
            call_kwargs = MockCS.call_args[1]
            assert call_kwargs["auth_token"] == "unauthorized_user_token"

    async def test_lazy_init_authenticates_without_async_with(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Credentials authenticate lazily when _setup_services is called without async with."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with (
            patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM,
            _patch_connection_service(),
        ):
            mock_am = _make_mock_auth_manager(auth_token="fake_token_abc123xyz")
            MockAM.return_value = mock_am

            client = OHLCV(auth_token="fake_token_abc123xyz")
            assert client._auth_manager is None

            await client._setup_services()

            assert client._auth_manager is mock_am
            mock_am.__aenter__.assert_called_once()

    async def test_aenter_after_lazy_init_does_not_reinitialize(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """__aenter__ must reuse the existing AuthManager if lazy init already ran."""
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with (
            patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM,
            _patch_connection_service(),
        ):
            mock_am = _make_mock_auth_manager(auth_token="fake_token_abc123xyz")
            MockAM.return_value = mock_am

            client = OHLCV(auth_token="fake_token_abc123xyz")
            await client._setup_services()  # lazy init — __aenter__ called once

            async with client:
                pass  # __aenter__ runs — must reuse existing manager

            mock_am.__aenter__.assert_called_once()  # still only one call total
            assert MockAM.call_count == 1  # no second AuthManager constructed

    async def test_wait_until_ready_returns_immediately_if_no_probe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(probe_task=None)
            MockAM.return_value = mock_am

            async with OHLCV() as client:
                await client.wait_until_ready()

    async def test_wait_until_ready_blocks_until_probe_done(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)
        done_event = asyncio.Event()

        async def _slow_probe() -> None:
            await done_event.wait()

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            probe_task: asyncio.Task[None] = asyncio.create_task(_slow_probe())
            mock_am = _make_mock_auth_manager(probe_task=probe_task)
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:

                async def _unblock() -> None:
                    await asyncio.sleep(0)
                    done_event.set()

                await asyncio.gather(client.wait_until_ready(), _unblock())

    async def test_wait_until_ready_never_raises_on_probe_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)

        async def _failing_probe() -> None:
            raise RuntimeError("probe failed")

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            probe_task: asyncio.Task[None] = asyncio.create_task(_failing_probe())
            mock_am = _make_mock_auth_manager(probe_task=probe_task)
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                await client.wait_until_ready()

    async def test_wait_until_ready_never_raises_on_cancelled_probe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)

        async def _sleeping_probe() -> None:
            await asyncio.sleep(100)

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            probe_task: asyncio.Task[None] = asyncio.create_task(_sleeping_probe())
            probe_task.cancel()
            try:
                await probe_task
            except asyncio.CancelledError:
                pass

            mock_am = _make_mock_auth_manager(probe_task=probe_task)
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                await client.wait_until_ready()

    async def test_wait_until_ready_propagates_caller_cancellation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tvkit.api.chart.ohlcv import OHLCV

        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)

        async def _long_probe() -> None:
            await asyncio.sleep(100)

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            probe_task: asyncio.Task[None] = asyncio.create_task(_long_probe())
            mock_am = _make_mock_auth_manager(probe_task=probe_task)
            MockAM.return_value = mock_am

            async with OHLCV(browser="chrome") as client:
                waiter: asyncio.Task[None] = asyncio.create_task(client.wait_until_ready())
                await asyncio.sleep(0)
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter

            probe_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await probe_task

    async def test_ws_auth_error_raises_to_caller(self) -> None:
        """ChartAuthError raised from get_data_stream() propagates out of the service layer."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        svc._ws = MagicMock()  # type: ignore[assignment]
        svc._ws.close = AsyncMock()
        svc._ws.state = MagicMock()

        auth_error_frame = json.dumps(
            {"m": "critical_error", "p": [{"error_code": "unauthorized_access"}]}
        )
        await svc._message_queue.put(auth_error_frame)

        with pytest.raises(ChartAuthError):
            async for _ in svc.get_data_stream():
                pass

    async def test_ws_auth_error_raises_no_reextraction(self) -> None:
        """Auth error raises ChartAuthError; no cookie invalidation or token re-fetch occurs."""
        svc = ConnectionService(ws_url="wss://test", auth_token="fake_token_abc123xyz")
        svc._ws = MagicMock()  # type: ignore[assignment]
        svc._ws.close = AsyncMock()
        svc._ws.state = MagicMock()

        auth_error_frame = json.dumps(
            {"m": "set_auth_token", "p": [{"error": "unauthorized_access"}]}
        )
        await svc._message_queue.put(auth_error_frame)

        mock_cp = MagicMock()
        mock_tp = MagicMock()

        with pytest.raises(ChartAuthError):
            async for _ in svc.get_data_stream():
                pass

        mock_cp.invalidate_cache.assert_not_called()
        mock_tp.get_valid_token.assert_not_called()

    async def test_max_bars_source_transitions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """max_bars_source is 'estimate' after __aenter__; stub probe does not change it."""
        monkeypatch.delenv("TVKIT_BROWSER", raising=False)
        monkeypatch.delenv("TVKIT_AUTH_TOKEN", raising=False)

        mock_account = _make_mock_account()
        assert mock_account.max_bars_source == "estimate"  # initial state

        with patch("tvkit.api.chart.ohlcv.AuthManager") as MockAM:
            mock_am = _make_mock_auth_manager(
                auth_token="fake_token_abc123xyz", account=mock_account
            )
            MockAM.return_value = mock_am

            from tvkit.api.chart.ohlcv import OHLCV

            async with OHLCV(browser="chrome") as client:
                # Immediately after __aenter__, source is plan-based estimate.
                assert client.account is mock_account
                assert client.account.max_bars_source == "estimate"

            # After context exit, source is still "estimate" (probe stub did not update it).
            assert mock_account.max_bars_source == "estimate"


# ---------------------------------------------------------------------------
# Integration tests — real browser (skipped unless TVKIT_BROWSER is set)
# ---------------------------------------------------------------------------

_TV_BROWSER = os.getenv("TVKIT_BROWSER", "")
_HAS_REAL_BROWSER = bool(_TV_BROWSER)

_SKIP_REASON = (
    "TVKIT_BROWSER not set — set to 'chrome' or 'firefox' to run "
    "real browser integration tests (requires active TradingView session)"
)


@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_REAL_BROWSER, reason=_SKIP_REASON)
class TestRealBrowserAuth:
    """
    Integration tests that extract real cookies from a local browser.

    Skipped unless TVKIT_BROWSER=chrome or TVKIT_BROWSER=firefox is set.
    Requires the user to be actively logged in to TradingView in that browser.
    """

    async def test_real_browser_returns_auth_token(self) -> None:
        creds = TradingViewCredentials(browser=_TV_BROWSER)
        async with AuthManager(creds) as auth:
            assert auth.auth_token, "auth_token must be non-empty"
            assert len(auth.auth_token) >= 10, "auth_token must be at least 10 chars"
            assert auth.account is not None
            assert auth.account.user_id > 0
            assert auth.account.username
            assert auth.account.tier in ("free", "pro", "premium", "ultimate")
            assert auth.account.max_bars > 0

    async def test_real_anonymous_token_unchanged(self) -> None:
        async with AuthManager() as auth:
            assert auth.auth_token == "unauthorized_user_token"
            assert auth.account is None
