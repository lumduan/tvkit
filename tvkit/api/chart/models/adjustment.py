"""TradingView price adjustment mode enum for OHLCV data."""

from enum import Enum


class Adjustment(str, Enum):
    """TradingView price adjustment mode for OHLCV data.

    Controls how historical prices are adjusted for corporate actions.
    Maps directly to the ``adjustment`` field in TradingView's
    ``resolve_symbol`` WebSocket message.

    Being a ``str`` subclass, each member serialises directly to its
    string value — ``Adjustment.DIVIDENDS.value == "dividends"`` — so
    it can be embedded in ``json.dumps`` calls without a custom encoder.

    Usage::

        from tvkit.api.chart import Adjustment

        bars = await client.get_historical_ohlcv(
            "SET:ADVANC", "1D", bars_count=300,
            adjustment=Adjustment.DIVIDENDS,
        )
    """

    SPLITS = "splits"
    """Split-adjusted prices only.

    Default — backwards-compatible with all calls that omit the
    ``adjustment`` parameter.  Only forward stock splits and reverse
    splits are reflected in historical prices.
    """

    DIVIDENDS = "dividends"
    """Dividend-adjusted (total-return) prices.

    Both splits and cash dividends are reflected backwards in historical
    prices.  Each dividend payment is subtracted from all prior closing
    prices so the series represents the total return of holding the stock
    continuously.  Use for accurate long-term backtesting of
    dividend-paying stocks.
    """
