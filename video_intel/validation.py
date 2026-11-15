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


# Reject unsupported schema additions rather than silently accepting invalid data.
SCHEMA_KEYWORDS = frozenset({
    "$schema", "title", "description", "type", "required", "properties", "items",
    "const", "enum", "minimum", "maximum", "minLength", "maxLength", "x-maxWords",
    "pattern", "format", "minItems", "additionalProperties",
})


def validate_schema_definition(schema):
    unknown = set(schema) - SCHEMA_KEYWORDS
    if unknown:
        raise ValueError(f"Unsupported JSON Schema keywords: {sorted(unknown)}")
    if schema.get("format") not in (None, "uri", "date"):
        raise ValueError(f"Unsupported JSON Schema format: {schema['format']}")
    if "additionalProperties" in schema and schema["additionalProperties"] is not True:
        raise ValueError("Unsupported JSON Schema additionalProperties constraint")
    for child in schema.get("properties", {}).values():
        validate_schema_definition(child)
    if "items" in schema:
        validate_schema_definition(schema["items"])


def validate_timestamps(value, duration, path="analysis.lenses"):
    errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in ("t", "t_start", "t_end") and type(child) in (int, float) and child > duration:
                errors.append(f"{child_path}: timestamp exceeds video.duration {duration}")
            errors.extend(validate_timestamps(child, duration, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(validate_timestamps(child, duration, f"{path}[{index}]"))
    return errors


def validate_schema(data, name):
    schema = json.loads(files("video_intel").joinpath(f"schema/{name}.schema.json").read_text(encoding="utf-8"))
    validate_schema_definition(schema)
    errors = []

    def matches(value, kind):
        return {
            "object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "null": value is None,
            "integer": type(value) is int,
            "boolean": type(value) is bool,
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
            if len(value) < rule.get("minItems", 0):
                errors.append(f"{path}: at least {rule['minItems']} items required")
            for index, child in enumerate(value):
                check(child, rule.get("items", {}), f"{path}[{index}]")

    check(data, schema, name)
    if errors:
        raise ValidationError(errors)


def validate_analysis(analysis: dict) -> None:
    validate_schema(analysis, "analysis")
    actions = analysis["lenses"].get("actions", [])
    ids = [item["id"] for item in actions]
    errors = []
    claims = [item["id"] for item in analysis["lenses"].get("claims", [])]
    if len(claims) != len(set(claims)):
        errors.append("analysis.lenses.claims: duplicate ids")
    duration = analysis["video"].get("duration")
    if duration is not None:
        errors.extend(validate_timestamps(analysis["lenses"], duration))
    if len(ids) != len(set(ids)):
        errors.append("analysis.lenses.actions: duplicate ids")
    dependencies = {item["id"]: item["depends_on"] for item in actions}
    for item in actions:
        seen = {item["id"]}
        parent = item["depends_on"]
        while parent is not None:
            if parent not in dependencies or parent in seen:
                errors.append(f"analysis.lenses.actions.{item['id']}: invalid or cyclic depends_on")
                break
            seen.add(parent)
            parent = dependencies[parent]
    if errors:
        raise ValidationError(errors)


def validate_compare(data):
    validate_schema(data, "compare")
    ids = [video["id"] for video in data["videos"]]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("compare.videos: duplicate ids")
    for group, key in (("common_claims", "videos"), ("contradictions", "positions"),
                       ("who_says_what", "stances"), ("unique_points", None)):
        for item in data[group]:
            refs = item[key] if key else [item]
            for ref in refs:
                if ref["id"] not in ids:
                    errors.append(f"compare.{group}: unknown video id {ref['id']}")
            if key == "stances" and sorted(ref["id"] for ref in refs) != sorted(ids):
                errors.append("compare.who_says_what: each video must have exactly one stance")
    if errors:
        raise ValidationError(errors)
