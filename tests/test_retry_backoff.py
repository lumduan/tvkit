"""
Unit tests for tvkit.api.utils.retry.calculate_backoff_delay.

Coverage target: 100% (lines and branches).
All tests are pure — no I/O, no async, no mocking required.
"""

import pytest

from tvkit.api.utils.retry import calculate_backoff_delay


class TestExponentialGrowth:
    def test_attempt_1_returns_base_delay(self) -> None:
        assert calculate_backoff_delay(1) == 1.0

    def test_exponential_growth(self) -> None:
        # Each attempt doubles: 1, 2, 4, 8, 16
        expected = [1.0, 2.0, 4.0, 8.0, 16.0]
        for attempt, exp in enumerate(expected, start=1):
            assert calculate_backoff_delay(attempt) == exp

    def test_custom_base_delay(self) -> None:
        assert calculate_backoff_delay(1, base_delay=2.0) == 2.0
        assert calculate_backoff_delay(2, base_delay=2.0) == 4.0
        assert calculate_backoff_delay(3, base_delay=2.0) == 8.0


class TestMaxDelayCap:
    def test_max_delay_cap(self) -> None:
        # Attempt 6: 1 * 2^5 = 32 > 30 — must be capped at 30
        assert calculate_backoff_delay(6) == 30.0

    def test_large_attempt_still_capped(self) -> None:
        assert calculate_backoff_delay(100) == 30.0

    def test_custom_max_delay(self) -> None:
        assert calculate_backoff_delay(10, base_delay=1.0, max_delay=5.0) == 5.0

    def test_attempt_at_cap_boundary(self) -> None:
        # Attempt 5: 1 * 2^4 = 16 — not yet capped
        assert calculate_backoff_delay(5) == 16.0
        # Attempt 6: 1 * 2^5 = 32 — capped at 30
        assert calculate_backoff_delay(6) == 30.0

    def test_max_delay_less_than_base_delay(self) -> None:
        # base_delay=10, max_delay=5 — attempt 1 is immediately clamped to 5
        assert calculate_backoff_delay(1, base_delay=10.0, max_delay=5.0) == 5.0


class TestJitter:
    def test_zero_jitter_is_deterministic(self) -> None:
        result1 = calculate_backoff_delay(3, jitter_range=0.0)
        result2 = calculate_backoff_delay(3, jitter_range=0.0)
        assert result1 == result2 == 4.0

    def test_jitter_within_range(self) -> None:
        # attempt=3, base=1 → computed=4.0; jitter in [0, 1.0] → result in [4.0, 5.0]
        for _ in range(50):
            delay = calculate_backoff_delay(3, base_delay=1.0, max_delay=30.0, jitter_range=1.0)
            assert 4.0 <= delay <= 5.0

    def test_jitter_clamped_to_max(self) -> None:
        # attempt=6 is already at max_delay=30; jitter_range=10 must not push past 30
        for _ in range(50):
            delay = calculate_backoff_delay(6, base_delay=1.0, max_delay=30.0, jitter_range=10.0)
            assert delay <= 30.0

    def test_jitter_result_at_least_base_computed(self) -> None:
        # Jitter is purely additive — result must be >= the pre-jitter computed delay
        for _ in range(50):
            delay = calculate_backoff_delay(2, base_delay=1.0, max_delay=30.0, jitter_range=2.0)
            assert delay >= 2.0


class TestInputValidation:
    def test_attempt_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            calculate_backoff_delay(0)

    def test_attempt_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            calculate_backoff_delay(-1)

    def test_base_delay_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="base_delay must be > 0"):
            calculate_backoff_delay(1, base_delay=0.0)

    def test_base_delay_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="base_delay must be > 0"):
            calculate_backoff_delay(1, base_delay=-1.0)

    def test_max_delay_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="max_delay must be > 0"):
            calculate_backoff_delay(1, max_delay=0.0)

    def test_max_delay_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="max_delay must be > 0"):
            calculate_backoff_delay(1, max_delay=-5.0)

    def test_jitter_range_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="jitter_range must be >= 0"):
            calculate_backoff_delay(1, jitter_range=-0.5)
