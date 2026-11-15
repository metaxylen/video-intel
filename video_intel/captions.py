"""Parse yt-dlp's VTT and YouTube srv3 subtitle payloads without dependencies."""

from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_text(text: str) -> str:
    parser = _PlainText()
    parser.feed(re.sub(r"<\d{2}:\d{2}(?::\d{2})?\.\d{3}>", "", text))
    return " ".join("".join(parser.parts).split())


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) not in (2, 3):
        raise ValueError("invalid caption timestamp")
    result = 0.0
    for part in parts:
        result = result * 60 + float(part)
    if not math.isfinite(result) or result < 0:
        raise ValueError("invalid caption timestamp")
    return result


def parse_vtt(payload: str) -> list[dict]:
    segments = []
    payload = payload.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    previous_lines, previous_end = [], -1.0
    for block in re.split(r"\n\s*\n", payload):
        lines = block.strip().splitlines()
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        for index, line in enumerate(lines):
            if "-->" not in line:
                continue
            start, end = line.split("-->", 1)
            try:
                start = _seconds(start.strip())
                end = _seconds(end.strip().split()[0])
            except (ValueError, IndexError):
                break
            cue_lines = [clean_text(value) for value in lines[index + 1:]]
            cue_lines = [value for value in cue_lines if value]
            if end >= start:
                fresh = cue_lines
                if start <= previous_end + 0.02:
                    for overlap in range(min(len(previous_lines), len(cue_lines)), 0, -1):
                        if previous_lines[-overlap:] == cue_lines[:overlap]:
                            fresh = cue_lines[overlap:]
                            break
                text = " ".join(fresh)
                if text:
                    segments.append({"start": start, "end": end, "text": text})
                previous_lines, previous_end = cue_lines, end
            break
    return segments


def parse_srv3(payload: str) -> list[dict]:
    root = ET.fromstring(payload)
    segments = []
    for node in root.iter("p"):
        start = float(node.get("t", "0")) / 1000
        end = start + float(node.get("d", "0")) / 1000
        text = " ".join(html.unescape("".join(node.itertext())).split())
        if text and math.isfinite(start) and math.isfinite(end) and 0 <= start <= end:
            segments.append({"start": start, "end": end, "text": text})
    return segments
