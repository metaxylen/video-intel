"""Offline dependency and output-directory diagnostics; never downloads models."""

from __future__ import annotations

import importlib
import os
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path

from video_intel.acquisition import ASR_MODEL


def diagnose(output_dir=None):
    checks = []

    def add(name, ok, detail, fix):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail), "fix": "" if ok else fix})

    try:
        value = version("yt-dlp")
        importlib.import_module("yt_dlp")
        add("yt-dlp", True, value, "")
    except Exception as exc:
        add("yt-dlp", False, exc, "Install yt-dlp in this Python environment.")
    try:
        importlib.import_module("curl_cffi.requests")
        add("impersonation", True, "curl_cffi available for yt-dlp browser impersonation", "")
    except Exception as exc:
        add("impersonation", False, exc,
            'python -m pip install -U "yt-dlp[default,curl-cffi]>=2026.10.26"')
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10, check=True)
        add("ffmpeg", True, result.stdout.splitlines()[0], "")
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        add("ffmpeg", False, exc, "Install ffmpeg and put it on PATH.")
    try:
        importlib.import_module("mlx_whisper")
        add("mlx-whisper", True, "Importable", "")
    except Exception as exc:
        add("mlx-whisper", False, exc, "Install the [asr] extra on Apple Silicon.")
    cache = Path.home() / ".cache/huggingface/hub" / ("models--" + ASR_MODEL.replace("/", "--"))
    # A directory alone is not a usable model: require config and complete weights.
    snapshots = cache / "snapshots"
    try:
        cached = any((snapshot / "config.json").is_file() and
                     any(p.is_file() for pattern in ("*.safetensors", "*.npz") for p in snapshot.glob(pattern))
                     for snapshot in snapshots.iterdir()) if snapshots.is_dir() else False
        detail = cache
    except OSError as exc:
        cached, detail = False, exc
    add("asr-model", cached, detail, f"Cache {ASR_MODEL} before offline ASR use.")
    output = Path(output_dir or (os.environ.get("VIDEO_INTEL_OUT") or "~/video-reports")).expanduser()
    try:
        ancestor = output
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            raise OSError(f"Not a directory: {ancestor}")
        # Probe actual write access without creating the configured output tree.
        with tempfile.TemporaryFile(dir=ancestor) as probe:
            probe.write(b"video-intel doctor")
        add("output-dir", True, output, "")
    except OSError as exc:
        add("output-dir", False, exc, "Set VIDEO_INTEL_OUT to a writable directory.")
    missing = [check["name"] for check in checks if not check["ok"]]
    return {"ok": not missing, "checks": checks, "missing": missing}
