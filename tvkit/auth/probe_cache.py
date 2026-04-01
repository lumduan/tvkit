"""Optional disk cache for background capability probe results."""

import json
import logging
import os
import tempfile
import time
from pathlib import Path

__all__ = ["ProbeCache", "PROBE_CACHE_TTL"]

logger: logging.Logger = logging.getLogger(__name__)

# Default cache TTL: 1 day in seconds.
PROBE_CACHE_TTL: int = 86_400

# Default cache file location.
_CACHE_PATH: Path = Path.home() / ".cache" / "tvkit" / "capabilities.json"


class ProbeCache:
    """
    Optional disk cache for background capability probe results.

    Caches ``max_bars`` per ``user_id`` to avoid re-probing on every session
    start. A live WebSocket probe takes 3–10 seconds; the cache avoids this
    cost for users who restart tvkit frequently.

    Cache is stored at ``~/.cache/tvkit/capabilities.json`` as a JSON object
    keyed by ``user_id`` (string). Writes are atomic via temp-file rename
    (``os.replace``) — safe under concurrent processes without extra
    dependencies.

    The cache file never stores cookies, tokens, or credentials.

    Args:
        path: Override the cache file path. Defaults to
            ``~/.cache/tvkit/capabilities.json``.
        ttl: Override the cache TTL in seconds. Defaults to ``PROBE_CACHE_TTL``
            (86,400 seconds = 1 day).

    Example::

        cache = ProbeCache()
        cached = cache.load(user_id=12345)
        if cached is None:
            # run live probe ...
            cache.save(user_id=12345, max_bars=20000, plan="pro_premium")
    """

    def __init__(
        self,
        path: Path | None = None,
        ttl: int = PROBE_CACHE_TTL,
    ) -> None:
        self._path: Path = path or _CACHE_PATH
        self._ttl: int = ttl

    def load(self, user_id: int) -> int | None:
        """
        Return the cached ``max_bars`` for ``user_id`` if the entry is fresh.

        Args:
            user_id: TradingView numeric user ID (key in the cache).

        Returns:
            Cached ``max_bars`` integer if the entry exists and is younger
            than ``ttl`` seconds, otherwise ``None``.
        """
        data = self._read_cache()
        entry = data.get(str(user_id))
        if entry is None:
            logger.debug("ProbeCache: no cache entry for user_id=%d", user_id)
            return None

        ts = entry.get("timestamp", 0)
        age = time.time() - float(ts)
        if age >= self._ttl:
            logger.debug(
                "ProbeCache: stale entry for user_id=%d (age=%.0fs, ttl=%ds)",
                user_id,
                age,
                self._ttl,
            )
            return None

        max_bars: int = int(float(entry["max_bars"]))
        logger.info(
            "ProbeCache: cache hit for user_id=%d (max_bars=%d, age=%.0fs)",
            user_id,
            max_bars,
            age,
        )
        return max_bars

    def save(self, user_id: int, max_bars: int, plan: str) -> None:
        """
        Write or update the cache entry for ``user_id``.

        The write is atomic: the JSON is written to a temp file in the same
        directory, then renamed over the cache file via ``os.replace``.

        Args:
            user_id: TradingView numeric user ID.
            max_bars: Probe-confirmed maximum bars value to cache.
            plan: Raw ``pro_plan`` string (stored for observability; not used
                to determine ``max_bars`` on load).
        """
        data = self._read_cache()
        data[str(user_id)] = {
            "max_bars": max_bars,
            "plan": plan,
            "timestamp": time.time(),
        }
        self._write_cache(data)
        logger.debug(
            "ProbeCache: saved max_bars=%d for user_id=%d (plan=%r)",
            max_bars,
            user_id,
            plan,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_cache(self) -> dict[str, dict[str, float | int | str]]:
        """
        Read and return the cache file contents.

        Returns an empty dict if the file does not exist or cannot be parsed.
        """
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("ProbeCache: failed to read cache file: %s", exc)
        return {}

    def _write_cache(self, data: dict[str, dict[str, float | int | str]]) -> None:
        """
        Atomically write the cache dict to disk.

        Uses a temp file in the same directory as the cache file and
        ``os.replace`` to achieve an atomic rename, preventing partial writes.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=".tvkit-capabilities-",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                os.replace(tmp_path, self._path)
            except Exception:
                # Clean up temp file on write failure.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.warning("ProbeCache: failed to write cache file: %s", exc)
