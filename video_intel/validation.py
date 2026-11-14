"""Small validator for the subset of JSON Schema used by the shipped v1 schema."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from importlib.resources import files
from urllib.parse import urlsplit


class ValidationError(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(errors))


def safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return ""


def read_json(path):
    def reject_constant(value):
        raise ValueError(f"Invalid JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def validate_analysis(analysis: dict) -> None:
    schema = json.loads(files("video_intel").joinpath("schema/analysis.schema.json").read_text(encoding="utf-8"))
    errors = []

    def matches(value, kind):
        return {
            "object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "null": value is None,
            "integer": type(value) is int,
            "number": type(value) is int or (type(value) is float and math.isfinite(value)),
        }.get(kind, False)

    def check(value, rule, path):
        kinds = rule.get("type")
        if kinds and not any(matches(value, kind) for kind in ([kinds] if isinstance(kinds, str) else kinds)):
            errors.append(f"{path}: expected {kinds}")
            return
        if "const" in rule and (type(value) is not type(rule["const"]) or value != rule["const"]):
            errors.append(f"{path}: expected {rule['const']}")
        if "enum" in rule and value not in rule["enum"]:
            errors.append(f"{path}: expected one of {rule['enum']}")
        if type(value) in (int, float):
            if type(value) is float and not math.isfinite(value):
                errors.append(f"{path}: expected a finite number")
            for key, fails in (("minimum", value < rule.get("minimum", value)),
                               ("maximum", value > rule.get("maximum", value))):
                if fails:
                    errors.append(f"{path}: violates {key} {rule[key]}")
        if isinstance(value, str):
            for key, fails in (("minLength", len(value) < rule.get("minLength", 0)),
                               ("maxLength", len(value) > rule.get("maxLength", len(value)))):
                if fails:
                    errors.append(f"{path}: violates {key} {rule[key]}")
            if "x-maxWords" in rule and len(value.split()) > rule["x-maxWords"]:
                errors.append(f"{path}: at most {rule['x-maxWords']} words allowed")
            if "pattern" in rule and not re.search(rule["pattern"], value):
                errors.append(f"{path}: does not match required pattern")
            if rule.get("format") == "uri" and not safe_url(value):
                errors.append(f"{path}: expected an HTTP(S) URL")
            if rule.get("format") == "date":
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError()
                    date.fromisoformat(value)
                except ValueError:
                    errors.append(f"{path}: expected a real YYYY-MM-DD date")
        if isinstance(value, dict):
            for key in rule.get("required", []):
                if key not in value:
                    errors.append(f"{path}.{key}: required field missing")
            for key, child in value.items():
                check(child, rule.get("properties", {}).get(key, {}), f"{path}.{key}")
        if isinstance(value, list):
            for index, child in enumerate(value):
                check(child, rule.get("items", {}), f"{path}[{index}]")

    check(analysis, schema, "analysis")
    if errors:
        raise ValidationError(errors)
