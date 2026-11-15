"""Lazy video download and bounded scene/interval JPEG extraction."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from video_intel.acquisition import _youtube_dl, normalize_url, ydl_options
from video_intel.errors import VideoIntelError, with_retry
from video_intel.validation import read_json
from video_intel.window import focus_window


def extract_frames(run_dir: Path, max_frames=24, every=None, keep_video=False, cookies=None):
    if type(max_frames) is not int or max_frames < 1:
        raise ValueError("--max-frames must be a positive integer")
    every = 30.0 if every is None else every
    if type(every) not in (int, float) or not math.isfinite(every) or every <= 0:
        raise ValueError("--every must be finite and greater than zero")
    run_dir = Path(run_dir)
    meta = read_json(run_dir / "meta.json")
    url = normalize_url(meta["webpage_url"])
    transcript_path = run_dir / "transcript.json"
    window = read_json(transcript_path).get("window") if transcript_path.is_file() else None
    window = focus_window(**window) if window else None
    previous_path = run_dir / "frames.json"
    previous = read_json(previous_path) if previous_path.is_file() else []
    work = Path(tempfile.mkdtemp(prefix=".video-", dir=run_dir))
    retained = False
    try:
        def download():
            options = ydl_options(cookies)
            # Include combined and video-only formats; prioritize height over quality.
            options.update(format="worst*[height>=360][vcodec!=none]",
                           format_sort=["height", "tbr"], format_sort_force=True,
                           outtmpl=str(work / "source.%(ext)s"))
            with _youtube_dl(options) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise VideoIntelError("UNAVAILABLE", "Video download returned no video")
                return Path(ydl.prepare_filename(info))

        video = with_retry(download)
        command = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "info",
                   "-threads", "1", "-filter_threads", "1"]
        offset = window["start"] if window else 0
        if window:
            command += ["-ss", str(offset)]
            if window["end"] is not None:
                command += ["-to", str(window["end"])]
        command += ["-i", str(video), "-an", "-vf",
                    f"select='isnan(prev_selected_t)+gt(scene,0.3)+gte(t-prev_selected_t,{every})',scale=512:-2,showinfo",
                    "-fps_mode", "vfr", "-frames:v", str(max_frames), "-threads", "1",
                    "-q:v", "3", str(work / "frame-%06d.jpg")]
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as exc:
            raise VideoIntelError("UNAVAILABLE", "Frame extraction requires ffmpeg on PATH") from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise VideoIntelError("UNAVAILABLE", "ffmpeg could not extract frames") from exc
        times = [float(t) + offset for t in re.findall(r"\bpts_time:([\d.eE+-]+)", result.stderr)]
        images = sorted(work.glob("frame-*.jpg"))[:max_frames]
        if not images or len(times) < len(images):
            raise VideoIntelError("UNAVAILABLE", "ffmpeg returned no timestamped frames in the focus window")
        records = []
        destination = run_dir / "frames"
        destination.mkdir(exist_ok=True)
        seen = set()
        for image, t in zip(images, times):
            if not math.isfinite(t) or t < 0 or (window and
                    (t < offset or (window["end"] is not None and t >= window["end"]))):
                continue
            t = round(t, 2)
            if window and window["end"] is not None and t >= window["end"]:
                continue
            name = f"{t:07.2f}.jpg"
            if name in seen:
                continue
            seen.add(name)
            shutil.copyfile(image, destination / name)
            records.append({"t": t, "path": f"frames/{name}"})
        if not records:
            raise VideoIntelError("UNAVAILABLE", "No frames inside the focus window")
        (run_dir / "frames.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        # Only remove files owned by the previous manifest, after a successful run.
        current = {record["path"] for record in records}
        for record in previous if isinstance(previous, list) else []:
            path = record.get("path") if isinstance(record, dict) else None
            if isinstance(path, str) and re.fullmatch(r"frames/\d{4,}\.\d{2}\.jpg", path) and path not in current:
                (run_dir / path).unlink(missing_ok=True)
        if keep_video:
            # Keep only the downloaded video, never the intermediate JPEGs.
            for image in work.glob("frame-*.jpg"):
                image.unlink()
            retained = True
        return records
    finally:
        if not retained:
            shutil.rmtree(work)
