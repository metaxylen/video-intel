"""Command line interface for video acquisition and offline reports."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from video_intel.acquisition import fetch_video
from video_intel.errors import map_error
from video_intel.report import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch video transcripts and render offline analysis reports.")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("fetch", help="Fetch captions, falling back to local speech recognition")
    fetch.add_argument("urls", nargs="+")
    fetch.add_argument("--lang", default="", help="Preferred caption languages, e.g. tr,en")
    fetch.add_argument("--asr", choices=("auto", "force", "never"), default="auto")
    fetch.add_argument("--asr-lang", choices=("auto", "tr", "en"), default="auto")
    fetch.add_argument("--cookies-from-browser", metavar="SPEC", help="Opt in to yt-dlp browser cookies")
    fetch.add_argument("--keep-audio", action="store_true")
    fetch.add_argument("--out", type=Path, default=None,
                       help="Output root (VIDEO_INTEL_OUT or ~/video-reports)")
    report = commands.add_parser("report", help="Validate analysis.json and render HTML and Markdown")
    report.add_argument("run_dir", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "report":
        try:
            paths = write_report(args.run_dir.expanduser())
        except (ValueError, OSError) as exc:
            print(f"FAIL report: {exc}", file=sys.stderr)
            return 1
        print(f"OK report -> {paths[0]}\nMarkdown -> {paths[1]}")
        return 0
    root = (args.out or Path(os.environ.get("VIDEO_INTEL_OUT", "~/video-reports"))).expanduser()
    languages = [part.strip() for part in args.lang.split(",") if part.strip()]
    failed = 0
    for url in args.urls:
        try:
            run_dir = fetch_video(url, root, languages=languages, asr=args.asr, asr_lang=args.asr_lang,
                                  cookies=args.cookies_from_browser, keep_audio=args.keep_audio)
            print(f"OK {url} -> {run_dir}")
        except Exception as exc:
            error = map_error(exc)
            failed += 1
            # One machine-readable result line per URL, even for multiline extractor errors.
            print(f"FAIL {url} {error.code} {' '.join(str(error).split())}")
    print(f"Summary: {len(args.urls) - failed} succeeded, {failed} failed")
    return 1 if failed else 0
