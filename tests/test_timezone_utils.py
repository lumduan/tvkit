"""
Tests for tvkit.time — UTC timezone utilities.

Covers:
- tvkit/time/conversion.py  (to_utc, ensure_utc, convert_timestamp, convert_to_timezone)
- tvkit/time/exchange.py    (exchange_timezone, register_exchange, supported_exchanges,
                             exchange_timezone_map, validate_exchange_registry)
- tvkit/time/__init__.py    (convert_to_exchange_timezone)

Coverage target: 100% for all tvkit/time/ modules.
"""

import importlib
import sys
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl
import pytest

import tvkit.time.exchange as _exchange_module
from tvkit.time import (
    convert_timestamp,
    convert_to_exchange_timezone,
    convert_to_timezone,
    ensure_utc,
    exchange_timezone,
    exchange_timezone_map,
    load_exchange_overrides,
    register_exchange,
    supported_exchanges,
    to_utc,
    validate_exchange_registry,
)
from tvkit.time.exchange import _EXCHANGE_TIMEZONES

# ── Constants ─────────────────────────────────────────────────────────────────

# Fixed deterministic timestamp used across tests.
# datetime.fromtimestamp(1_700_000_000, UTC) == 2023-11-14 22:13:20+00:00
_ANCHOR_TS: float = 1_700_000_000.0

# ── Helpers ───────────────────────────────────────────────────────────────────


def _first_dt(df: pl.DataFrame, column: str = "timestamp") -> datetime:
    """Return the first value of a tz-aware datetime column, asserting it is not None."""
    val = df[column][0]
    assert val is not None
    return val  # type: ignore[return-value]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def clean_exchange_registry():
    """
    Isolate module-level exchange registry state between tests.

    Removes any test-registered exchange codes and clears the warned-exchanges
    set after each test that uses this fixture.
    """
    registered_before = set(_exchange_module._USER_EXCHANGE_TIMEZONES.keys())
    warned_before = set(_exchange_module._WARNED_EXCHANGES)
    yield
    added_keys = set(_exchange_module._USER_EXCHANGE_TIMEZONES.keys()) - registered_before
    for key in added_keys:
        del _exchange_module._USER_EXCHANGE_TIMEZONES[key]
    _exchange_module._WARNED_EXCHANGES.clear()
    _exchange_module._WARNED_EXCHANGES.update(warned_before)


# ── TestToUtc ─────────────────────────────────────────────────────────────────


class TestToUtc:
    """Tests for to_utc() — UTC normalization from any datetime."""

    def test_naive_datetime_returns_utc_and_warns(self) -> None:
        naive = datetime(2024, 1, 1, 9, 30)
        with pytest.warns(UserWarning):
            result = to_utc(naive)
        assert result.tzinfo is not None
        assert result.utcoffset() == timedelta(0)

    def test_naive_datetime_warning_contains_assumed_utc(self) -> None:
        naive = datetime(2024, 6, 15, 12, 0, 0)
        with pytest.warns(UserWarning, match=r"assumed UTC"):
            to_utc(naive)

    def test_already_utc_passthrough(self) -> None:
        utc_dt = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
        result = to_utc(utc_dt)
        assert result == utc_dt
        assert result.utcoffset() == timedelta(0)

    def test_tz_aware_non_utc_converts_silently(self) -> None:
        bangkok = ZoneInfo("Asia/Bangkok")
        bkk_dt = datetime(2024, 1, 1, 16, 30, tzinfo=bangkok)  # +07:00
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning → failure
            result = to_utc(bkk_dt)
        assert result.utcoffset() == timedelta(0)

    def test_tz_aware_non_utc_value_is_correct(self) -> None:
        bangkok = ZoneInfo("Asia/Bangkok")
        # 16:30 Bangkok (+07:00) = 09:30 UTC
        bkk_dt = datetime(2024, 1, 1, 16, 30, tzinfo=bangkok)
        result = to_utc(bkk_dt)
        assert result.hour == 9
        assert result.minute == 30

    def test_non_datetime_raises_type_error_int(self) -> None:
        with pytest.raises(TypeError):
            to_utc(1_700_000_000)  # type: ignore[arg-type]

    def test_non_datetime_raises_type_error_str(self) -> None:
        with pytest.raises(TypeError):
            to_utc("2024-01-01")  # type: ignore[arg-type]

    def test_non_datetime_raises_type_error_none(self) -> None:
        with pytest.raises(TypeError):
            to_utc(None)  # type: ignore[arg-type]

    def test_type_error_message_contains_type_name(self) -> None:
        with pytest.raises(TypeError, match="int"):
            to_utc(42)  # type: ignore[arg-type]


# ── TestEnsureUtc ─────────────────────────────────────────────────────────────


class TestEnsureUtc:
    """Tests for ensure_utc() — semantic alias for to_utc()."""

    def test_ensure_utc_is_alias_for_to_utc(self) -> None:
        utc_dt = datetime(2024, 3, 15, 10, 0, tzinfo=UTC)
        assert ensure_utc(utc_dt) == to_utc(utc_dt)

    def test_ensure_utc_naive_warns(self) -> None:
        naive = datetime(2024, 1, 1)
        with pytest.warns(UserWarning):
            result = ensure_utc(naive)
        assert result.utcoffset() == timedelta(0)

    def test_ensure_utc_aware_converts(self) -> None:
        ny = ZoneInfo("America/New_York")
        # 12:00 New York EST (-05:00) = 17:00 UTC
        ny_dt = datetime(2024, 1, 15, 12, 0, tzinfo=ny)
        result = ensure_utc(ny_dt)
        assert result.hour == 17
        assert result.utcoffset() == timedelta(0)


# ── TestConvertTimestamp ──────────────────────────────────────────────────────


class TestConvertTimestamp:
    """Tests for convert_timestamp() — UTC epoch float → tz-aware datetime.

    Anchor timestamp: 1_700_000_000 == 2023-11-14 22:13:20 UTC
    """

    @pytest.mark.parametrize(
        "tz,expected_offset_hours",
        [
            ("Asia/Bangkok", 7),
            ("America/New_York", -5),  # November: EST
            ("Europe/London", 0),  # November: GMT
            ("America/Los_Angeles", -8),  # November: PST
            ("UTC", 0),
        ],
    )
    def test_utc_epoch_to_timezone(self, tz: str, expected_offset_hours: int) -> None:
        result = convert_timestamp(_ANCHOR_TS, tz)
        assert result.utcoffset() == timedelta(hours=expected_offset_hours)

    def test_utc_epoch_to_bangkok_exact_value(self) -> None:
        result = convert_timestamp(_ANCHOR_TS, "Asia/Bangkok")
        # 2023-11-14 22:13:20 UTC = 2023-11-15 05:13:20+07:00
        assert result.day == 15
        assert result.hour == 5

    def test_utc_epoch_to_new_york_exact_value(self) -> None:
        result = convert_timestamp(_ANCHOR_TS, "America/New_York")
        # 2023-11-14 22:13:20 UTC = 2023-11-14 17:13:20-05:00 (EST)
        assert result.day == 14
        assert result.hour == 17

    def test_utc_epoch_to_los_angeles_exact_value(self) -> None:
        result = convert_timestamp(_ANCHOR_TS, "America/Los_Angeles")
        # 2023-11-14 22:13:20 UTC = 2023-11-14 14:13:20-08:00 (PST)
        assert result.day == 14
        assert result.hour == 14

    def test_fractional_epoch_supported(self) -> None:
        # Guards against silent truncation: int(ts) before fromtimestamp would lose .5s
        result = convert_timestamp(_ANCHOR_TS + 0.5, "UTC")
        assert result.microsecond == 500_000

    def test_negative_epoch_supported(self) -> None:
        # Unix timestamps before 1970-01-01 must be handled correctly
        result = convert_timestamp(-1.0, "UTC")
        assert result.year == 1969
        assert result.month == 12
        assert result.day == 31

    def test_dst_spring_forward_new_york_before(self) -> None:
        # 2024-03-10 06:59 UTC = 01:59 AM EST (before spring-forward at 07:00 UTC)
        result = convert_timestamp(1710053940, "America/New_York")
        assert result.utcoffset() == timedelta(hours=-5)  # EST

    def test_dst_spring_forward_new_york_after(self) -> None:
        # 2024-03-10 07:01 UTC = 03:01 AM EDT (after spring-forward)
        result = convert_timestamp(1710054060, "America/New_York")
        assert result.utcoffset() == timedelta(hours=-4)  # EDT

    def test_dst_fall_back_new_york_before(self) -> None:
        # 2024-11-03 05:59 UTC = 01:59 AM EDT (before fall-back at 06:00 UTC)
        result = convert_timestamp(1730609940, "America/New_York")
        assert result.utcoffset() == timedelta(hours=-4)  # EDT

    def test_dst_fall_back_new_york_after(self) -> None:
        # 2024-11-03 06:01 UTC = 01:01 AM EST (after fall-back)
        result = convert_timestamp(1730613660, "America/New_York")
        assert result.utcoffset() == timedelta(hours=-5)  # EST

    def test_invalid_iana_tz_raises(self) -> None:
        with pytest.raises(ZoneInfoNotFoundError):
            convert_timestamp(_ANCHOR_TS, "Not/ATimezone")


# ── TestConvertToTimezone ─────────────────────────────────────────────────────


class TestConvertToTimezone:
    """Tests for convert_to_timezone() — epoch column in Polars DataFrame → tz-aware datetime."""

    @pytest.fixture
    def df_seconds(self) -> pl.DataFrame:
        return pl.DataFrame({"timestamp": [int(_ANCHOR_TS), int(_ANCHOR_TS) + 3600]})

    @pytest.fixture
    def df_milliseconds(self) -> pl.DataFrame:
        return pl.DataFrame(
            {"timestamp": [int(_ANCHOR_TS) * 1000, (int(_ANCHOR_TS) + 3600) * 1000]}
        )

    def test_dataframe_timestamp_column_converted(self, df_seconds: pl.DataFrame) -> None:
        result = convert_to_timezone(df_seconds, "Asia/Bangkok")
        assert isinstance(result["timestamp"].dtype, pl.Datetime)

    def test_custom_column_name(self) -> None:
        df = pl.DataFrame({"time": [int(_ANCHOR_TS)]})
        result = convert_to_timezone(df, "UTC", column="time")
        assert "time" in result.columns
        assert isinstance(result["time"].dtype, pl.Datetime)

    def test_original_dataframe_not_mutated(self, df_seconds: pl.DataFrame) -> None:
        original_dtype = df_seconds["timestamp"].dtype
        convert_to_timezone(df_seconds, "Asia/Bangkok")
        # Input DataFrame must be unchanged (Polars with_columns immutability)
        assert df_seconds["timestamp"].dtype == original_dtype

    def test_invalid_iana_tz_raises(self, df_seconds: pl.DataFrame) -> None:
        with pytest.raises(pl.exceptions.ComputeError):
            convert_to_timezone(df_seconds, "Not/ATimezone")

    def test_missing_column_raises(self, df_seconds: pl.DataFrame) -> None:
        with pytest.raises(pl.exceptions.ColumnNotFoundError):
            convert_to_timezone(df_seconds, "UTC", column="nonexistent")

    def test_millisecond_unit(self, df_milliseconds: pl.DataFrame) -> None:
        result = convert_to_timezone(df_milliseconds, "UTC", unit="ms")
        assert isinstance(result["timestamp"].dtype, pl.Datetime)
        first = _first_dt(result)
        # 1_700_000_000_000 ms = 2023-11-14 22:13:20 UTC
        assert first.year == 2023
        assert first.month == 11
        assert first.day == 14
        assert first.hour == 22

    def test_value_roundtrip_bangkok(self, df_seconds: pl.DataFrame) -> None:
        result = convert_to_timezone(df_seconds, "Asia/Bangkok")
        first = _first_dt(result)
        # 2023-11-14 22:13:20 UTC = 2023-11-15 05:13:20+07:00
        assert first.day == 15
        assert first.hour == 5

    def test_empty_dataframe(self) -> None:
        df_empty = pl.DataFrame({"timestamp": pl.Series([], dtype=pl.Int64)})
        result = convert_to_timezone(df_empty, "Asia/Bangkok")
        assert len(result) == 0
        assert isinstance(result["timestamp"].dtype, pl.Datetime)

    def test_float_epoch_column(self) -> None:
        # Some data providers supply float epochs; Polars from_epoch accepts Float64
        df = pl.DataFrame({"timestamp": [_ANCHOR_TS]})
        result = convert_to_timezone(df, "UTC")
        assert isinstance(result["timestamp"].dtype, pl.Datetime)

    def test_idempotency_data_corruption(self, df_seconds: pl.DataFrame) -> None:
        """
        Calling convert_to_timezone on an already-converted Datetime column silently
        corrupts data rather than raising. Polars treats the Datetime column's internal
        microsecond integer as a raw epoch value, producing timestamps so far in the future
        they overflow Python's datetime range (OverflowError on value access).

        API contract: convert_to_timezone expects an integer/float epoch column.
        Never call it twice on the same column.
        """
        converted = convert_to_timezone(df_seconds, "Asia/Bangkok")
        corrupted = convert_to_timezone(converted, "Asia/Bangkok")
        # The second conversion succeeds at the Polars level but the stored value
        # is out of Python's representable datetime range
        with pytest.raises(OverflowError):
            _ = corrupted["timestamp"][0]


# ── TestExchangeTimezone ──────────────────────────────────────────────────────


class TestExchangeTimezone:
    """Tests for exchange_timezone() — exchange code → IANA timezone string."""

    @pytest.mark.parametrize("exchange", list(_EXCHANGE_TIMEZONES.keys()))
    def test_all_known_exchanges_return_valid_iana(self, exchange: str) -> None:
        tz = exchange_timezone(exchange)
        # ZoneInfo raises ZoneInfoNotFoundError if the string is not a valid IANA tz
        ZoneInfo(tz)

    def test_nasdaq(self) -> None:
        assert exchange_timezone("NASDAQ") == "America/New_York"

    def test_set(self) -> None:
        assert exchange_timezone("SET") == "Asia/Bangkok"

    def test_lse(self) -> None:
        assert exchange_timezone("LSE") == "Europe/London"

    def test_case_insensitive_lowercase(self) -> None:
        assert exchange_timezone("nasdaq") == exchange_timezone("NASDAQ")

    def test_case_insensitive_mixed(self) -> None:
        assert exchange_timezone("Nasdaq") == exchange_timezone("NASDAQ")

    @pytest.mark.parametrize("symbol", ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:TSLA"])
    def test_symbol_string_parametrized(self, symbol: str) -> None:
        assert exchange_timezone(symbol) == "America/New_York"

    def test_exchange_code_whitespace_stripped(self) -> None:
        assert exchange_timezone(" NASDAQ ") == "America/New_York"

    def test_unknown_exchange_returns_utc(self, clean_exchange_registry: None) -> None:
        assert exchange_timezone("COMPLETELY_UNKNOWN_XYZ") == "UTC"

    def test_unknown_exchange_logs_warning(
        self, caplog: pytest.LogCaptureFixture, clean_exchange_registry: None
    ) -> None:
        import logging

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="tvkit.time.exchange"):
            exchange_timezone("UNKNOWN_EXCHANGE_LOG_TEST")
        assert any("UNKNOWN_EXCHANGE_LOG_TEST" in rec.message for rec in caplog.records)

    def test_unknown_exchange_warning_logged_once(
        self, caplog: pytest.LogCaptureFixture, clean_exchange_registry: None
    ) -> None:
        """
        Calling exchange_timezone() for an unknown exchange multiple times logs
        only one WARNING — prevents log spam when processing millions of bars on
        an unsupported exchange.
        """
        import logging

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="tvkit.time.exchange"):
            exchange_timezone("SPAMMY_UNKNOWN_EXCHANGE")
            exchange_timezone("SPAMMY_UNKNOWN_EXCHANGE")
            exchange_timezone("SPAMMY_UNKNOWN_EXCHANGE")
        matching = [r for r in caplog.records if "SPAMMY_UNKNOWN_EXCHANGE" in r.message]
        assert len(matching) == 1


# ── TestRegisterExchange ──────────────────────────────────────────────────────


class TestRegisterExchange:
    """Tests for register_exchange() — runtime extension of the exchange registry."""

    def test_register_and_lookup(self, clean_exchange_registry: None) -> None:
        register_exchange("TESTEX", "Asia/Bangkok")
        assert exchange_timezone("TESTEX") == "Asia/Bangkok"

    def test_register_takes_precedence_over_builtin(self, clean_exchange_registry: None) -> None:
        register_exchange("NASDAQ", "Asia/Tokyo")
        assert exchange_timezone("NASDAQ") == "Asia/Tokyo"

    def test_invalid_iana_tz_raises_value_error(self, clean_exchange_registry: None) -> None:
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            register_exchange("BADEX", "Not/ATimezone")

    def test_register_is_case_normalized(self, clean_exchange_registry: None) -> None:
        register_exchange("lowercase_ex", "Europe/London")
        assert exchange_timezone("LOWERCASE_EX") == "Europe/London"
        assert exchange_timezone("lowercase_ex") == "Europe/London"


# ── TestSupportedExchanges ────────────────────────────────────────────────────


class TestSupportedExchanges:
    """Tests for supported_exchanges() — set of all known exchange codes."""

    def test_returns_set(self) -> None:
        assert isinstance(supported_exchanges(), set)

    def test_includes_known_exchanges(self) -> None:
        known = supported_exchanges()
        assert "NASDAQ" in known
        assert "SET" in known
        assert "LSE" in known

    def test_includes_user_registered(self, clean_exchange_registry: None) -> None:
        register_exchange("CUSTOM_TEST_EX", "Pacific/Auckland")
        assert "CUSTOM_TEST_EX" in supported_exchanges()


# ── TestExchangeTimezoneMap ───────────────────────────────────────────────────


class TestExchangeTimezoneMap:
    """Tests for exchange_timezone_map() — full merged registry as a dict copy."""

    def test_returns_dict(self) -> None:
        assert isinstance(exchange_timezone_map(), dict)

    def test_includes_nasdaq(self) -> None:
        mapping = exchange_timezone_map()
        assert mapping["NASDAQ"] == "America/New_York"

    def test_user_overrides_shadow_builtin(self, clean_exchange_registry: None) -> None:
        register_exchange("NASDAQ", "Asia/Kolkata")
        mapping = exchange_timezone_map()
        assert mapping["NASDAQ"] == "Asia/Kolkata"

    def test_mutation_does_not_affect_registry(self) -> None:
        """
        Mutating the returned dict must not affect future lookups.

        Guards against a reference-leak bug where the implementation returns
        the internal dict directly instead of a copy:
            return _EXCHANGE_TIMEZONES          # ← bug
            return dict(_EXCHANGE_TIMEZONES)    # ← correct
        """
        mapping = exchange_timezone_map()
        mapping["NASDAQ"] = "FAKE/TIMEZONE"
        assert exchange_timezone("NASDAQ") == "America/New_York"


# ── TestValidateExchangeRegistry ──────────────────────────────────────────────


class TestValidateExchangeRegistry:
    """Tests for validate_exchange_registry() — coverage check against MARKET_INFO."""

    def test_returns_empty_set_for_full_coverage(self) -> None:
        missing = validate_exchange_registry()
        assert missing == set(), (
            f"Exchange registry is missing {len(missing)} code(s): {sorted(missing)}. "
            "Add them to tvkit/time/exchange.py or register them via register_exchange()."
        )

    def test_returns_missing_codes(self, clean_exchange_registry: None) -> None:
        """Temporarily removing a built-in entry surfaces it as missing."""
        original_tz = _EXCHANGE_TIMEZONES.pop("NASDAQ", None)
        try:
            missing = validate_exchange_registry()
            assert "NASDAQ" in missing
        finally:
            if original_tz is not None:
                _EXCHANGE_TIMEZONES["NASDAQ"] = original_tz


# ── TestConvertToExchangeTimezone ─────────────────────────────────────────────


class TestConvertToExchangeTimezone:
    """Tests for convert_to_exchange_timezone() — DataFrame conversion via exchange code."""

    @pytest.fixture
    def df(self) -> pl.DataFrame:
        return pl.DataFrame({"timestamp": [int(_ANCHOR_TS)]})

    def test_nasdaq_maps_to_new_york(self, df: pl.DataFrame) -> None:
        result = convert_to_exchange_timezone(df, "NASDAQ")
        first = _first_dt(result)
        # 2023-11-14 22:13:20 UTC = 2023-11-14 17:13:20-05:00 (EST)
        assert first.utcoffset() == timedelta(hours=-5)

    def test_set_maps_to_bangkok(self, df: pl.DataFrame) -> None:
        result = convert_to_exchange_timezone(df, "SET")
        first = _first_dt(result)
        assert first.utcoffset() == timedelta(hours=7)

    def test_binance_maps_to_utc(self, df: pl.DataFrame, clean_exchange_registry: None) -> None:
        # BINANCE is unknown → falls back to UTC
        result = convert_to_exchange_timezone(df, "BINANCE")
        first = _first_dt(result)
        assert first.utcoffset() == timedelta(0)

    @pytest.mark.parametrize("symbol", ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:TSLA"])
    def test_symbol_string_parametrized(self, df: pl.DataFrame, symbol: str) -> None:
        result = convert_to_exchange_timezone(df, symbol)
        first = _first_dt(result)
        assert first.utcoffset() == timedelta(hours=-5)

    def test_custom_column_name(self) -> None:
        df_custom = pl.DataFrame({"time": [int(_ANCHOR_TS)]})
        result = convert_to_exchange_timezone(df_custom, "SET", column="time")
        assert "time" in result.columns
        first = _first_dt(result, column="time")
        assert first.utcoffset() == timedelta(hours=7)


# ── TestLoadExchangeOverrides ─────────────────────────────────────────────────


class TestLoadExchangeOverrides:
    """Tests for load_exchange_overrides() — YAML-file-based registry extension."""

    def test_valid_yaml_loads_exchanges(
        self, tmp_path: Path, clean_exchange_registry: None
    ) -> None:
        yaml_file = tmp_path / "overrides.yaml"
        yaml_file.write_text("exchanges:\n  YAMLTEST: Asia/Bangkok\n  ANOTHER: Europe/London\n")
        load_exchange_overrides(yaml_file)
        assert exchange_timezone("YAMLTEST") == "Asia/Bangkok"
        assert exchange_timezone("ANOTHER") == "Europe/London"

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Exchange override file not found"):
            load_exchange_overrides(tmp_path / "nonexistent.yaml")

    def test_non_dict_top_level_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="expected a YAML mapping"):
            load_exchange_overrides(yaml_file)

    def test_exchanges_not_dict_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad_exchanges.yaml"
        yaml_file.write_text("exchanges:\n  - NASDAQ\n  - SET\n")
        with pytest.raises(ValueError, match="'exchanges' must be a mapping"):
            load_exchange_overrides(yaml_file)

    def test_invalid_timezone_in_yaml_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad_tz.yaml"
        yaml_file.write_text("exchanges:\n  BADTZ: Not/ATimezone\n")
        with pytest.raises(ValueError, match="Invalid IANA timezone"):
            load_exchange_overrides(yaml_file)

    def test_accepts_string_path(self, tmp_path: Path, clean_exchange_registry: None) -> None:
        yaml_file = tmp_path / "str_path.yaml"
        yaml_file.write_text("exchanges:\n  STRPATHTEST: Pacific/Auckland\n")
        load_exchange_overrides(str(yaml_file))
        assert exchange_timezone("STRPATHTEST") == "Pacific/Auckland"

    def test_missing_pyyaml_raises_import_error(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "overrides.yaml"
        yaml_file.write_text("exchanges:\n  TESTEX: UTC\n")
        with patch.dict(sys.modules, {"yaml": None}):
            with pytest.raises(ImportError, match="pyyaml"):
                load_exchange_overrides(yaml_file)


# ── TestEnvVarAutoLoad ────────────────────────────────────────────────────────


class TestEnvVarAutoLoad:
    """Tests for the TVKIT_EXCHANGE_OVERRIDES env-var auto-load at module import."""

    def test_env_var_triggers_load_on_import(
        self, tmp_path: Path, clean_exchange_registry: None
    ) -> None:
        yaml_file = tmp_path / "env_overrides.yaml"
        yaml_file.write_text("exchanges:\n  ENVTEST: Asia/Tokyo\n")
        # Reload the module with the env var pointing to the file
        with patch.dict("os.environ", {"TVKIT_EXCHANGE_OVERRIDES": str(yaml_file)}):
            import tvkit.time.exchange as exc_mod

            importlib.reload(exc_mod)
        try:
            assert exc_mod.exchange_timezone("ENVTEST") == "Asia/Tokyo"
        finally:
            # Clean up the reload side-effects on the reloaded module
            exc_mod._USER_EXCHANGE_TIMEZONES.pop("ENVTEST", None)

    def test_invalid_env_var_path_logs_warning(
        self, caplog: pytest.LogCaptureFixture, clean_exchange_registry: None
    ) -> None:
        import logging

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="tvkit.time.exchange"):
            with patch.dict("os.environ", {"TVKIT_EXCHANGE_OVERRIDES": "/nonexistent/path.yaml"}):
                import tvkit.time.exchange as exc_mod

                importlib.reload(exc_mod)
        assert any("TVKIT_EXCHANGE_OVERRIDES" in rec.message for rec in caplog.records)
