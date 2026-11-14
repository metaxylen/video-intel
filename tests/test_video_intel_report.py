import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from video_intel.report import generic, render_reports, timestamp_url, write_report
from video_intel.validation import ValidationError, read_json, safe_url, validate_analysis


def analysis_fixture():
    return {
        "schema_version": 1,
        "video": {"id": "dQw4w9WgXcQ", "title": "A video", "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "platform": "youtube"},
        "transcript_source": "captions-manual", "asr_model": None,
        "lenses": {
            "summary": {"tldr": "A useful summary.", "key_points": ["First point", "Second point"], "audience": "Developers"},
            "moments": [{"t": 65.5, "title": "Important moment", "note": "What changed"}],
            "claims": [{"id": "c1", "claim_reviewed": "A checkable claim", "quote": "The speaker's words", "t": 125,
                        "kind": "fact", "verdict": "mostly-true", "rating": 4, "confidence": "high",
                        "rationale": "Primary evidence supports this.",
                        "evidence": [{"url": "https://example.org/source", "publisher": "Primary source",
                                      "published": "2026-11-01", "retrieved": "2026-11-15", "snippet": "Short evidence quote."}]}],
        },
        "caveats": ["The video may simplify the topic."]
    }


class TestSchema(unittest.TestCase):
    def test_valid_analysis(self):
        validate_analysis(analysis_fixture())

    def test_partial_and_future_lenses(self):
        data = analysis_fixture()
        data["lenses"] = {"future": {"nested": [{"tag": "tool"}], "confidence": 0.8}}
        validate_analysis(data)

    def test_nullable_fields(self):
        data = analysis_fixture()
        data["lenses"]["summary"]["audience"] = None
        claim = data["lenses"]["claims"][0]
        claim["rating"] = None
        claim["evidence"][0]["published"] = None
        validate_analysis(data)

    def test_missing_required_top_level_fields(self):
        for key in analysis_fixture():
            data = analysis_fixture()
            del data[key]
            with self.subTest(key=key), self.assertRaises(ValidationError) as caught:
                validate_analysis(data)
            self.assertIn(key, str(caught.exception))

    def test_invalid_top_level_types(self):
        for value in ([], None, "bad", 1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_analysis(value)

    def test_nested_required_fields(self):
        for lens, key in (("summary", "tldr"), ("moments", "note"), ("claims", "quote")):
            data = analysis_fixture()
            target = data["lenses"][lens]
            target = target if isinstance(target, dict) else target[0]
            del target[key]
            with self.subTest(lens=lens), self.assertRaises(ValidationError) as caught:
                validate_analysis(data)
            self.assertIn(key, str(caught.exception))

    def test_invalid_claim_values(self):
        for key, value in (("claim_reviewed", "x" * 76), ("kind", "rumour"), ("verdict", "yes"),
                           ("rating", 0), ("rating", 6), ("rating", True), ("rating", 2.5),
                           ("confidence", "certain"), ("t", -1), ("t", float("nan")),
                           ("t", float("inf")), ("t", "65"), ("quote", None), ("evidence", {})):
            data = analysis_fixture()
            data["lenses"]["claims"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                validate_analysis(data)

    def test_claim_length_boundary(self):
        data = analysis_fixture()
        data["lenses"]["claims"][0]["claim_reviewed"] = "x" * 75
        validate_analysis(data)

    def test_snippet_word_limit(self):
        data = analysis_fixture()
        evidence = data["lenses"]["claims"][0]["evidence"][0]
        evidence["snippet"] = " ".join(["word"] * 25)
        validate_analysis(data)
        evidence["snippet"] += " extra"
        with self.assertRaises(ValidationError) as caught:
            validate_analysis(data)
        self.assertIn("25 words", str(caught.exception))

    def test_evidence_dates_and_urls(self):
        for key, value in (("retrieved", "2026-02-30"), ("retrieved", "20261115"),
                           ("url", "javascript:alert(1)"), ("publisher", None)):
            data = analysis_fixture()
            data["lenses"]["claims"][0]["evidence"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_analysis(data)

    def test_bad_version_and_source(self):
        for key, value in (("schema_version", 2), ("schema_version", True),
                           ("transcript_source", "unknown"), ("asr_model", {})):
            data = analysis_fixture()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_analysis(data)

    def test_reports_multiple_validation_errors(self):
        data = analysis_fixture()
        del data["schema_version"]
        data["caveats"] = "bad"
        with self.assertRaises(ValidationError) as caught:
            validate_analysis(data)
        self.assertGreaterEqual(len(caught.exception.errors), 2)

    def test_json_rejects_nonstandard_constants(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "analysis.json"
            path.write_text('{"value": NaN}')
            with self.assertRaises(ValueError):
                read_json(path)


class _HTMLAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.links = []
        self.external_resources = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == "a":
            self.links.append(attributes.get("href", ""))
        if tag in ("script", "iframe", "img", "link", "video", "audio", "object"):
            self.external_resources.append((tag, attributes))


class TestRenderer(unittest.TestCase):
    def test_known_lenses_and_evidence(self):
        document, markdown = render_reports(analysis_fixture())
        for text in ("Summary", "Key moments", "Claims", "Caveats", "Primary source",
                     "mostly true", "Confidence: high", "Rating: 4/5", "01:05", "02:05", "2026-11-15"):
            with self.subTest(text=text):
                self.assertIn(text, document)
                self.assertIn(text, markdown)
        audit = _HTMLAudit()
        audit.feed(document)
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=65", audit.links)
        self.assertIn("https://example.org/source", audit.links)

    def test_unknown_lens_nested_data(self):
        data = analysis_fixture()
        data["lenses"]["tool mentions"] = {"tools": [{"name": "Example tool", "steps": ["Install", "Use"]}], "empty": None}
        document, markdown = render_reports(data)
        for text in ("tool mentions", "Example tool", "Install", "Use"):
            self.assertIn(text, document)
            self.assertIn(text, markdown)
        self.assertIn("<dl>", document)

    def test_escapes_all_untrusted_text(self):
        attack = '<script>alert("x")</script><img src=x onerror=alert(1)>'
        data = analysis_fixture()
        data["video"]["title"] = attack
        data["video"]["channel"] = attack
        data["lenses"]["summary"]["tldr"] = attack
        claim = data["lenses"]["claims"][0]
        claim["quote"] = attack
        claim["claim_reviewed"] = "<img onerror=alert(1)>"
        claim["rationale"] = attack
        claim["id"] = attack
        claim["evidence"][0]["publisher"] = attack
        data["lenses"][attack] = {attack: [attack]}
        data["caveats"] = [attack]
        transcript = {"segments": [{"start": 0, "text": attack}]}
        document, markdown = render_reports(data, transcript)
        self.assertIn("&lt;script&gt;", document)
        self.assertNotIn("<script>", markdown)
        audit = _HTMLAudit()
        audit.feed(document)
        self.assertEqual(audit.external_resources, [])
        self.assertNotIn("script", audit.tags)

    def test_offline_responsive_theme(self):
        document, _ = render_reports(analysis_fixture())
        self.assertIn('name="viewport"', document)
        self.assertIn("prefers-color-scheme:dark", document)
        self.assertIn("--bg:", document)
        self.assertIn("max-width:480px", document)
        self.assertIn("overflow-wrap:anywhere", document)
        self.assertIn("system-ui", document)
        self.assertIn("Content-Security-Policy", document)
        audit = _HTMLAudit()
        audit.feed(document)
        self.assertEqual(audit.external_resources, [])

    def test_asr_source_model_and_caveat(self):
        data = analysis_fixture()
        data.update(transcript_source="asr", asr_model="mlx-community/whisper-large-v3-turbo", caveats=[])
        document, markdown = render_reports(data)
        for output in (document, markdown):
            self.assertIn("whisper", output)
            self.assertIn("names and numbers", output)

    def test_optional_audience_empty_lenses_and_null_rating(self):
        data = analysis_fixture()
        data["lenses"]["summary"]["audience"] = None
        data["lenses"]["claims"][0]["rating"] = None
        document, _ = render_reports(data)
        self.assertNotIn("Audience:", document)
        self.assertIn("Rating: —/5", document)
        data["lenses"] = {}
        render_reports(data)

    def test_timestamp_urls(self):
        for original in ("https://youtu.be/dQw4w9WgXcQ?t=100", "https://youtube.com/shorts/dQw4w9WgXcQ"):
            self.assertEqual(timestamp_url(original, 65.5), "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=65")
        self.assertEqual(timestamp_url("https://x.com/u/status/1?lang=en&t=2#x", 3),
                         "https://x.com/u/status/1?lang=en&t=3")

    def test_safe_links_and_generic_html(self):
        for url in ("javascript:alert(1)", "data:text/html,hello", "file:///etc/passwd", "https://[broken"):
            self.assertEqual(safe_url(url), "")
            self.assertEqual(timestamp_url(url, 0), "")
        self.assertEqual(generic("<img>"), "&lt;img&gt;")

    def test_invalid_transcript_is_rejected(self):
        for transcript in ([], {}, {"segments": "wrong"}, {"segments": [{"start": -1, "text": "x"}]},
                           {"segments": [{"start": float("nan"), "text": "x"}]},
                           {"segments": [{"start": 0, "text": {}}]}):
            with self.subTest(transcript=transcript), self.assertRaises(ValueError):
                render_reports(analysis_fixture(), transcript)

    def test_writes_report_and_merges_meta_without_mutating_analysis(self):
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            data = analysis_fixture()
            metadata = data.pop("video")
            raw = json.dumps(data)
            (run / "analysis.json").write_text(raw)
            (run / "meta.json").write_text(json.dumps(metadata))
            (run / "transcript.json").write_text(json.dumps({"segments": [{"start": 1, "text": "Transcript text"}]}))
            html_path, md_path = write_report(run)
            self.assertIn("Transcript text", html_path.read_text())
            self.assertIn("Transcript text", md_path.read_text())
            self.assertEqual((run / "analysis.json").read_text(), raw)

    def test_invalid_analysis_leaves_existing_reports_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            (run / "analysis.json").write_text('{}')
            (run / "report.html").write_text("previous")
            with self.assertRaises(ValidationError):
                write_report(run)
            self.assertEqual((run / "report.html").read_text(), "previous")
            self.assertFalse((run / "report.md").exists())
