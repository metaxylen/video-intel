import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from video_intel import cli
from video_intel.errors import VideoIntelError


class TestCLI(unittest.TestCase):
    def run_cli(self, arguments):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = cli.main(arguments)
        return result, out.getvalue(), err.getvalue()

    def test_batch_continues_and_exits_one(self):
        with patch.object(cli, "fetch_video", side_effect=[Path("run-a"), VideoIntelError("LOGIN_REQUIRED", "Please login"), Path("run-c")]) as fetch:
            result, out, _ = self.run_cli(["fetch", "https://x.com/1", "https://x.com/2", "https://x.com/3"])
        self.assertEqual(result, 1)
        self.assertEqual(fetch.call_count, 3)
        self.assertIn("OK https://x.com/1 -> run-a", out)
        self.assertIn("FAIL https://x.com/2 LOGIN_REQUIRED Please login", out)
        self.assertIn("OK https://x.com/3 -> run-c", out)
        self.assertIn("Summary: 2 succeeded, 1 failed", out)

    def test_fetch_options_and_out_precedence(self):
        with patch.object(cli, "fetch_video", return_value=Path("run")) as fetch, patch.dict(os.environ, {"VIDEO_INTEL_OUT": "env-output"}):
            result, out, _ = self.run_cli(["fetch", "https://x.com/1", "--lang", "tr, en", "--asr", "force", "--asr-lang", "tr",
                                         "--cookies-from-browser", "chrome:Profile 1", "--keep-audio", "--out", "chosen"])
        self.assertEqual(result, 0)
        self.assertEqual(fetch.call_args.args[1], Path("chosen"))
        self.assertEqual(fetch.call_args.kwargs, {"languages": ["tr", "en"], "asr": "force", "asr_lang": "tr",
                                                 "cookies": "chrome:Profile 1", "keep_audio": True})
        self.assertIn("Summary: 1 succeeded, 0 failed", out)

    def test_environment_output_default(self):
        with patch.object(cli, "fetch_video", return_value=Path("run")) as fetch, patch.dict(os.environ, {"VIDEO_INTEL_OUT": "env-output"}):
            self.run_cli(["fetch", "https://x.com/1"])
        self.assertEqual(fetch.call_args.args[1], Path("env-output"))
        self.assertIsNone(fetch.call_args.kwargs["cookies"])

    def test_home_output_default(self):
        env = dict(os.environ)
        env.pop("VIDEO_INTEL_OUT", None)
        with patch.object(cli, "fetch_video", return_value=Path("run")) as fetch, patch.dict(os.environ, env, clear=True):
            self.run_cli(["fetch", "https://x.com/1"])
        self.assertEqual(fetch.call_args.args[1], Path.home() / "video-reports")

    def test_multiline_failure_is_one_line(self):
        with patch.object(cli, "fetch_video", side_effect=RuntimeError("Video unavailable\nDetails")):
            result, out, _ = self.run_cli(["fetch", "https://x.com/1"])
        self.assertEqual(result, 1)
        self.assertEqual(len(out.splitlines()), 2)

    def test_report_validation_failure(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "analysis.json").write_text('{}')
            result, _, err = self.run_cli(["report", root])
            self.assertFalse((Path(root) / "report.html").exists())
        self.assertEqual(result, 1)
        self.assertIn("schema_version", err)
        self.assertIn("lenses", err)

    def test_report_invalid_json_and_missing_run(self):
        with tempfile.TemporaryDirectory() as root:
            result, _, err = self.run_cli(["report", root])
            self.assertEqual(result, 1)
            self.assertIn("analysis.json", err)
            (Path(root) / "analysis.json").write_text('{bad')
            result, _, err = self.run_cli(["report", root])
            self.assertEqual(result, 1)
            self.assertIn("FAIL report:", err)

    def test_report_success_real_files(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            analysis = {"schema_version": 1, "transcript_source": "captions-auto", "asr_model": None,
                        "lenses": {"summary": {"tldr": "A report", "key_points": [], "audience": None}}, "caveats": []}
            (path / "analysis.json").write_text(json.dumps(analysis))
            (path / "meta.json").write_text(json.dumps({"title": "Report title", "webpage_url": "https://example.org/video"}))
            result, out, _ = self.run_cli(["report", root])
            self.assertTrue((path / "report.html").is_file())
            self.assertTrue((path / "report.md").is_file())
        self.assertEqual(result, 0)
        self.assertIn("OK report ->", out)

    def test_module_entrypoint_renders_without_optional_dependencies(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            data = {"schema_version": 1, "video": {"title": "CLI report", "webpage_url": "https://example.org/video"},
                    "transcript_source": "captions-manual", "asr_model": None, "lenses": {}, "caveats": []}
            (path / "analysis.json").write_text(json.dumps(data))
            result = subprocess.run([sys.executable, "-m", "video_intel", "report", root],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CLI report", (path / "report.html").read_text())
            self.assertIn("# CLI report", (path / "report.md").read_text())


class TestSharedTranscriptCompatibility(unittest.TestCase):
    def test_existing_selection_retry_merge_and_raw_timing(self):
        # Supply the API dependency in-memory so this exercises the shared module
        # even on a machine with only Python's standard library installed.
        fake = types.ModuleType("youtube_transcript_api")
        fake.CouldNotRetrieveTranscript = type("CouldNotRetrieveTranscript", (Exception,), {})
        for name in ("NoTranscriptFound", "RequestBlocked", "TranscriptsDisabled", "VideoUnavailable", "YouTubeRequestFailed"):
            setattr(fake, name, type(name, (fake.CouldNotRetrieveTranscript,), {}))
        fake.YouTubeTranscriptApi = Mock()
        source = Path(__file__).resolve().parents[1] / "youtube_transcript" / "transcript.py"
        spec = importlib.util.spec_from_file_location("_shared_transcript_test", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"youtube_transcript_api": fake, spec.name: module}):
            spec.loader.exec_module(module)
            class Fetched(list):
                language_code = "en"
                is_generated = False

            fetched = Fetched([SimpleNamespace(start=65.0, duration=1.0, text="Hello"),
                               SimpleNamespace(start=66.0, duration=2.5, text="world.")])
            track = SimpleNamespace(language_code="en", is_generated=False, fetch=Mock(return_value=fetched))
            auto = SimpleNamespace(language_code="tr", is_generated=True, fetch=Mock())
            client = SimpleNamespace(list=Mock(side_effect=[fake.YouTubeRequestFailed("timeout"), [auto, track]]))
            sleep = Mock()
            result = module.fetch_transcript_with_retry("video-id", ["en"], True, sleep_fn=sleep, api=client)
        self.assertEqual(result.text, "[01:05] Hello world.")
        self.assertEqual(result.segments[1], {"start": 66.0, "end": 68.5, "text": "world."})
        sleep.assert_called_once_with(1)
        auto.fetch.assert_not_called()
