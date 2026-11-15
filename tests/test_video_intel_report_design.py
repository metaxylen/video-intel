"""Offline report presentation contracts, using parsed HTML rather than screenshots."""

import copy
import hashlib
import base64
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from video_intel.compare import render_compare
from video_intel.presentation import CSS, LABELS, SCRIPT, VERDICTS
from video_intel.report import render_reports, write_report
from video_intel.validation import ValidationError, validate_analysis, validate_compare


URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


def analysis():
    return {'schema_version': 1, 'video': {'title': 'Gerçek rapor', 'webpage_url': URL},
            'transcript_source': 'captions-auto', 'asr_model': None, 'caveats': [],
            'lenses': {'summary': {'tldr': 'Bak [01:09] ve [1:02:03].',
                                   'key_points': ['Bir bulgu.'], 'audience': None},
                       'claims': [{'id': 'c1', 'claim_reviewed': 'Bir iddia', 'quote': 'Alıntı',
                                   't': 69, 'kind': 'fact', 'confidence': 'medium', 'verdict': 'half-true',
                                   'rating': 3, 'rationale': 'Gerekçe.', 'evidence': []}]}}


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements, self.links, self.text = [], [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == 'a':
            self.links.append(attrs.get('href'))

    def handle_data(self, data):
        self.text.append(data)

    def select(self, tag, key=None, value=None):
        return [attrs for name, attrs in self.elements if name == tag and
                (key is None or (key in attrs and (value is None or attrs[key] == value)))]


class TestReportDesign(unittest.TestCase):
    def test_language_precedence_and_unsupported_fallback(self):
        for explicit, transcript_language, expected in (
            ('tr', 'en', 'tr'), ('en', 'tr', 'en'), (None, 'tr', 'tr'),
            (None, 'en', 'en'), (None, 'de', 'en'), (None, None, 'en'),
            (None, ['tr'], 'en'),
        ):
            with self.subTest(explicit=explicit, transcript_language=transcript_language):
                data = analysis()
                if explicit:
                    data['report_language'] = explicit
                doc, markdown = render_reports(data, {'language': transcript_language, 'segments': []})
                parsed = Document(doc)
                self.assertEqual(parsed.select('html')[0]['lang'], expected)
                for key in ('summary', 'claims', 'copy', 'print', 'half-true', 'fact', 'confidence', 'medium'):
                    self.assertIn(LABELS[expected][key], doc)
                self.assertIn('## ' + LABELS[expected]['summary'], markdown)

    def test_language_schema_optional_and_restricted(self):
        validate_analysis(analysis())
        for language in ('tr', 'en'):
            validate_analysis(dict(analysis(), report_language=language))
        for invalid in ('de', '', None, 1, ['tr']):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_analysis(dict(analysis(), report_language=invalid))

    def test_every_interface_label_has_both_languages(self):
        self.assertFalse(set(LABELS['en']) - set(LABELS['tr']))

    def test_verdict_bar_counts_order_and_filter_buttons(self):
        data = analysis()
        template = data['lenses']['claims'][0]
        verdicts = list(reversed(VERDICTS[:-1])) + ['false', 'false']
        data['lenses']['claims'] = [dict(template, id=f'c{i}', verdict=v) for i, v in enumerate(verdicts)]
        doc = Document(render_reports(data)[0])
        segments = doc.select('button', 'class', 'verdict-segment')
        self.assertEqual([v['data-filter-verdict'] for v in segments], list(VERDICTS[:-1]))
        self.assertEqual([int(v['data-count']) for v in segments], [3, 1, 1, 1, 1, 1, 1])
        for segment in segments:
            verdict, count = segment['data-filter-verdict'], segment['data-count']
            self.assertIn(f'--count:{count};', segment['style'])
            self.assertEqual(segment['aria-label'], f'{LABELS["en"][verdict]}: {count}')
            self.assertEqual(segment['aria-pressed'], 'false')
            self.assertEqual(len(doc.select('button', 'data-filter-verdict', verdict)), 3)

    def test_truth_meter_and_quiet_metadata(self):
        doc, _ = render_reports(analysis())
        # The Markdown payload deliberately retains the rating; inspect just the visible card.
        card = doc.split('<article data-claim', 1)[1].split('</article>', 1)[0]
        parsed = Document(card)
        self.assertEqual(len(parsed.select('i', 'class', 'filled')), 3)
        self.assertIn('aria-label="Rating: 3/5"', card)
        meta = re.search(r'<p class="claim-meta">(.*?)</p>', card, re.S).group(1)
        self.assertNotIn('c1', meta)
        self.assertNotIn('Rating', meta)
        self.assertIn('Fact · Confidence: Medium', meta)
        for verdict in ('not-checkable', 'not-enough-evidence'):
            data = analysis()
            data['lenses']['claims'][0].update(verdict=verdict, rating=5)
            card = render_reports(data)[0].split('<article data-claim', 1)[1].split('</article>', 1)[0]
            self.assertEqual(len(Document(card).select('i')), 5)
            self.assertEqual(len(Document(card).select('i', 'class', 'filled')), 0)

    def test_timestamps_link_only_to_youtube(self):
        for url, linked in ((URL, True), ('https://youtu.be/dQw4w9WgXcQ', True),
                            ('https://x.com/u/status/1', False), ('https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ', False)):
            data = analysis()
            data['video']['webpage_url'] = url
            data['lenses']['future'] = {'note': '[02:03] <script>unsafe</script>'}
            data['lenses']['claims'][0]['rationale'] = 'Başka an [00:47]'
            parsed = Document(render_reports(data)[0])
            for seconds in (69, 3723, 123, 47):
                self.assertEqual(f'{URL}&t={seconds}' in parsed.links, linked)
            self.assertNotIn('unsafe', [a.get('src') for a in parsed.select('script')])
            self.assertIn('[01:09]', ''.join(parsed.text))

    def test_timestamp_escaping_and_invalid_timestamps(self):
        data = analysis()
        data['lenses']['summary']['tldr'] = '<img src=x onerror="bad()"> [00:04] [00:99] [1:60:01]'
        doc = Document(render_reports(data)[0])
        self.assertFalse(doc.select('img'))
        self.assertIn(URL + '&t=4', doc.links)
        self.assertIn('[00:99]', ''.join(doc.text))
        self.assertIn('[1:60:01]', ''.join(doc.text))

    def test_transcript_collapsed_searchable_and_after_title(self):
        transcript = {'language': 'tr', 'segments': [{'start': 0, 'text': 'Aranacak sözler'}]}
        html, _ = render_reports(analysis(), transcript)
        parsed = Document(html)
        self.assertNotIn('open', parsed.select('details', 'id', 'full-transcript')[0])
        self.assertEqual(parsed.select('input', 'id', 'transcript-search')[0]['type'], 'search')
        self.assertEqual(len(parsed.select('p', 'data-transcript-segment')), 1)
        visible_body = html.split('<body>', 1)[1]
        self.assertLess(visible_body.index('<h1>'), visible_body.index('data-copy-markdown'))
        self.assertLess(visible_body.index('<h1>'), visible_body.index('<nav'))
        self.assertIn('Transkriptin tamamını oku', html)

    def test_no_external_resources_and_hashed_script(self):
        html, _ = render_reports(analysis())
        parsed = Document(html)
        self.assertEqual(len(parsed.select('script')), 1)
        self.assertFalse(parsed.select('script', 'src'))
        self.assertFalse(parsed.select('link'))
        csp = parsed.select('meta', 'http-equiv', 'Content-Security-Policy')[0]['content']
        self.assertIn("default-src 'none'", csp)
        self.assertIn("connect-src 'none'", csp)
        self.assertIn('sha256-' + base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode(), csp)
        self.assertIn('@media print', html)
        self.assertIn('prefers-reduced-motion', html)
        self.assertIn(':focus-visible', html)

    def test_frame_data_is_self_contained_and_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            (run / 'analysis.json').write_text(json.dumps(analysis()))
            (run / 'frames').mkdir()
            frame = run / 'frames/0012.00.jpg'
            frame.write_bytes(b'\xff\xd8\xff\xd9')
            (run / 'frames.json').write_text(json.dumps([{'t':12, 'path':'frames/0012.00.jpg'}]))
            html = write_report(run)[0].read_text()
            image = Document(html).select('img')[0]
            self.assertEqual(image['src'], 'data:image/jpeg;base64,/9j/2Q==')
            self.assertEqual(image['loading'], 'lazy')
            self.assertEqual((image['width'], image['height']), ('512', '288'))
            frame.unlink()
            frame.symlink_to(Path(root).parent / 'outside.jpg')
            with self.assertRaisesRegex(ValueError, 'inside the run'):
                write_report(run)

    def test_palette_text_contrast_in_both_themes(self):
        def luminance(color):
            if len(color) == 4:
                color = "#" + "".join(c * 2 for c in color[1:])
            rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
            return sum(x * w for x, w in zip(linear, (.2126, .7152, .0722)))
        light, dark = re.findall(r':root\s*\{([^}]+)\}', CSS)[:2]
        for theme, block in (('light', light), ('dark', dark)):
            colors = dict(re.findall(r'--([\w-]+):(#\w+)', block))
            for foreground in ('ink', 'muted', 'accent', *VERDICTS):
                for background in ('bg', 'surface'):
                    values = sorted([luminance(colors[foreground]), luminance(colors[background])])
                    contrast = (values[1] + .05) / (values[0] + .05)
                    with self.subTest(theme=theme, foreground=foreground, background=background):
                        self.assertGreaterEqual(contrast, 4.5)


class TestCompareDesign(unittest.TestCase):
    def test_compare_localization_fallback_schema_and_reference_timestamps(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            videos = []
            for i, url in enumerate((URL, 'https://x.com/u/status/1')):
                run = base / f'run{i}'
                run.mkdir()
                (run / 'meta.json').write_text(json.dumps({'webpage_url': url}))
                (run / 'transcript.json').write_text(json.dumps({'language': 'tr', 'segments': []}))
                videos.append({'id':f'v{i}', 'run_dir':str(run), 'title':'Video', 'creator':'Üretici'})
            data = {'schema_version':1, 'topic':'Ortak konu', 'videos': videos,
                    'common_claims':[{'claim':'Ortak iddia', 'videos':[{'id':'v0','t':4}, {'id':'v1','t':4}],
                                      'verdict':'not-checked', 'note':'Araştırılmadı'}],
                    'contradictions':[], 'unique_points':[], 'who_says_what':[], 'verdict_overall':'Sonuç'}
            for explicit, expected in ((None, 'tr'), ('tr', 'tr'), ('en', 'en')):
                sample = copy.deepcopy(data)
                if explicit:
                    sample['report_language'] = explicit
                validate_compare(sample)
                html, markdown = render_compare(sample, base)
                self.assertEqual(Document(html).select('html')[0]['lang'], expected)
                for key in ('common_claims', 'contradictions', 'who_says_what', 'unique_points', 'overall', 'not-checked', 'copy', 'print'):
                    self.assertIn(LABELS[expected][key], html)
                self.assertIn('## ' + LABELS[expected]['common_claims'], markdown)
                self.assertIn(URL + '&t=4', Document(html).links)
                self.assertNotIn('https://x.com/u/status/1&t=4', Document(html).links)
            for invalid in ('de', None, 1):
                with self.assertRaises(ValidationError):
                    validate_compare(dict(data, report_language=invalid))
