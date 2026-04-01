"""TradingView homepage bootstrap parser for tvkit.auth."""

import json
import logging
import re
from typing import Any

from tvkit.auth.exceptions import ProfileFetchError

__all__ = ["ProfileParser"]

logger: logging.Logger = logging.getLogger(__name__)

# Sentinel for "not yet found" — distinguishes "found null" from "not found".
_NOT_FOUND: object = object()

# Known TradingView bootstrap container markers for Strategy 3.
BOOTSTRAP_CONTAINERS: list[str] = [
    "window.__TV_DATA__ = ",
    "window.initData = ",
]

# Compiled patterns for HTML script block extraction.
_SCRIPT_RE: re.Pattern[str] = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_JSON_SCRIPT_RE: re.Pattern[str] = re.compile(
    r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# Strategy 0: TradingView embeds the full user object as a JS variable assignment.
# e.g.  var user = {"id":123,"username":"alice",...,"auth_token":"eyJ..."};
_VAR_USER_RE: re.Pattern[str] = re.compile(r"var\s+user\s*=\s*(\{)", re.DOTALL)


class ProfileParser:
    """
    Extracts the TradingView user profile dict from homepage HTML.

    Uses a 4-step fallback strategy to remain resilient across TradingView
    frontend deployments that restructure the bootstrap script layout:

    0. **Strategy 0** — JavaScript variable assignment ``var user = {...}``.
       TradingView's current frontend embeds the full authenticated user object
       (including ``auth_token``) as a plain JS variable in an inline script.
    1. **Strategy 1** — Balanced-brace extraction directly from ``"user":{``.
    2. **Strategy 2** — Scan ``<script>`` blocks for one containing
       ``"auth_token"``, then extract ``"user":{`` within it.
    3. **Strategy 3** — Scan known bootstrap container markers
       (``window.__TV_DATA__``, ``window.initData``) and
       ``<script type="application/json">`` blocks.

    After extraction, the result is validated: it must be a non-null dict
    containing ``id`` and ``username`` fields.
    """

    @staticmethod
    def parse(html: str) -> dict[str, Any]:
        """
        Extract and validate the ``user`` profile object from TradingView homepage HTML.

        Args:
            html: Raw HTML response text from ``GET https://www.tradingview.com/``.

        Returns:
            Parsed ``user`` profile dict containing at minimum ``id``, ``username``,
            ``auth_token``, ``pro_plan``, ``is_pro``, ``is_broker``, and ``badges``.

        Raises:
            ProfileFetchError: If all 3 extraction strategies fail, or if the
                extracted user object is null, empty, or missing required fields.
        """
        raw: Any = _NOT_FOUND

        # Strategy 0: var user = {...}
        # TradingView's current frontend inlines the authenticated user object as a
        # JavaScript variable assignment. This is the most reliable extraction path
        # because the block is always the session owner's full profile.
        m0 = _VAR_USER_RE.search(html)
        if m0 is not None:
            try:
                json_block = ProfileParser._balanced_brace_extract(html, m0.start(1))
                candidate = json.loads(json_block)
                if (
                    isinstance(candidate, dict)
                    and candidate.get("id")
                    and candidate.get("username")
                ):
                    raw = candidate
                    logger.debug("ProfileParser: Strategy 0 succeeded (var user = {...})")
            except (json.JSONDecodeError, ValueError):
                logger.debug("ProfileParser: Strategy 0 parse failed; falling through")

        # Strategy 1: scan all '"user":{' occurrences for one containing "auth_token"
        # The HTML may contain many user objects (feed, comment authors); only the
        # authenticated session owner's profile includes the "auth_token" field.
        s1_pos = 0
        while raw is _NOT_FOUND:
            s1_pos = html.find('"user":{', s1_pos)
            if s1_pos == -1:
                break
            try:
                json_block = ProfileParser._balanced_brace_extract(html, s1_pos + len('"user":'))
                candidate = json.loads(json_block)
                if isinstance(candidate, dict) and "auth_token" in candidate:
                    raw = candidate
            except (json.JSONDecodeError, ValueError):
                pass
            s1_pos += 1

        # Strategy 2: scan <script> blocks containing '"auth_token"'
        if raw is _NOT_FOUND:
            for script in ProfileParser._extract_script_blocks(html):
                if not script.strip():
                    continue
                if '"auth_token"' not in script:
                    continue
                s2_start = script.find('"user":{')
                if s2_start != -1:
                    try:
                        json_block = ProfileParser._balanced_brace_extract(
                            script, s2_start + len('"user":')
                        )
                        raw = json.loads(json_block)
                        break
                    except (json.JSONDecodeError, ValueError):
                        logger.debug("Strategy 2 script block parse failed; continuing scan")

        # Strategy 3a: bootstrap container markers
        if raw is _NOT_FOUND:
            for marker in BOOTSTRAP_CONTAINERS:
                idx = html.find(marker)
                if idx != -1:
                    try:
                        json_block = ProfileParser._balanced_brace_extract(html, idx + len(marker))
                        data = json.loads(json_block)
                        if isinstance(data, dict) and "user" in data:
                            raw = data["user"]
                            break
                    except (json.JSONDecodeError, ValueError):
                        logger.debug("Strategy 3a marker '%s' parse failed", marker)

        # Strategy 3b: <script type="application/json"> blocks
        if raw is _NOT_FOUND:
            for script in ProfileParser._extract_json_script_blocks(html):
                if not script.strip():
                    continue
                try:
                    data = json.loads(script)
                    if (
                        isinstance(data, dict)
                        and "user" in data
                        and isinstance(data["user"], dict)
                        and "auth_token" in data["user"]
                    ):
                        raw = data["user"]
                        break
                except json.JSONDecodeError:
                    logger.debug("Strategy 3b JSON script block parse failed; continuing")

        if raw is _NOT_FOUND:
            raise ProfileFetchError(
                "Failed to extract user profile from TradingView homepage — "
                "all 3 parsing strategies failed. This usually means TradingView "
                "has restructured its frontend. A parser update may be required."
            )

        return ProfileParser._validate(raw)

    @staticmethod
    def _validate(user: Any) -> dict[str, Any]:
        """
        Validate that the extracted user object is a usable profile dict.

        Args:
            user: The raw value extracted from the ``"user"`` key.

        Returns:
            The validated profile dict.

        Raises:
            ProfileFetchError: If the user object is null, not a dict, or missing
                required ``id`` or ``username`` fields.
        """
        if not isinstance(user, dict):
            raise ProfileFetchError(
                "user object is null or not a dict — TradingView may have returned "
                "a logged-out homepage. Check that the credentials are valid."
            )
        if not user.get("id"):
            raise ProfileFetchError(
                "user.id is missing or null in the TradingView profile payload. "
                "The page may have returned a partial bootstrap."
            )
        if not user.get("username"):
            raise ProfileFetchError(
                "user.username is missing or null in the TradingView profile payload."
            )
        return user

    @staticmethod
    def _balanced_brace_extract(text: str, start: int) -> str:
        """
        Extract a balanced JSON object ``{...}`` starting at or after ``start``.

        Walks the text character by character, tracking brace depth and string
        escape state to correctly handle nested objects and escaped quotes.

        Args:
            text: The source text to scan.
            start: Position to begin scanning for the opening ``{``.

        Returns:
            The substring from the opening ``{`` to its matching ``}``.

        Raises:
            ValueError: If no opening brace is found, or if braces are unbalanced.
        """
        i = start
        while i < len(text) and text[i] != "{":
            i += 1
        if i >= len(text):
            raise ValueError(f"No opening brace found after position {start}")

        depth = 0
        in_string = False
        escape_next = False

        for j in range(i, len(text)):
            c = text[j]
            if escape_next:
                escape_next = False
                continue
            if c == "\\" and in_string:
                escape_next = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[i : j + 1]

        raise ValueError(f"Unbalanced braces in JSON extraction starting at position {start}")

    @staticmethod
    def _extract_script_blocks(html: str) -> list[str]:
        """
        Extract the content of all ``<script>`` tags from HTML.

        Note: This also matches external script tags (``<script src="..."></script>``)
        whose content is empty. Callers must skip empty blocks with
        ``if not script.strip(): continue``.

        Args:
            html: Raw HTML text.

        Returns:
            List of script block content strings (may include empty strings).
        """
        return [m.group(1) for m in _SCRIPT_RE.finditer(html)]

    @staticmethod
    def _extract_json_script_blocks(html: str) -> list[str]:
        """
        Extract the content of ``<script type="application/json">`` tags from HTML.

        Args:
            html: Raw HTML text.

        Returns:
            List of JSON script block content strings.
        """
        return [m.group(1) for m in _JSON_SCRIPT_RE.finditer(html)]
