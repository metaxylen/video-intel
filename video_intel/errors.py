"""Stable, machine-readable acquisition failures."""

from __future__ import annotations

import re
import time


class VideoIntelError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _error_text(exc):
    # IDs and URLs are context, never HTTP statuses (even /429 or ID=401).
    text = re.sub(r"(?im)^\s*(?:ERROR:\s*)?\[[^\]]+\]\s+[^\s:]+:\s*", "", str(exc))
    return re.sub(r"https?://\S+", "", text).lower()


def _has_status(text, *codes):
    return any(re.search(rf"\b{code}\b", text) for code in codes)


def map_error(exc: Exception, *, cookies=None) -> VideoIntelError:
    if isinstance(exc, VideoIntelError):
        return exc
    message = str(exc)
    text = _error_text(exc)
    if "private video" in text or "video is private" in text:
        code = "LOGIN_REQUIRED" if cookies else "UNAVAILABLE"
    elif any(s in text for s in ("not available in your country", "not available from your location",
                                 "geo-restricted", "geographic restriction", "blocked in your country")):
        code = "UNAVAILABLE"
    elif "blocked" in text:
        code = "BLOCKED"
        message += "; try --cookies-from-browser with user permission or another network"
    elif any(s in text for s in (
        "sign in", "sign-in", "log in", "log-in", "logged in", "login", "authentication", "cookies",
        "registered users", "account is required", "members-only", "age-restricted", "confirm you're not a bot",
    )) or _has_status(text, 401):
        code = "LOGIN_REQUIRED"
    elif _has_status(text, 429) or any(s in text for s in ("too many requests", "rate limit", "rate-limit")):
        code = "RATE_LIMITED"
    elif any(s in text for s in ("no transcript", "no subtitles", "captions are disabled")):
        code = "NO_TRANSCRIPT"
    else:
        code = "UNAVAILABLE"
    return VideoIntelError(code, message or type(exc).__name__)


def is_network_error(exc: Exception) -> bool:
    if map_error(exc).code in ("LOGIN_REQUIRED", "BLOCKED"):
        return False
    text = _error_text(exc)
    return _has_status(text, 429, 502, 503, 504) or any(s in text for s in (
        "timed out", "timeout", "connection", "network", "temporary failure", "name resolution",
        "too many requests", "rate limit", "rate-limit",
    ))


def with_retry(operation, *, sleep_fn=None, attempts=3, cookies=None):
    """Use the existing transcript path's three attempts and 1s/2s backoff."""
    sleep_fn = sleep_fn or time.sleep
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            if attempt + 1 == attempts or not is_network_error(exc):
                raise map_error(exc, cookies=cookies) from exc
            sleep_fn(2 ** attempt)
