"""Network-free tests; unittest cases are also collected by pytest."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from video_intel import acquisition as acq
from video_intel.captions import parse_srv3, parse_vtt
from video_intel.errors import VideoIntelError, map_error, with_retry

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VTT = "WEBVTT\n\n00:01.000 --> 00:03.500\nHello world.\n"
CAPTIONS = {"source": "captions-manual", "model": None, "language": "en",
            "segments": [{"start": 1.0, "end": 3.5, "text": "Hello world."}]}
INFO = {"id": "dQw4w9WgXcQ", "title": "A / test: video", "channel": "Channel",
        "webpage_url": URL, "subtitles": {"en": [{"ext": "vtt", "data": VTT}]}}


class TestPlatforms(unittest.TestCase):
    def test_detection_table(self):
        for url, expected in (
            (URL, "youtube"), ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
            ("dQw4w9WgXcQ", "youtube"), ("m.youtube.com/shorts/dQw4w9WgXcQ", "youtube"),
            ("https://instagram.com/reel/abc", "instagram"),
            ("https://www.instagram.com/p/abc", "instagram"),
            ("https://twitter.com/user/status/1", "x"), ("https://x.com/user/status/1", "x"),
            ("https://mobile.twitter.com/user/status/1", "x"),
            ("https://www.tiktok.com/@user/video/1", "tiktok"),
            ("https://vm.tiktok.com/abc", "tiktok"), ("https://vimeo.com/1", "other"),
            ("https://youtube.com.evil.test/1", "other"),
        ):
            with self.subTest(url=url):
                self.assertEqual(acq.detect_platform(url), expected)

    def test_twitter_normalization(self):
        self.assertEqual(acq.normalize_url("https://www.twitter.com/u/status/1?s=2"),
                         "https://x.com/u/status/1?s=2")

    def test_rejects_non_web_urls(self):
        for url in ("file:///etc/passwd", "ftp://host/video", "https://user:pass@host/video"):
            with self.subTest(url=url), self.assertRaises(VideoIntelError):
                acq.normalize_url(url)


class TestSubtitleParsing(unittest.TestCase):
    def test_vtt_timestamp_and_settings(self):
        payload = "WEBVTT\nKind: captions\n\ncue-id\n01:02:03.250 --> 01:02:06.500 align:start\nHello\nworld.\n"
        self.assertEqual(parse_vtt(payload), [{"start": 3723.25, "end": 3726.5, "text": "Hello world."}])

    def test_vtt_entities_and_inline_tags(self):
        payload = "WEBVTT\n\n00:01.000 --> 00:02.000\n<v Speaker><c>Fish &amp; chips</c> <00:01.500>today\n"
        self.assertEqual(parse_vtt(payload)[0]["text"], "Fish & chips today")

    def test_vtt_ignores_notes_and_styles(self):
        payload = ("\ufeffWEBVTT\r\n\r\nNOTE ignored\r\n00:00.000 --> 00:01.000\r\nwrong\r\n\r\n"
                   "STYLE\r\n::cue {color:red}\r\n\r\n00:01.000 --> 00:02.000\r\nRight\r\n")
        self.assertEqual(len(parse_vtt(payload)), 1)
        self.assertEqual(parse_vtt(payload)[0]["text"], "Right")

    def test_vtt_rejects_invalid_and_empty_cues(self):
        payload = "WEBVTT\n\nbad --> bad\nX\n\n00:05.000 --> 00:01.000\nX\n\n00:01.000 --> 00:02.000\n"
        self.assertEqual(parse_vtt(payload), [])

    def test_srv3(self):
        payload = '<timedtext><body><p t="1250" d="2250"><s>Hello </s><s>world &amp; all.</s></p></body></timedtext>'
        self.assertEqual(parse_srv3(payload), [{"start": 1.25, "end": 3.5, "text": "Hello world & all."}])

    def test_manual_then_language_then_auto(self):
        info = {"subtitles": {"de": [{"ext": "vtt", "data": VTT}],
                              "en": [{"ext": "vtt", "data": VTT.replace("Hello", "English")}]},
                "automatic_captions": {"tr": [{"ext": "vtt", "data": VTT}]}}
        result = acq.ydl_captions(info, ["tr", "en"])
        self.assertEqual((result["source"], result["language"]), ("captions-manual", "en"))

    def test_auto_and_srv3_fallback(self):
        info = {"automatic_captions": {"tr-TR": [{"ext": "vtt", "data": "bad"},
                {"ext": "srv3", "data": '<timedtext><p t="0" d="1000">Merhaba</p></timedtext>'}]}}
        result = acq.ydl_captions(info, ["tr"])
        self.assertEqual((result["source"], result["language"]), ("captions-auto", "tr-TR"))

    def test_no_supported_captions(self):
        self.assertIsNone(acq.ydl_captions({"subtitles": {"en": [{"ext": "ttml"}]}}, []))

    def test_bad_track_does_not_hide_usable_track(self):
        info = {"subtitles": {"en": [{"ext": "srv3", "data": "<bad"}], "tr": [{"ext": "vtt", "data": VTT}]}}
        self.assertEqual(acq.ydl_captions(info, ["en"])["language"], "tr")


class TestErrors(unittest.TestCase):
    def test_mapping_table(self):
        for message, expected in (
            ("Sign in to confirm your age", "LOGIN_REQUIRED"),
            ("Please log in", "LOGIN_REQUIRED"), ("Login required; pass cookies", "LOGIN_REQUIRED"),
            ("You must be logged in", "LOGIN_REQUIRED"),
            ("HTTP Error 429: Too Many Requests", "RATE_LIMITED"),
            ("rate-limit exceeded", "RATE_LIMITED"), ("Video unavailable", "UNAVAILABLE"),
            ("This video is private", "UNAVAILABLE"), ("Video has been removed", "UNAVAILABLE"),
            ("No subtitles found", "NO_TRANSCRIPT"),
        ):
            with self.subTest(message=message):
                self.assertEqual(map_error(RuntimeError(message)).code, expected)

    def test_preserves_typed_error(self):
        error = VideoIntelError("NO_TRANSCRIPT", "No speech")
        self.assertIs(map_error(error), error)

    def test_retry_backoff(self):
        operation = Mock(side_effect=[OSError("connection reset"), OSError("timeout"), "ok"])
        sleep = Mock()
        self.assertEqual(with_retry(operation, sleep_fn=sleep), "ok")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_retry_exhaustion(self):
        operation = Mock(side_effect=OSError("429 too many requests"))
        with self.assertRaises(VideoIntelError) as caught:
            with_retry(operation, sleep_fn=Mock())
        self.assertEqual(caught.exception.code, "RATE_LIMITED")
        self.assertEqual(operation.call_count, 3)

    def test_login_is_not_retried(self):
        operation = Mock(side_effect=RuntimeError("login required"))
        with self.assertRaises(VideoIntelError):
            with_retry(operation, sleep_fn=Mock())
        operation.assert_called_once()


class TestRunDirectories(unittest.TestCase):
    def test_safe_naming_and_collisions(self):
        with tempfile.TemporaryDirectory() as root:
            first = acq.create_run_dir(Path(root), "youtube", "../A: Video?!", "id", today="2026-11-15")
            sentinel = first / "meta.json"
            sentinel.write_text("old")
            second = acq.create_run_dir(Path(root), "youtube", "../A: Video?!", "id", today="2026-11-15")
            third = acq.create_run_dir(Path(root), "youtube", "../A: Video?!", "id", today="2026-11-15")
            self.assertEqual(first.name, "2026-11-15-youtube-a-video")
            self.assertEqual(second.name, first.name + "-2")
            self.assertEqual(third.name, first.name + "-3")
            self.assertEqual(sentinel.read_text(), "old")

    def test_empty_unicode_and_long_titles(self):
        with tempfile.TemporaryDirectory() as root:
            for title in ("", "<>:/", "İstanbul Türkçe 视频", "x" * 1000, "视" * 1000):
                with self.subTest(title=title):
                    path = acq.create_run_dir(Path(root), "other", title, "../../", today="2026-11-15")
                    self.assertEqual(path.parent, Path(root))
                    self.assertLess(len(path.name), 140)
                    self.assertLess(len(path.name.encode("utf-8")), 240)


class TestFetchDecision(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metadata = patch.object(acq, "fetch_metadata", return_value=INFO).start()
        self.youtube = patch.object(acq, "youtube_captions", return_value=CAPTIONS).start()
        self.asr = patch.object(acq, "asr_transcript", return_value=dict(CAPTIONS, source="asr", model=acq.ASR_MODEL)).start()
        self.addCleanup(patch.stopall)

    def test_youtube_first_and_output_files(self):
        path = acq.fetch_video(URL, self.root, languages=["tr", "en"])
        self.youtube.assert_called_once_with("dQw4w9WgXcQ", ["tr", "en"])
        self.asr.assert_not_called()
        self.assertEqual({p.name for p in path.iterdir()}, {"meta.json", "transcript.json", "transcript.md"})
        transcript = json.loads((path / "transcript.json").read_text())
        self.assertEqual(transcript, CAPTIONS)
        self.assertIn("[00:01] Hello world.", (path / "transcript.md").read_text())
        meta = json.loads((path / "meta.json").read_text())
        self.assertEqual(meta["platform"], "youtube")
        self.assertEqual(meta["uploader"], "Channel")
        self.assertIn("like_count", meta)

    def test_youtube_failure_uses_ydl_captions(self):
        self.youtube.side_effect = RuntimeError("no transcript")
        path = acq.fetch_video(URL, self.root)
        self.asr.assert_not_called()
        self.assertEqual(json.loads((path / "transcript.json").read_text())["source"], "captions-manual")

    def test_other_platform_skips_youtube_api(self):
        acq.fetch_video("https://instagram.com/reel/abc", self.root)
        self.youtube.assert_not_called()
        self.asr.assert_not_called()

    def test_missing_captions_uses_asr(self):
        self.metadata.return_value = dict(INFO, subtitles={})
        acq.fetch_video("https://x.com/u/status/1", self.root, asr_lang="tr", cookies="chrome", keep_audio=True)
        self.asr.assert_called_once()
        self.assertEqual(self.asr.call_args.args[2:], ("tr", "chrome", True))

    def test_force_skips_all_captions(self):
        with patch.object(acq, "ydl_captions") as captions:
            path = acq.fetch_video(URL, self.root, asr="force")
        self.youtube.assert_not_called()
        captions.assert_not_called()
        self.asr.assert_called_once()
        self.assertIn(acq.ASR_MODEL, (path / "transcript.md").read_text())

    def test_never_fails_without_creating_run(self):
        self.metadata.return_value = dict(INFO, subtitles={})
        with self.assertRaises(VideoIntelError) as caught:
            acq.fetch_video("https://tiktok.com/@u/video/1", self.root, asr="never")
        self.assertEqual(caught.exception.code, "NO_TRANSCRIPT")
        self.asr.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_never_preserves_login_error(self):
        with patch.object(acq, "ydl_captions", side_effect=RuntimeError("login required")):
            with self.assertRaises(VideoIntelError) as caught:
                acq.fetch_video("https://instagram.com/reel/1", self.root, asr="never")
        self.assertEqual(caught.exception.code, "LOGIN_REQUIRED")


class TestIntegrations(unittest.TestCase):
    def test_remote_subtitles_preserve_headers_and_opted_in_cookies(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.urlopen.return_value.__enter__.return_value.read.return_value = VTT.encode()
        request = Mock(return_value="request")
        info = {"http_headers": {"Referer": "https://example.org/"},
                "subtitles": {"en": [{"ext": "vtt", "url": "https://example.org/captions.vtt",
                                       "http_headers": {"User-Agent": "test"}}]}}
        with patch.dict(sys.modules, {"yt_dlp.networking": SimpleNamespace(Request=request)}), \
                patch.object(acq, "ydl_options", return_value={"cookiesfrombrowser": ("chrome",)}) as options, \
                patch.object(acq, "_youtube_dl", return_value=ydl):
            result = acq.ydl_captions(info, ["en"], "chrome")
        self.assertEqual(result["segments"][0]["text"], "Hello world.")
        options.assert_called_once_with("chrome")
        request.assert_called_once_with("https://example.org/captions.vtt",
                                        headers={"Referer": "https://example.org/", "User-Agent": "test"})

    def test_metadata_retries_transient_failure(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.side_effect = [OSError("connection reset"), INFO]
        with patch.object(acq, "_youtube_dl", return_value=ydl), patch("video_intel.errors.time.sleep") as sleep:
            self.assertEqual(acq.fetch_metadata(URL), INFO)
        sleep.assert_called_once_with(1)

    def test_metadata_rejects_playlists(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {"_type": "playlist"}
        with patch.object(acq, "_youtube_dl", return_value=ydl), self.assertRaises(VideoIntelError):
            acq.fetch_metadata(URL)

    def test_metadata_uses_download_false_and_opt_in_cookies(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = INFO
        with patch.object(acq, "_youtube_dl", return_value=ydl) as factory:
            self.assertEqual(acq.fetch_metadata(URL), INFO)
        ydl.__enter__.return_value.extract_info.assert_called_once_with(URL, download=False)
        self.assertNotIn("cookiesfrombrowser", factory.call_args.args[0])

    def test_cookies_delegated_to_yt_dlp_parser(self):
        parsed = SimpleNamespace(ydl_opts={"cookiesfrombrowser": ("firefox", "work", None, "Personal")})
        module = SimpleNamespace(parse_options=Mock(return_value=parsed))
        with patch.dict(sys.modules, {"yt_dlp": module}):
            result = acq.ydl_options("firefox:work::Personal")
        self.assertEqual(result["cookiesfrombrowser"], parsed.ydl_opts["cookiesfrombrowser"])
        module.parse_options.assert_called_once_with(["--ignore-config", "--cookies-from-browser", "firefox:work::Personal"])

    def test_missing_yt_dlp(self):
        with patch.dict(sys.modules, {"yt_dlp": None}), self.assertRaises(VideoIntelError) as caught:
            acq._youtube_dl({})
        self.assertEqual(caught.exception.code, "UNAVAILABLE")

    def test_missing_asr_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {"mlx_whisper": None}):
            with self.assertRaises(VideoIntelError) as caught:
                acq.asr_transcript(URL, Path(root))
            self.assertEqual(caught.exception.code, "NO_TRANSCRIPT")
            self.assertIn("[asr]", str(caught.exception))
            self.assertEqual(list(Path(root).iterdir()), [])

    def _asr_run(self, keep=False, failure=None, language="auto"):
        with tempfile.TemporaryDirectory() as root:
            module = SimpleNamespace(transcribe=Mock(return_value={"language": "tr", "segments": CAPTIONS["segments"]}, side_effect=failure))
            ydl = MagicMock()
            client = ydl.__enter__.return_value
            client.extract_info.return_value = {"id": "v", "ext": "m4a"}

            def prepare(info):
                return str(Path(root) / "source.m4a")

            client.prepare_filename.side_effect = prepare

            def convert(command, **kwargs):
                Path(command[-1]).write_bytes(b"wav")

            with patch.dict(sys.modules, {"mlx_whisper": module}), \
                    patch.object(acq, "_youtube_dl", return_value=ydl) as factory, \
                    patch.object(acq.subprocess, "run", side_effect=convert) as ffmpeg:
                if failure:
                    with self.assertRaises(VideoIntelError):
                        acq.asr_transcript(URL, Path(root), language, keep_audio=keep)
                else:
                    result = acq.asr_transcript(URL, Path(root), language, keep_audio=keep)
                    self.assertEqual(result["source"], "asr")
                    self.assertEqual(result["model"], acq.ASR_MODEL)
                    self.assertEqual(result["language"], "tr")
                self.assertEqual(module.transcribe.call_args.kwargs["path_or_hf_repo"], acq.ASR_MODEL)
                self.assertEqual(module.transcribe.call_args.kwargs["language"], None if language == "auto" else language)
                self.assertEqual(factory.call_args.args[0]["format"], "bestaudio")
                client.extract_info.assert_called_once_with(URL, download=True)
                command = ffmpeg.call_args.args[0]
                self.assertEqual(command[command.index("-ar") + 1], "16000")
                self.assertEqual(command[command.index("-ac") + 1], "1")
            self.assertEqual((Path(root) / "audio" / "audio.wav").exists(), keep)
            self.assertFalse(any(p.name.startswith(".audio-") for p in Path(root).iterdir()))

    def test_asr_model_auto_language_and_cleanup(self):
        self._asr_run()

    def test_asr_keep_audio_and_explicit_language(self):
        self._asr_run(keep=True, language="en")

    def test_asr_cleanup_on_error(self):
        self._asr_run(failure=RuntimeError("model failed"))

    def test_missing_ffmpeg_cleans_up(self):
        module = SimpleNamespace(transcribe=Mock())
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {"id": "v"}
        ydl.__enter__.return_value.prepare_filename.return_value = "source.m4a"
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {"mlx_whisper": module}), \
                patch.object(acq, "_youtube_dl", return_value=ydl), \
                patch.object(acq.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(VideoIntelError) as caught:
                acq.asr_transcript(URL, Path(root))
            self.assertIn("ffmpeg", str(caught.exception))
            self.assertEqual(list(Path(root).iterdir()), [])
            module.transcribe.assert_not_called()

    def test_youtube_wrapper_uses_shared_fetch(self):
        shared = SimpleNamespace(fetch_transcript_with_retry=Mock(return_value=SimpleNamespace(
            language="en", is_generated=True, segments=CAPTIONS["segments"])))
        with patch.dict(sys.modules, {"youtube_transcript.transcript": shared}):
            result = acq.youtube_captions("video-id", ["tr", "en"])
        shared.fetch_transcript_with_retry.assert_called_once_with("video-id", ["tr", "en"], include_timestamps=True)
        self.assertEqual(result["source"], "captions-auto")
        self.assertEqual(result["segments"], CAPTIONS["segments"])

    def test_cli_import_does_not_load_heavy_dependencies(self):
        result = subprocess.run([sys.executable, "-c", "import sys; import video_intel.cli; "
            "assert 'yt_dlp' not in sys.modules; assert 'mlx_whisper' not in sys.modules"],
            capture_output=True, text=True, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
