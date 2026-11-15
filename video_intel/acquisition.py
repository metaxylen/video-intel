"""Caption-first acquisition. Heavy integrations are imported only when used."""

from __future__ import annotations

import json
import os
from optparse import OptParseError
import sys
from contextlib import redirect_stdout
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from youtube_transcript.files import sanitize_filename
from youtube_transcript.markdown import CaptionSegment, build_markdown_document, merge_captions
from youtube_transcript.urls import extract_video_id

from video_intel.captions import parse_srv3, parse_vtt
from video_intel.errors import VideoIntelError, map_error, with_retry
from video_intel.window import clip_transcript, focus_window

ASR_MODEL = "mlx-community/whisper-large-v3-turbo"


def normalize_url(url: str) -> str:
    url = url.strip()
    if extract_video_id(url) and "://" not in url:
        return f"https://www.youtube.com/watch?v={extract_video_id(url)}"
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username:
        raise VideoIntelError("UNAVAILABLE", "Expected an HTTP(S) video URL")
    host = parts.hostname.lower()
    if host in ("twitter.com", "www.twitter.com", "mobile.twitter.com"):
        parts = parts._replace(netloc="x.com")
    return urlunsplit(parts)


def detect_platform(url: str) -> str:
    host = (urlsplit(normalize_url(url)).hostname or "").lower()
    for platform, domains in (
        ("youtube", ("youtube.com", "youtu.be")),
        ("instagram", ("instagram.com",)),
        ("x", ("x.com", "twitter.com")),
        ("tiktok", ("tiktok.com",)),
    ):
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return "other"


def ydl_options(cookies: str | None = None) -> dict:
    options = {"quiet": True, "noprogress": True, "no_warnings": True, "noplaylist": True,
               "socket_timeout": 30, "retries": 0, "fragment_retries": 0}
    if cookies:
        # Let yt-dlp interpret its own BROWSER[+KEYRING][:PROFILE][::CONTAINER] syntax.
        import yt_dlp

        try:
            parsed = yt_dlp.parse_options(["--ignore-config", "--cookies-from-browser", cookies])
            options["cookiesfrombrowser"] = parsed.ydl_opts["cookiesfrombrowser"]
        except (ValueError, SystemExit, OptParseError) as exc:
            raise ValueError("Invalid --cookies-from-browser specification") from exc
    return options


def _youtube_dl(options):
    try:
        import yt_dlp
    except ImportError as exc:
        raise VideoIntelError("UNAVAILABLE", "yt-dlp is required for video acquisition") from exc
    return yt_dlp.YoutubeDL(options)


def fetch_metadata(url: str, cookies=None) -> dict:
    def extract():
        with _youtube_dl(ydl_options(cookies)) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info or info.get("_type") in ("playlist", "multi_video"):
            raise VideoIntelError("UNAVAILABLE", "Expected a single available video")
        return info

    return with_retry(extract, cookies=cookies)


def youtube_captions(video_id: str, languages: list[str]) -> dict:
    from youtube_transcript.transcript import fetch_transcript_with_retry

    result = fetch_transcript_with_retry(video_id, languages, include_timestamps=True)
    if not result.segments or not any(s["text"].strip() for s in result.segments):
        raise VideoIntelError("NO_TRANSCRIPT", "YouTube returned empty captions")
    return {"source": "captions-auto" if result.is_generated else "captions-manual",
            "model": None, "language": result.language, "segments": result.segments}


def _language_rank(language, languages):
    for index, preference in enumerate(languages):
        if language == preference or language.startswith(preference + "-"):
            return index
    return len(languages)


def ydl_captions(info: dict, languages: list[str], cookies=None) -> dict | None:
    """Try manual tracks before automatic ones, preferring requested languages."""
    languages = languages or ([info["language"]] if info.get("language") else [])
    last_error = None
    for key, source in (("subtitles", "captions-manual"), ("automatic_captions", "captions-auto")):
        tracks = info.get(key) or {}
        for language in sorted(tracks, key=lambda lang: _language_rank(lang, languages)):
            if key == "automatic_captions" and not (
                _language_rank(language, languages) < len(languages)
                or language.endswith("-orig") or language == info.get("language")
            ):
                continue
            formats = sorted(tracks[language], key=lambda f: {"vtt": 0, "srv3": 1}.get(f.get("ext"), 2))
            for track in formats:
                ext = track.get("ext")
                if ext not in ("vtt", "srv3"):
                    continue
                try:
                    def read():
                        if "data" in track:
                            return track["data"]
                        with _youtube_dl(ydl_options(cookies)) as ydl:
                            # Keep extractor headers and opted-in cookies on subtitle requests.
                            from yt_dlp.networking import Request

                            headers = dict(info.get("http_headers") or {})
                            headers.update(track.get("http_headers") or {})
                            with ydl.urlopen(Request(track["url"], headers=headers)) as response:
                                return response.read().decode("utf-8-sig")

                    payload = with_retry(read, cookies=cookies)
                    segments = (parse_vtt if ext == "vtt" else parse_srv3)(payload)
                    if segments:
                        return {"source": source, "model": None, "language": language, "segments": segments}
                except Exception as exc:
                    last_error = map_error(exc, cookies=cookies)
    if last_error:
        raise last_error
    return None


def create_run_dir(root: Path, platform: str, title: str, video_id: str, today=None) -> Path:
    """Reserve a unique directory atomically, including across concurrent fetches."""
    safe_title = sanitize_filename(title or video_id, max_length=90)
    slug = re.sub(r"[^\w-]+", "-", safe_title, flags=re.UNICODE).strip("-_").lower() or "video"
    slug = slug.encode("utf-8")[:160].decode("utf-8", errors="ignore").rstrip("-")
    prefix = f"{today or date.today().isoformat()}-{platform}-{slug}"
    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    suffix = 1
    while True:
        candidate = root / (prefix if suffix == 1 else f"{prefix}-{suffix}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            suffix += 1


def has_audio_stream(source: Path, info: dict) -> bool:
    """Inspect selected streams, never unselected alternatives in info['formats']."""
    selected = info.get("requested_downloads") or info.get("requested_formats") or [info]
    codecs = [stream.get("acodec") for stream in selected]
    if any(codec and codec != "none" for codec in codecs):
        return True
    if codecs and all(codec == "none" for codec in codecs):
        return False
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                                 "-show_entries", "stream=codec_type", "-of", "json", str(source)],
                                check=True, capture_output=True, text=True, timeout=30)
        return bool(json.loads(result.stdout)["streams"])
    except FileNotFoundError as exc:
        raise VideoIntelError("NO_TRANSCRIPT", "Audio inspection requires ffprobe (install ffmpeg) on PATH") from exc
    except (subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise VideoIntelError("NO_TRANSCRIPT", "ffprobe could not inspect downloaded audio") from exc


def asr_transcript(url: str, run_dir: Path, language="auto", cookies=None, keep_audio=False, window=None,
                   allow_empty=False) -> dict:
    def transcribe(work_dir):
        audio = work_dir / "audio.wav"

        def download():
            options = ydl_options(cookies)
            options.update({"format": "bestaudio/best", "outtmpl": str(work_dir / "source.%(ext)s")})
            with _youtube_dl(options) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise VideoIntelError("UNAVAILABLE", "Audio download returned no video")
                return Path(ydl.prepare_filename(info)), info

        source, info = with_retry(download, cookies=cookies)
        if not has_audio_stream(source, info):
            raise VideoIntelError("NO_AUDIO", "platform served video without audio; retry with "
                                  "--cookies-from-browser if the user allows, or use --frames for on-screen text")
        # Set before imports: huggingface_hub reads environment at import time.
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        os.environ["TQDM_DISABLE"] = "1"
        try:
            with redirect_stdout(sys.stderr):
                import mlx_whisper
                try:
                    from huggingface_hub.utils import disable_progress_bars
                    disable_progress_bars()
                except ImportError:
                    pass
        except ImportError as exc:
            raise VideoIntelError("NO_TRANSCRIPT", "ASR needs the [asr] extra (mlx-whisper) on Apple Silicon") from exc
        slice_args = []
        if window:
            slice_args = ["-ss", str(window["start"])]
            if window["end"] is not None:
                slice_args += ["-to", str(window["end"])]
        try:
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(source),
                            *slice_args, "-vn", "-ar", "16000", "-ac", "1", str(audio)],
                           check=True, capture_output=True, timeout=300)
        except FileNotFoundError as exc:
            raise VideoIntelError("NO_TRANSCRIPT", "ASR requires ffmpeg on PATH") from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise VideoIntelError("NO_TRANSCRIPT", "ffmpeg could not convert audio to 16 kHz mono WAV") from exc
        try:
            with redirect_stdout(sys.stderr):
                result = mlx_whisper.transcribe(str(audio), path_or_hf_repo=ASR_MODEL, verbose=None,
                                                language=None if language == "auto" else language)
        except Exception as exc:
            raise VideoIntelError("NO_TRANSCRIPT", f"Local ASR failed: {exc}") from exc
        offset = window["start"] if window else 0
        segments = [{"start": float(s["start"]) + offset, "end": float(s["end"]) + offset, "text": str(s["text"])}
                    for s in result.get("segments", []) if str(s.get("text", "")).strip()]
        if not segments and not allow_empty:
            raise VideoIntelError("NO_TRANSCRIPT", "ASR returned no speech segments")
        return {"source": "asr", "model": ASR_MODEL,
                "language": result.get("language") or language, "segments": segments}

    if keep_audio:
        work_dir = run_dir / "audio"
        work_dir.mkdir()
        return transcribe(work_dir)
    with tempfile.TemporaryDirectory(prefix=".audio-", dir=run_dir) as directory:
        return transcribe(Path(directory))


def fetch_video(url: str, root: Path, languages=None, asr="auto", asr_lang="auto",
                cookies=None, keep_audio=False, start=None, end=None, frames=False) -> Path:
    window = focus_window(start, end)
    url = normalize_url(url)
    platform = detect_platform(url)
    languages = languages or []
    try:
        info = fetch_metadata(url, cookies)
    except Exception as exc:
        if platform != "youtube" or not extract_video_id(url):
            raise
        print(f"WARNING metadata: {' '.join(str(exc).split())}; trying YouTube captions", file=sys.stderr)
        info = {"id": extract_video_id(url), "title": extract_video_id(url), "webpage_url": url}
    languages = languages or ([info["language"]] if info.get("language") else [])
    video_id = str(info.get("id") or extract_video_id(url) or "video")
    title = str(info.get("title") or video_id)
    transcript = None
    caption_error = None
    if asr != "force":
        if platform == "youtube" and extract_video_id(url):
            try:
                transcript = youtube_captions(extract_video_id(url), languages)
            except Exception as exc:
                caption_error = map_error(exc, cookies=cookies)
        if transcript is None:
            try:
                transcript = ydl_captions(info, languages, cookies)
            except Exception as exc:
                caption_error = map_error(exc, cookies=cookies)
        if transcript is None and asr == "never":
            if caption_error and caption_error.code in ("LOGIN_REQUIRED", "RATE_LIMITED", "BLOCKED", "UNAVAILABLE"):
                raise caption_error
            raise VideoIntelError("NO_TRANSCRIPT", "No usable captions; ASR disabled by --asr never")

    root = Path(root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".run-", dir=root) as staging:
        run_dir = Path(staging)
        if transcript is None:
            try:
                transcript = asr_transcript(url, run_dir, asr_lang, cookies, keep_audio,
                                            **({"window": window} if window else {}),
                                            **({"allow_empty": True} if frames else {}))
            except VideoIntelError as exc:
                if not frames or exc.code != "NO_AUDIO":
                    raise
                print(f"WARNING NO_AUDIO: {exc}", file=sys.stderr)
                transcript = {"source": "none", "model": None, "language": None, "segments": []}
        transcript = clip_transcript(transcript, window)
        meta = {key: info.get(key) for key in (
            "upload_date", "duration", "description", "view_count", "like_count",
        )}
        meta.update({"id": video_id, "title": title, "uploader": info.get("uploader") or info.get("channel"),
                     "channel": info.get("channel") or info.get("uploader"),
                     "webpage_url": info.get("webpage_url") or url, "platform": platform})
        for name, value in (("meta.json", meta), ("transcript.json", transcript)):
            (run_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        body = merge_captions([CaptionSegment(s["start"], s["text"]) for s in transcript["segments"]],
                              include_timestamps=True)
        document = build_markdown_document(title, url, meta["channel"], transcript["language"],
                                           transcript["source"] != "captions-manual", body)
        document = document.replace("- Type: auto-generated", f"- Type: {transcript['source']}")
        if transcript["source"] == "asr":
            document += f"\nASR model: {ASR_MODEL}. Names and numbers may contain recognition errors.\n"
        (run_dir / "transcript.md").write_text(document, encoding="utf-8")
        if frames:
            from video_intel.frames import extract_frames

            extract_frames(run_dir, cookies=cookies)
        # Reserve a unique destination only once every artifact is ready.
        destination = create_run_dir(root, platform, title, video_id)
        try:
            run_dir.replace(destination)
        except BaseException:
            destination.rmdir()
            raise
        return destination
