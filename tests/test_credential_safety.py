"""
Credential-safety guards: where tvkit's session credentials may and may not go.

Each class pins one leak path that existed before 0.18.1:

- ``TestAuthTokenNotLogged`` — ``MessageService.send_message`` logged every outgoing
  frame at DEBUG, ``set_auth_token`` included, and the bug-report template asks users
  to paste DEBUG output into a public issue.
- ``TestSessionCookieStaysOnTradingView`` — ``TokenProvider`` handed httpx a plain
  cookie dict with ``follow_redirects=True``. httpx sends domain-less cookies to every
  host, so a redirect off TradingView would have carried ``sessionid`` with it.
- ``TestLookalikeCookiesDropped`` — ``browser_cookie3`` matches ``%tradingview.com%``,
  so cookies from look-alike hosts reached the flattened cookie dict.
- ``TestProbeCachePermissions`` — the cache directory was created with the umask's
  mode (``0775`` under umask ``002``), and a malformed entry raised.
- ``TestCookieExportFileMode`` — ``scripts/export_tv_cookies.py`` wrote the session
  cookies with ``Path.write_text`` (``0664`` under umask ``002``).

No network: httpx runs against ``httpx.MockTransport``.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import stat
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tvkit.api.chart.services.message_service import MessageService
from tvkit.auth import BrowserCookieError, CookieProvider, ProfileFetchError
from tvkit.auth import probe_cache as probe_cache_module
from tvkit.auth.probe_cache import ProbeCache
from tvkit.auth.token_provider import TokenProvider, _scoped_cookies

REPO_ROOT = Path(__file__).resolve().parents[1]

_TOKEN = "eyJSECRET.TOKEN.VALUE-0123456789"
_COOKIES = {"sessionid": "SESSION-SECRET", "sessionid_sign": "SIGN-SECRET"}
_PROFILE_HTML = (
    '<html><body><script>var user = {"id":1,"username":"u",'
    f'"auth_token":"{_TOKEN}","is_pro":false,"pro_plan":"","badges":[],'
    '"is_broker":false};</script></body></html>'
)

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")


# ---------------------------------------------------------------------------
# Auth token in DEBUG logs
# ---------------------------------------------------------------------------


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
class TestAuthTokenNotLogged:
    async def test_set_auth_token_frame_is_redacted(self, caplog: pytest.LogCaptureFixture) -> None:
        ws = _FakeWebSocket()
        service = MessageService(ws)  # type: ignore[arg-type]
        with caplog.at_level(logging.DEBUG):
            await service.send_message("set_auth_token", [_TOKEN])

        assert _TOKEN in ws.sent[0], "the token must still be SENT — only the log is redacted"
        assert _TOKEN not in caplog.text
        assert "set_auth_token (parameters redacted" in caplog.text

    async def test_other_frames_are_still_logged_verbatim(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Redaction is per-function, not a blanket mute of the debug log."""
        service = MessageService(_FakeWebSocket())  # type: ignore[arg-type]
        with caplog.at_level(logging.DEBUG):
            await service.send_message("quote_add_symbols", ["qs_abc", "NASDAQ:AAPL"])
        assert '"quote_add_symbols","p":["qs_abc","NASDAQ:AAPL"]' in caplog.text

    async def test_logs_under_the_module_logger_not_root(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A module logger lets users silence tvkit's frame log without touching root."""
        service = MessageService(_FakeWebSocket())  # type: ignore[arg-type]
        with caplog.at_level(logging.DEBUG):
            await service.send_message("set_locale", ["en", "US"])
        names = {r.name for r in caplog.records if "Sending message" in r.getMessage()}
        assert names == {"tvkit.api.chart.services.message_service"}


# ---------------------------------------------------------------------------
# Session cookies on redirect
# ---------------------------------------------------------------------------


def _client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[..., httpx.AsyncClient]:
    """Patch target for ``httpx.AsyncClient`` that keeps tvkit's kwargs and adds a mock transport."""
    real_client = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    return factory


def _redirecting_handler(
    location: str, seen: list[tuple[str, str | None]]
) -> Callable[[httpx.Request], httpx.Response]:
    """www.tradingview.com redirects to ``location``; any other host serves the profile page."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("cookie")))
        if request.url.host == "www.tradingview.com" and request.url.scheme == "https":
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, text=_PROFILE_HTML)

    return handler


@pytest.mark.asyncio
class TestSessionCookieStaysOnTradingView:
    @pytest.mark.parametrize(
        "location",
        [
            "https://attacker.example/landing",
            "https://nottradingview.com/",
            "https://www.tradingview.com.attacker.example/",
            "http://www.tradingview.com/",  # scheme downgrade
        ],
    )
    async def test_redirect_off_tradingview_is_refused_before_sending(self, location: str) -> None:
        seen: list[tuple[str, str | None]] = []
        factory = _client_factory(_redirecting_handler(location, seen))
        with patch("tvkit.auth.token_provider.httpx.AsyncClient", side_effect=factory):
            with pytest.raises(ProfileFetchError, match="Refusing to follow a redirect"):
                await TokenProvider().fetch_profile(_COOKIES)

        # Only the first request went out; the foreign hop was never sent at all.
        assert [host for host, _ in seen] == ["www.tradingview.com"]

    async def test_redirect_to_a_tradingview_subdomain_is_followed(self) -> None:
        seen: list[tuple[str, str | None]] = []
        factory = _client_factory(_redirecting_handler("https://th.tradingview.com/", seen))
        with patch("tvkit.auth.token_provider.httpx.AsyncClient", side_effect=factory):
            profile = await TokenProvider().fetch_profile(_COOKIES)

        assert profile["auth_token"] == _TOKEN
        assert [host for host, _ in seen] == ["www.tradingview.com", "th.tradingview.com"]
        assert all(cookie and "sessionid=SESSION-SECRET" in cookie for _, cookie in seen)

    async def test_scoped_jar_alone_withholds_cookies_from_another_host(self) -> None:
        """Second line of defence: even without the hook, the jar is bound to TradingView."""
        seen: list[tuple[str, str | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.host, request.headers.get("cookie")))
            return httpx.Response(200)

        async with httpx.AsyncClient(
            cookies=_scoped_cookies(_COOKIES), transport=httpx.MockTransport(handler)
        ) as client:
            await client.get("https://www.tradingview.com/")
            await client.get("https://attacker.example/")

        assert seen[0][1] is not None and "sessionid=SESSION-SECRET" in seen[0][1]
        assert seen[1] == ("attacker.example", None)

    async def test_invalid_token_error_does_not_echo_the_token(self) -> None:
        short = "xQ9zW"  # shorter than the 10-char minimum
        html = _PROFILE_HTML.replace(_TOKEN, short)
        factory = _client_factory(lambda request: httpx.Response(200, text=html))
        with patch("tvkit.auth.token_provider.httpx.AsyncClient", side_effect=factory):
            with pytest.raises(ProfileFetchError) as excinfo:
                await TokenProvider().fetch_profile(_COOKIES)
        assert short not in str(excinfo.value)
        assert "str of length 5" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Look-alike cookie domains
# ---------------------------------------------------------------------------


def _cookie(name: str, value: str, domain: str) -> MagicMock:
    c = MagicMock()
    c.name, c.value, c.domain = name, value, domain
    return c


def _provider_with_jar(jar: list[MagicMock]) -> tuple[CookieProvider, MagicMock]:
    bc3 = MagicMock()
    bc3.chrome.return_value = jar
    return CookieProvider(), bc3


class TestLookalikeCookiesDropped:
    def test_lookalike_sessionid_cannot_override_the_real_one(self) -> None:
        jar = [
            _cookie("sessionid", "REAL", ".tradingview.com"),
            _cookie("device_t", "DT", "www.tradingview.com"),
            _cookie("sessionid", "PLANTED", "nottradingview.com"),
            _cookie("tracker", "T", ".tradingview.com.attacker.example"),
        ]
        provider, bc3 = _provider_with_jar(jar)
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            cookies = provider.extract("chrome")
        assert cookies == {"sessionid": "REAL", "device_t": "DT"}

    def test_sessionid_only_on_a_lookalike_host_is_treated_as_missing(self) -> None:
        provider, bc3 = _provider_with_jar(
            [_cookie("sessionid", "PLANTED", "evil-tradingview.com")]
        )
        with patch("tvkit.auth.cookie_provider._get_browser_cookie3", return_value=bc3):
            with pytest.raises(BrowserCookieError, match="sessionid cookie not found"):
                provider.extract("chrome")


# ---------------------------------------------------------------------------
# ProbeCache permissions and malformed entries
# ---------------------------------------------------------------------------


@posix_only
class TestProbeCachePermissions:
    def test_new_cache_dir_is_0700_and_file_is_0600(self, tmp_path: Path) -> None:
        old_umask = os.umask(0o002)  # the umask that made settfex's directory group-writable
        try:
            path = tmp_path / "cachedir" / "capabilities.json"
            ProbeCache(path=path).save(user_id=1, max_bars=5_000, plan="")
        finally:
            os.umask(old_umask)
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_loose_default_dir_is_tightened(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        default = tmp_path / "home-cache" / "tvkit" / "capabilities.json"
        default.parent.mkdir(parents=True)
        default.parent.chmod(0o775)
        monkeypatch.setattr(probe_cache_module, "_CACHE_PATH", default)

        ProbeCache().save(user_id=1, max_bars=5_000, plan="")

        assert stat.S_IMODE(default.parent.stat().st_mode) == 0o700

    def test_existing_caller_dir_is_left_alone(self, tmp_path: Path) -> None:
        shared = tmp_path / "shared"
        shared.mkdir()
        shared.chmod(0o775)
        ProbeCache(path=shared / "caps.json").save(user_id=1, max_bars=5_000, plan="")
        assert stat.S_IMODE(shared.stat().st_mode) == 0o775


class TestProbeCacheMalformedEntry:
    @pytest.mark.parametrize(
        "entry",
        [
            ["not", "a", "dict"],
            {"timestamp": 9e18},  # no max_bars
            {"timestamp": "yesterday", "max_bars": 5000},
            {"timestamp": 9e18, "max_bars": None},
        ],
    )
    def test_malformed_entry_is_a_miss_not_a_crash(self, tmp_path: Path, entry: object) -> None:
        path = tmp_path / "caps.json"
        path.write_text(json.dumps({"1": entry}))
        assert ProbeCache(path=path).load(user_id=1) is None


# ---------------------------------------------------------------------------
# scripts/export_tv_cookies.py file mode
# ---------------------------------------------------------------------------


def _load_export_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "export_tv_cookies", REPO_ROOT / "scripts" / "export_tv_cookies.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@posix_only
class TestCookieExportFileMode:
    def test_new_file_is_0600(self, tmp_path: Path) -> None:
        old_umask = os.umask(0o002)
        try:
            dest = tmp_path / "tv_cookies.json"
            _load_export_script()._write_private(dest, json.dumps(_COOKIES))
        finally:
            os.umask(old_umask)
        assert stat.S_IMODE(dest.stat().st_mode) == 0o600
        assert json.loads(dest.read_text()) == _COOKIES

    def test_existing_loose_file_is_tightened(self, tmp_path: Path) -> None:
        dest = tmp_path / "tv_cookies.json"
        dest.write_text("{}")
        dest.chmod(0o664)
        _load_export_script()._write_private(dest, json.dumps(_COOKIES))
        assert stat.S_IMODE(dest.stat().st_mode) == 0o600
