"""
Exponential backoff utility for WebSocket reconnection.

This module provides a pure, stateless function for calculating retry delays
using exponential backoff with optional additive jitter. It has no I/O
dependencies and can be used by any component that needs retry delay logic.
"""

import random


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_range: float = 0.0,
) -> float:
    """
    Calculate exponential backoff delay for a given retry attempt.

    The base delay doubles with each attempt, capped at ``max_delay``. An
    optional additive jitter can be applied to distribute reconnection
    attempts across time when multiple clients experience simultaneous
    failures.

    Jitter is applied **after** exponential growth and **before** the final
    clamp. Both clamp operations are required: the first caps exponential
    growth; the second ensures jitter cannot push the final delay past
    ``max_delay``.

    Args:
        attempt: 1-based attempt index. Attempt 1 returns ``base_delay``,
            attempt 2 returns ``base_delay * 2``, and so on. Must be >= 1.
        base_delay: Base delay in seconds. The delay doubles each attempt
            starting from this value. Must be > 0.
        max_delay: Maximum delay cap in seconds. Applied before and after
            jitter to guarantee the final delay never exceeds this value.
            Must be > 0.
        jitter_range: Upper bound of additive random jitter in seconds.
            A uniform random value in ``[0, jitter_range]`` is added to
            the capped delay. Set to ``0.0`` (default) to disable jitter.
            Must be >= 0.

    Returns:
        Delay in seconds to wait before the given attempt.

    Raises:
        ValueError: If ``attempt`` is less than 1.
        ValueError: If ``base_delay`` is <= 0.
        ValueError: If ``max_delay`` is <= 0.
        ValueError: If ``jitter_range`` is < 0.

    Example:
        >>> calculate_backoff_delay(1)
        1.0
        >>> calculate_backoff_delay(2)
        2.0
        >>> calculate_backoff_delay(3)
        4.0
        >>> calculate_backoff_delay(6)  # capped at max_delay=30
        30.0
        >>> # With custom base and cap
        >>> calculate_backoff_delay(1, base_delay=2.0, max_delay=60.0)
        2.0
        >>> # With jitter — result varies but never exceeds max_delay
        >>> delay = calculate_backoff_delay(3, jitter_range=1.0)
        >>> assert 4.0 <= delay <= 5.0  # base=4.0, jitter in [0, 1.0]
    """
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    if base_delay <= 0:
        raise ValueError(f"base_delay must be > 0, got {base_delay}")
    if max_delay <= 0:
        raise ValueError(f"max_delay must be > 0, got {max_delay}")
    if jitter_range < 0:
        raise ValueError(f"jitter_range must be >= 0, got {jitter_range}")

    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    if jitter_range > 0:
        delay = min(delay + random.uniform(0, jitter_range), max_delay)
    return delay
