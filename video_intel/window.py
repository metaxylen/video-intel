"""Focus windows use absolute source timestamps and an exclusive end."""

from __future__ import annotations

import math
import re


def parse_time(value: str) -> float:
    if not re.fullmatch(r"\d+(?::[0-5]?\d){0,2}(?:\.\d+)?", value):
        raise ValueError("Expected SS, MM:SS or HH:MM:SS (nonnegative)")
    result = 0.0
    for part in value.split(":"):
        result = result * 60 + float(part)
    if not math.isfinite(result):
        raise ValueError("Timestamp must be finite")
    return result


def focus_window(start=None, end=None):
    if start is None and end is None:
        return None
    start = 0 if start is None else start
    if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0
           for t in (start, end) if t is not None):
        raise ValueError("Window timestamps must be finite and nonnegative")
    if end is not None and end <= start:
        raise ValueError("--end must be greater than --start")
    return {"start": start, "end": end}


def clip_transcript(transcript, window):
    if window is None:
        return transcript
    segments = []
    for segment in transcript["segments"]:
        start = max(segment["start"], window["start"])
        end = segment["end"] if window["end"] is None else min(segment["end"], window["end"])
        if start < end:
            segments.append(dict(segment, start=start, end=end))
    return dict(transcript, segments=segments, window=dict(window))
