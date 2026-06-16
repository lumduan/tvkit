"""Regression tests for tvkit.api.utils.indicator_service parsing robustness.

These cover the defensive-parsing fix in ``fetch_tradingview_indicators``: malformed
entries from TradingView's public ``pubscripts-suggest-json`` endpoint must be skipped
rather than raising ``KeyError``/``TypeError`` and aborting the whole search. All HTTP
I/O is mocked — no network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tvkit.api.utils.indicator_service import fetch_tradingview_indicators

_CLIENT_PATH = "tvkit.api.utils.indicator_service.httpx.AsyncClient"


def _mock_httpx_client(json_payload: object) -> MagicMock:
    """Return a patched ``httpx.AsyncClient`` context manager yielding ``json_payload``."""
    response = MagicMock()
    response.raise_for_status = MagicMock(return_value=None)
    response.json = MagicMock(return_value=json_payload)

    client = AsyncMock()
    client.get = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_fetch_indicators_parses_valid_entries() -> None:
    payload = {
        "results": [
            {
                "scriptName": "RSI Strategy",
                "imageUrl": "img/rsi.png",
                "author": {"username": "trader_joe"},
                "agreeCount": 42,
                "isRecommended": True,
                "scriptIdPart": "PUB;rsi",
                "version": "1.0",
            }
        ]
    }
    with patch(_CLIENT_PATH, return_value=_mock_httpx_client(payload)):
        results = await fetch_tradingview_indicators("rsi")

    assert len(results) == 1
    assert results[0].script_name == "RSI Strategy"
    assert results[0].author == "trader_joe"
    assert results[0].agree_count == 42
    assert results[0].version == "1.0"


@pytest.mark.asyncio
async def test_fetch_indicators_skips_malformed_entries_without_raising() -> None:
    """A malformed entry must not abort parsing of the rest of the result set."""
    payload = {
        "results": [
            # Matches the query and has minimal-but-valid fields → defaults fill the rest.
            {"scriptName": "RSI Pro", "author": {"username": "rsi_master"}},
            # Missing scriptName entirely → skipped.
            {"author": {"username": "no_name"}},
            # author is the wrong type → username cannot be resolved → skipped.
            {"scriptName": "RSI Lite", "author": "not-a-dict"},
            # Not a dict at all → skipped.
            None,
            # Fully valid entry.
            {
                "scriptName": "RSI Full",
                "imageUrl": "img.png",
                "author": {"username": "full"},
                "agreeCount": 5,
                "isRecommended": False,
                "scriptIdPart": "PUB;full",
            },
        ]
    }
    with patch(_CLIENT_PATH, return_value=_mock_httpx_client(payload)):
        results = await fetch_tradingview_indicators("rsi")

    assert {r.script_name for r in results} == {"RSI Pro", "RSI Full"}
    # Defaults are applied for the minimal entry rather than raising.
    pro = next(r for r in results if r.script_name == "RSI Pro")
    assert pro.image_url == ""
    assert pro.agree_count == 0
    assert pro.version is None


@pytest.mark.asyncio
async def test_fetch_indicators_handles_non_dict_payload() -> None:
    """A non-dict JSON payload yields an empty list, not an AttributeError."""
    with patch(_CLIENT_PATH, return_value=_mock_httpx_client(["unexpected", "list"])):
        results = await fetch_tradingview_indicators("rsi")
    assert results == []


@pytest.mark.asyncio
async def test_fetch_indicators_handles_json_decode_error() -> None:
    """A JSON decode failure is caught and returns an empty list."""
    response = MagicMock()
    response.raise_for_status = MagicMock(return_value=None)
    response.json = MagicMock(side_effect=ValueError("Expecting value"))

    client = AsyncMock()
    client.get = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(_CLIENT_PATH, return_value=ctx):
        results = await fetch_tradingview_indicators("rsi")
    assert results == []
