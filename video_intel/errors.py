"""Stable, machine-readable acquisition failures."""

from __future__ import annotations

import time


class VideoIntelError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def map_error(exc: Exception) -> VideoIntelError:
    if isinstance(exc, VideoIntelError):
        return exc
    message = str(exc)
    text = message.lower()
    if any(s in text for s in ("429", "too many requests", "rate limit", "rate-limit")):
        code = "RATE_LIMITED"
    elif any(s in text for s in (
        "sign in", "sign-in", "log in", "log-in", "logged in", "login", "authentication", "cookies",
        "registered users", "account is required",
        "members-only", "age-restricted", "confirm you're not a bot", "401",
    )):
        code = "LOGIN_REQUIRED"
    elif any(s in text for s in ("no transcript", "no subtitles", "captions are disabled")):
        code = "NO_TRANSCRIPT"
    else:
        code = "UNAVAILABLE"
    return VideoIntelError(code, message or type(exc).__name__)


def is_network_error(exc: Exception) -> bool:
    return any(s in str(exc).lower() for s in (
        "timed out", "timeout", "connection", "network", "temporary failure",
        "name resolution", "429", "too many requests", "rate limit", "rate-limit",
        "502", "503", "504",
    ))


def with_retry(operation, *, sleep_fn=None, attempts=3):
    """Use the existing transcript path's three attempts and 1s/2s backoff."""
    sleep_fn = sleep_fn or time.sleep
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            if attempt + 1 == attempts or not is_network_error(exc):
                raise map_error(exc) from exc
            sleep_fn(2 ** attempt)
