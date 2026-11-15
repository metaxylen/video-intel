"""Command line interface for video acquisition and offline reports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

from video_intel.acquisition import fetch_video, ydl_options
from video_intel.errors import map_error
from video_intel.report import write_report
from video_intel.window import focus_window, parse_time
from youtube_transcript.files import load_urls_from_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch video transcripts and render offline analysis reports.")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Fetch captions, falling back to local speech recognition")
    fetch.add_argument("urls", nargs="*")
    fetch.add_argument("--file", "-f", type=Path, help="URL list; blank lines and # comments ignored")
    fetch.add_argument("--frames", action="store_true", help="Also download video and extract frames")
    fetch.add_argument("--start", type=parse_time, help="Focus start: SS, MM:SS or HH:MM:SS")
    fetch.add_argument("--end", type=parse_time, help="Focus end (exclusive)")
    fetch.add_argument("--lang", default="", help="Preferred caption languages, e.g. tr,en")
    fetch.add_argument("--asr", choices=("auto", "force", "never"), default="auto")
    fetch.add_argument("--asr-lang", choices=("auto", "tr", "en"), default="auto")
    fetch.add_argument("--cookies-from-browser", metavar="SPEC", help="Opt in to yt-dlp browser cookies")
    fetch.add_argument("--keep-audio", action="store_true")
    fetch.add_argument("--out", type=Path, default=None,
                       help="Output root (VIDEO_INTEL_OUT or ~/video-reports)")
    report = commands.add_parser("report", help="Validate analysis.json and render HTML and Markdown")
    report.add_argument("run_dir", type=Path, nargs="?")
    report.add_argument("--compare", type=Path, help="Comparison JSON instead of a single run")
    frames = commands.add_parser("frames", help="Download video lazily and extract scene/interval frames")
    frames.add_argument("run_dir", type=Path)
    frames.add_argument("--max-frames", type=int, default=24)
    frames.add_argument("--every", type=float, help="Maximum gap between frames (default: 30 seconds)")
    frames.add_argument("--keep-video", action="store_true")
    doctor = commands.add_parser("doctor", help="Check setup offline without installing or downloading")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "cookies_from_browser", None):
        try:
            ydl_options(args.cookies_from_browser)
        except (ValueError, SystemExit) as exc:
            parser.error(f"--cookies-from-browser: {exc}")
    if args.command == "doctor":
        from video_intel.doctor import diagnose

        with redirect_stdout(sys.stderr):
            result = diagnose()
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            for check in result["checks"]:
                detail = " ".join(check["detail"].split())
                print(f"{'OK' if check['ok'] else 'FAIL'} {check['name']}: {detail}")
                if check["fix"]:
                    print(f"Fix {check['name']}: {check['fix']}", file=sys.stderr)
        return 0 if result["ok"] else 1
    if args.command == "frames":
        from video_intel.frames import extract_frames

        try:
            with redirect_stdout(sys.stderr):
                records = extract_frames(args.run_dir.expanduser(), args.max_frames, args.every, args.keep_video)
        except (ValueError, OSError, KeyError) as exc:
            print(f"FAIL frames: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            error = map_error(exc)
            print(f"FAIL frames {error.code}: {error}", file=sys.stderr)
            return 1
        print(f"OK frames -> {args.run_dir / 'frames.json'} ({len(records)} frames)")
        return 0
    if args.command == "report":
        try:
            if bool(args.run_dir) == bool(args.compare):
                raise ValueError("Provide either RUN_DIR or --compare PATH/compare.json")
            if args.compare:
                from video_intel.compare import write_compare

                paths = write_compare(args.compare.expanduser())
            else:
                paths = write_report(args.run_dir.expanduser())
        except (ValueError, OSError) as exc:
            print(f"FAIL report: {exc}", file=sys.stderr)
            return 1
        print(f"OK report -> {paths[0]}\nOK Markdown -> {paths[1]}")
        return 0
    root = (args.out or Path((os.environ.get("VIDEO_INTEL_OUT") or "~/video-reports"))).expanduser()
    languages = [part.strip() for part in args.lang.split(",") if part.strip()]
    try:
        focus_window(args.start, args.end)
        if args.file:
            args.urls.extend(load_urls_from_file(args.file.expanduser()))
        if not args.urls:
            raise ValueError("Provide at least one URL or --file urls.txt")
    except (ValueError, OSError) as exc:
        print(f"FAIL fetch: {exc}", file=sys.stderr)
        return 1
    extra = {key: value for key, value in (("start", args.start), ("end", args.end), ("frames", args.frames))
             if value is not None and value is not False}
    failed = 0
    for url in args.urls:
        try:
            with redirect_stdout(sys.stderr):
                run_dir = fetch_video(url, root, languages=languages, asr=args.asr, asr_lang=args.asr_lang,
                                      cookies=args.cookies_from_browser, keep_audio=args.keep_audio, **extra)
            print(f"OK {url} -> {run_dir}")
        except Exception as exc:
            error = map_error(exc, cookies=args.cookies_from_browser)
            failed += 1
            # One machine-readable result line per URL, even for multiline extractor errors.
            print(f"FAIL {url} {error.code} {' '.join(str(error).split())}")
    print(f"Summary: {len(args.urls) - failed} succeeded, {failed} failed")
    return 1 if failed else 0
