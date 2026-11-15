"""Regressions for Unicode run paths and looping local ASR output."""

import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import MagicMock, patch
import wave

from video_intel import acquisition as acq


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIDEO_ID = "dQw4w9WgXcQ"


class TestAsciiRunDirectories(unittest.TestCase):
    def test_live_eval_titles_and_emoji_fallback(self):
        cases = (
            ("Ex-Google Recruiter Explains 6 Résumé Secrets...",
             "ex-google-recruiter-explains-6-resume-secrets"),
            ("Yeni Mezunlar İçin Mükemmel CV Nasıl Hazırlanır | Noktalı Virgül",
             "yeni-mezunlar-icin-mukemmel-cv-nasil-hazirlanir-noktali"),
            ("Yeni Mezunlar İÇİN MÜKEMMEL CV Nasıl Hazırlanır | Noktalı Virgül".lower(),
             "yeni-mezunlar-icin-mukemmel-cv-nasil-hazirlanir-noktali"),
            ("🎥✨🚀", VIDEO_ID.lower()),
            ("I ı İ Ş ş Ğ ğ Ç ç Ö ö Ü ü", "i-i-i-s-s-g-g-c-c-o-o-u-u"),
        )
        with tempfile.TemporaryDirectory() as root:
            for title, expected in cases:
                with self.subTest(title=title):
                    run = acq.create_run_dir(Path(root), "youtube", title, VIDEO_ID, today="2026-11-15")
                    # Two differently cased Turkish titles intentionally collide.
                    suffix = "-2" if title.startswith("yeni mezunlar") else ""
                    self.assertEqual(run.name, f"2026-11-15-youtube-{expected}{suffix}")
                    self.assertRegex(run.name, r"^[a-z0-9-]+$")
                    self.assertNotIn("%", run.as_uri())

    def test_cap_at_word_boundary_and_keep_collision_contents(self):
        title = "A readable title " * 10
        expected = "a-readable-title-a-readable-title-a-readable-title-a"
        with tempfile.TemporaryDirectory() as root:
            first = acq.create_run_dir(Path(root), "youtube", title, VIDEO_ID, today="2026-11-15")
            sentinel = first / "meta.json"
            sentinel.write_text("preserved")
            second = acq.create_run_dir(Path(root), "youtube", title, VIDEO_ID, today="2026-11-15")
            self.assertEqual(first.name, "2026-11-15-youtube-" + expected)
            self.assertLessEqual(len(expected), 60)
            self.assertEqual(second.name, first.name + "-2")
            self.assertEqual(sentinel.read_text(), "preserved")

    def test_single_long_word_is_still_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            run = acq.create_run_dir(Path(root), "other", "x" * 1000, VIDEO_ID, today="2026-11-15")
            self.assertEqual(run.name, "2026-11-15-other-" + "x" * 60)


class TestAsrPostprocess(unittest.TestCase):
    def test_normalized_loop_is_capped_and_distinct_speech_resets_it(self):
        texts = ["Actual speech", "Thank you.", " THANK  YOU! ", "thank you",
                 "Thank you...", "Ｔｈａｎｋ ｙｏｕ！", "New thought", "thank you"]
        segments = [{"start": i, "end": i + 1, "text": text} for i, text in enumerate(texts)]
        original = copy.deepcopy(segments)
        cleaned, stats = acq.postprocess_asr_segments(segments, duration=20)
        self.assertEqual(cleaned, segments[:4] + segments[6:])
        self.assertEqual(stats, {"dropped_repeats": 2})
        self.assertEqual(segments, original)

    def test_media_duration_boundary_and_missing_duration(self):
        segments = [{"start": 579, "end": 580, "text": "End"},
                    {"start": 580, "end": 581, "text": "Boundary"},
                    {"start": 580.01, "end": 582, "text": "Hallucination"}]
        cleaned, stats = acq.postprocess_asr_segments(segments, duration=580)
        self.assertEqual(cleaned, segments[:2])
        self.assertEqual(stats, {"dropped_repeats": 0, "dropped_after_duration": 1})
        self.assertEqual(acq.postprocess_asr_segments(segments), (segments, {}))

    def test_short_repeats_and_nonconsecutive_text_are_preserved(self):
        segments = [{"start": i, "end": i + 1, "text": text}
                    for i, text in enumerate(["Yes", "Yes", "No", "Yes", "Yes", "Yes"])]
        self.assertEqual(acq.postprocess_asr_segments(segments), (segments, {}))
        self.assertEqual(acq.postprocess_asr_segments([], duration=0), ([], {}))


class TestAsrCleanupIntegration(unittest.TestCase):
    def fetch_with_asr(self, transcribe, *, duration=580, window=None, wav_duration=None):
        ydl = MagicMock()
        metadata = {"id": VIDEO_ID, "title": "ASR cleanup", "acodec": "aac", "duration": duration}
        ydl.__enter__.return_value.extract_info.return_value = metadata
        ydl.__enter__.return_value.prepare_filename.return_value = "source.m4a"

        def convert(command, **kwargs):
            if wav_duration is not None:
                with wave.open(command[-1], "wb") as audio:
                    audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\0\0" * int(wav_duration * 16000))

        with tempfile.TemporaryDirectory() as root, \
                patch.dict(sys.modules, {"mlx_whisper": SimpleNamespace(transcribe=transcribe)}), \
                patch.object(acq, "fetch_metadata", return_value=metadata), \
                patch.object(acq, "_youtube_dl", return_value=ydl), \
                patch.object(acq.subprocess, "run", side_effect=convert):
            options = {"start": window[0], "end": window[1]} if window else {}
            run = acq.fetch_video(URL, Path(root), asr="force", **options)
            return json.loads((run / "transcript.json").read_text())

    def test_decoding_options_and_cleanup_are_saved_to_transcript(self):
        segments = [{"start": 570 + i, "end": 571 + i, "text": "Thank you."} for i in range(6)]
        segments.append({"start": 581, "end": 582, "text": "Beyond media"})

        def transcribe(audio, *, condition_on_previous_text=True, compression_ratio_threshold=None,
                       hallucination_silence_threshold=None, word_timestamps=False, **kwargs):
            self.assertFalse(condition_on_previous_text)
            self.assertEqual(compression_ratio_threshold, 2.4)
            self.assertEqual(hallucination_silence_threshold, 2.0)
            self.assertTrue(word_timestamps)
            return {"language": "en", "segments": segments}

        transcript = self.fetch_with_asr(transcribe)
        self.assertEqual(transcript["segments"], segments[:3])
        self.assertEqual(transcript["asr_postprocess"], {"dropped_repeats": 3, "dropped_after_duration": 1})

    def test_older_signature_gets_no_unsupported_decoding_options(self):
        segments = [{"start": 0, "end": 1, "text": "Speech"}]

        def transcribe(audio, *, path_or_hf_repo, verbose, language,
                       condition_on_previous_text=True, **decode_options):
            self.assertFalse(condition_on_previous_text)
            self.assertEqual(decode_options, {})
            return {"language": "en", "segments": segments}

        transcript = self.fetch_with_asr(transcribe)
        self.assertEqual(transcript["segments"], segments)
        self.assertNotIn("asr_postprocess", transcript)

    def test_wav_duration_with_window_offset_and_no_metadata_duration(self):
        segments = [{"start": 0, "end": 1, "text": "Real speech"},
                    {"start": 3, "end": 4, "text": "Past actual audio end"}]

        def transcribe(audio, **kwargs):
            return {"language": "en", "segments": segments}

        transcript = self.fetch_with_asr(transcribe, duration=None, window=(60, 70), wav_duration=2)
        self.assertEqual(transcript["segments"], [{"start": 60, "end": 61, "text": "Real speech"}])
        self.assertEqual(transcript["asr_postprocess"], {"dropped_repeats": 0, "dropped_after_duration": 1})

    def test_measured_wav_duration_takes_priority_over_approximate_metadata(self):
        segments = [{"start": 0, "end": 0.5, "text": "First sentence"},
                    {"start": 1.5, "end": 1.9, "text": "Real final speech"},
                    {"start": 2.1, "end": 3, "text": "Past measured audio end"}]

        def transcribe(audio, **kwargs):
            return {"language": "en", "segments": segments}

        transcript = self.fetch_with_asr(transcribe, duration=1, wav_duration=2)
        self.assertEqual(transcript["segments"], segments[:2])
        self.assertEqual(transcript["asr_postprocess"], {"dropped_repeats": 0, "dropped_after_duration": 1})


if __name__ == "__main__":
    unittest.main()
