"""2026-11-15 live defects; extractor errors retain their real prefixes/URLs."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from optparse import OptParseError
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from video_intel import acquisition as acq, cli, doctor, frames, validation
from video_intel.captions import parse_vtt
from video_intel.errors import VideoIntelError, is_network_error, map_error, with_retry
from video_intel.report import md, render_reports, time_link, write_report

YT = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
IG = 'https://www.instagram.com/reel/DX7lzTOJ1p6/'
TT = 'https://www.tiktok.com/@user/video/6748451240264420610'
VTT = 'WEBVTT\n\n00:01.000 --> 00:03.000\nHello\n'
CAP = {'source': 'captions-auto', 'model': None, 'language': 'en',
       'segments': [{'start': 1, 'end': 3, 'text': 'Hello'}]}
BLOCK = 'ERROR: [TikTok] 6748451240264420610: Your IP address is blocked from accessing this post'
LOGIN = 'ERROR: [Instagram] DX7lzTOJ1p6: Requested content is not available, rate-limit reached or login required'
PRIVATE = "ERROR: [youtube] dQw4w9WgXcQ: Private video. Sign in if you've been granted access to this video"


def analysis():
    claim = {'id': 'c1', 'claim_reviewed': 'Claim', 'quote': 'Quote', 't': 3, 'kind': 'fact',
             'verdict': 'true', 'rating': 5, 'confidence': 'high', 'rationale': 'Why', 'evidence': []}
    return {'schema_version': 1, 'video': {'id': 'dQw4w9WgXcQ', 'title': 'Title', 'webpage_url': YT,
            'platform': 'youtube', 'duration': 10}, 'transcript_source': 'captions-auto', 'asr_model': None,
            'lenses': {'claims': [claim]}, 'caveats': []}


class TestLiveErrors(unittest.TestCase):
    def test_extractor_ids_and_urls_are_not_http_statuses(self):
        for message in (
            'ERROR: [TikTok] 6748451240295024013: Video unavailable (https://www.tiktok.com/@x/video/6748451240295024013)',
            'ERROR: [youtube] 429_401_502_: Video unavailable (https://youtube.com/watch?v=429_401_502_)',
            'ERROR: [generic] 429: Unable to download webpage: https://example.org/429/401/502',
        ):
            with self.subTest(message=message):
                self.assertEqual(map_error(RuntimeError(message)).code, 'UNAVAILABLE')
                self.assertFalse(is_network_error(RuntimeError(message)))

    def test_http_statuses_and_retries_with_real_prefixes(self):
        for status, code in ((429, 'RATE_LIMITED'), (401, 'LOGIN_REQUIRED'), (502, 'UNAVAILABLE')):
            message = f'ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error {status} (https://www.youtube.com/watch?v=dQw4w9WgXcQ)'
            self.assertEqual(map_error(RuntimeError(message)).code, code)
            self.assertEqual(is_network_error(RuntimeError(message)), status != 401)
        operation = Mock(side_effect=[RuntimeError('ERROR: [TikTok] 6748451240264420610: Unable to download webpage: HTTP Error 503: Service Unavailable'), 'ok'])
        sleep = Mock()
        self.assertEqual(with_retry(operation, sleep_fn=sleep), 'ok')
        sleep.assert_called_once_with(1)

    def test_ip_block_and_geo_are_distinct(self):
        for message in (BLOCK, 'ERROR: [TikTok] 6748451240264420610: Access blocked (https://www.tiktok.com/@user/video/6748451240264420610)'):
            error = map_error(RuntimeError(message))
            self.assertEqual(error.code, 'BLOCKED')
            self.assertIn('network', str(error))
            self.assertIn('cookies', str(error))
        geo = RuntimeError('ERROR: [TikTok] 6748451240264420610: This video is not available in your country (https://www.tiktok.com/@user/video/6748451240264420610)')
        self.assertEqual(map_error(geo).code, 'UNAVAILABLE')

    def test_instagram_login_precedes_rate_limit(self):
        self.assertEqual(map_error(RuntimeError(LOGIN)).code, 'LOGIN_REQUIRED')
        self.assertFalse(is_network_error(RuntimeError(LOGIN)))

    def test_private_video_depends_on_cookie_opt_in(self):
        self.assertEqual(map_error(RuntimeError(PRIVATE)).code, 'UNAVAILABLE')
        self.assertEqual(map_error(RuntimeError(PRIVATE), cookies='chrome').code, 'LOGIN_REQUIRED')
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.side_effect = RuntimeError(PRIVATE)
        with patch.object(acq, '_youtube_dl', return_value=ydl), patch.object(acq, 'ydl_options', return_value={}):
            for cookies, code in ((None, 'UNAVAILABLE'), ('chrome', 'LOGIN_REQUIRED')):
                with self.assertRaises(VideoIntelError) as caught:
                    acq.fetch_metadata(YT, cookies)
                self.assertEqual(caught.exception.code, code)


class TestAcquisitionRegressions(unittest.TestCase):
    def test_no_audio_and_bestaudio_fallback(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {'id': 'DX7lzTOJ1p6', 'acodec': 'none', 'vcodec': 'avc1'}
        ydl.__enter__.return_value.prepare_filename.return_value = 'source.mp4'
        model = SimpleNamespace(transcribe=Mock())
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {'mlx_whisper': model}), \
                patch.object(acq, '_youtube_dl', return_value=ydl) as download:
            with self.assertRaises(VideoIntelError) as caught:
                acq.asr_transcript(IG, Path(root))
            self.assertEqual(caught.exception.code, 'NO_AUDIO')
            self.assertIn('--cookies-from-browser', str(caught.exception))
            self.assertIn('--frames', str(caught.exception))
            self.assertEqual(download.call_args.args[0]['format'], 'bestaudio/best')
            self.assertEqual(list(Path(root).iterdir()), [])
        model.transcribe.assert_not_called()

    def test_unknown_audio_is_probed_after_download(self):
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {'id': 'DX7lzTOJ1p6', 'formats': [{'acodec': 'aac'}]}
        ydl.__enter__.return_value.prepare_filename.return_value = 'source.mp4'
        with tempfile.TemporaryDirectory() as root, patch.object(acq, '_youtube_dl', return_value=ydl), \
                patch.object(acq.subprocess, 'run', return_value=SimpleNamespace(stdout='{"streams": []}')) as probe:
            with self.assertRaises(VideoIntelError) as caught:
                acq.asr_transcript(IG, Path(root))
            self.assertEqual(caught.exception.code, 'NO_AUDIO')
            self.assertEqual(probe.call_args.args[0][0], 'ffprobe')

    def test_frames_no_audio_continues_and_protocol_is_clean(self):
        with tempfile.TemporaryDirectory() as root:
            out, err = io.StringIO(), io.StringIO()
            def download(*args, **kwargs):
                print('[download] 100% of 1.23MiB')
                raise VideoIntelError('NO_AUDIO', 'platform served video without audio')
            def extract(run, **kwargs):
                self.assertTrue(run.name.startswith('.run-'))
                self.assertFalse(any(p.name.startswith('2026-') for p in Path(root).iterdir()))
                (run / 'frames.json').write_text('[]')
            with patch.object(acq, 'fetch_metadata', return_value={'id': 'DX7lzTOJ1p6', 'title': 'Reel'}), \
                    patch.object(acq, 'asr_transcript', side_effect=download), \
                    patch.object(frames, 'extract_frames', side_effect=extract), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(['fetch', IG, '--frames', '--asr', 'force', '--out', root])
            self.assertEqual(code, 0, err.getvalue() + out.getvalue())
            self.assertTrue(all(line.startswith(('OK ', 'FAIL ', 'Summary:')) for line in out.getvalue().splitlines()))
            self.assertIn('NO_AUDIO', err.getvalue())
            runs = list(Path(root).iterdir())
            self.assertEqual(len(runs), 1)
            value = json.loads((runs[0] / 'transcript.json').read_text())
            self.assertEqual((value['source'], value['segments']), ('none', []))
            self.assertTrue((runs[0] / 'frames.json').exists())

    def test_failed_fetch_removes_staging_directory(self):
        with tempfile.TemporaryDirectory() as root, patch.object(acq, 'fetch_metadata', return_value={'id': 'v'}), \
                patch.object(acq, 'asr_transcript', side_effect=RuntimeError(BLOCK)):
            with self.assertRaises(Exception):
                acq.fetch_video(TT, Path(root), asr='force')
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_failed_frames_fetch_never_publishes_run(self):
        with tempfile.TemporaryDirectory() as root, patch.object(acq, 'fetch_metadata', return_value={'id': 'v'}), \
                patch.object(acq, 'asr_transcript', return_value=CAP), \
                patch.object(frames, 'extract_frames', side_effect=RuntimeError(BLOCK)):
            with self.assertRaises(Exception):
                acq.fetch_video(TT, Path(root), asr='force', frames=True)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_original_language_and_unmatched_translations(self):
        tracks = {lang: [{'ext': 'vtt', 'data': VTT}] for lang in ('af', 'en', 'tr-orig')}
        self.assertIsNone(acq.ydl_captions({'automatic_captions': {'af': tracks['af']}}, ['de']))
        for info in ({'automatic_captions': tracks}, {'language': 'en', 'automatic_captions': tracks}):
            self.assertIn(acq.ydl_captions(info, [])['language'], ('tr-orig', 'en'))
        self.assertEqual(acq.ydl_captions({'language': 'en', 'automatic_captions': tracks}, [])['language'], 'en')
        with tempfile.TemporaryDirectory() as root, patch.object(acq, 'fetch_metadata', return_value={'id': 'dQw4w9WgXcQ', 'language': 'tr'}), \
                patch.object(acq, 'youtube_captions', return_value=CAP) as captions:
            acq.fetch_video(YT, Path(root))
            captions.assert_called_once_with('dQw4w9WgXcQ', ['tr'])

    def test_youtube_metadata_failure_still_tries_captions(self):
        message = 'ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error 403: Forbidden (https://www.youtube.com/watch?v=dQw4w9WgXcQ)'
        with tempfile.TemporaryDirectory() as root, patch.object(acq, 'fetch_metadata', side_effect=RuntimeError(message)), \
                patch.object(acq, 'youtube_captions', return_value=CAP) as captions:
            run = acq.fetch_video(YT, Path(root), asr='never')
            meta = json.loads((run / 'meta.json').read_text())
            self.assertEqual((meta['id'], meta['webpage_url'], meta['platform']), ('dQw4w9WgXcQ', YT, 'youtube'))
            captions.assert_called_once()

    def test_asr_progress_disabled_and_diagnostics_stderr(self):
        def transcribe(*args, **kwargs):
            self.assertIsNone(kwargs['verbose'])
            self.assertEqual(os.environ['HF_HUB_DISABLE_PROGRESS_BARS'], '1')
            self.assertEqual(os.environ['TQDM_DISABLE'], '1')
            print('Fetching 4 files: 100%')
            return {'language': 'en', 'segments': CAP['segments']}
        module = SimpleNamespace(transcribe=Mock(side_effect=transcribe))
        ydl = MagicMock()
        ydl.__enter__.return_value.extract_info.return_value = {'id': 'v', 'acodec': 'aac'}
        ydl.__enter__.return_value.prepare_filename.return_value = 'source.m4a'
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {'mlx_whisper': module}), \
                patch.object(acq, '_youtube_dl', return_value=ydl), patch.object(acq.subprocess, 'run'), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            acq.asr_transcript(IG, Path(root))
        self.assertEqual(out.getvalue(), '')
        self.assertIn('Fetching', err.getvalue())
        for key in ('quiet', 'noprogress', 'no_warnings'):
            self.assertTrue(acq.ydl_options()[key])

    def test_empty_output_environment_uses_home_default(self):
        with patch.dict(os.environ, {'VIDEO_INTEL_OUT': ''}), patch.object(cli, 'fetch_video', return_value=Path('run')) as fetch, contextlib.redirect_stdout(io.StringIO()):
            cli.main(['fetch', IG])
        self.assertEqual(fetch.call_args.args[1], Path.home() / 'video-reports')

    def test_invalid_cookie_spec_is_argparse_error(self):
        fake = SimpleNamespace(parse_options=Mock(side_effect=OptParseError('unsupported browser specified for cookies: "invalid"')))
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(sys.modules, {'yt_dlp': fake}), patch.object(cli, 'fetch_video') as fetch, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            cli.main(['fetch', IG, '--cookies-from-browser', 'invalid'])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn('--cookies-from-browser', err.getvalue())
        self.assertNotIn('LOGIN_REQUIRED', out.getvalue() + err.getvalue())
        fetch.assert_not_called()

    def test_doctor_impersonation_and_dependency_extras(self):
        with tempfile.TemporaryDirectory() as root, patch.object(doctor.importlib, 'import_module', side_effect=ImportError('curl_cffi missing')), \
                patch.object(doctor.subprocess, 'run', return_value=SimpleNamespace(stdout='ffmpeg version test\n')):
            result = doctor.diagnose(root)
        check = next(c for c in result['checks'] if c['name'] == 'impersonation')
        self.assertFalse(check['ok'])
        self.assertIn('yt-dlp[default,curl-cffi]>=2026.10.26', check['fix'])
        project = (Path(__file__).parents[1] / 'pyproject.toml').read_text()
        self.assertIn('yt-dlp[default,curl-cffi]>=2026.10.26', project)
        self.assertIn('dev = ["pytest>=8"]', project)


class TestReportRegressions(unittest.TestCase):
    def test_rolling_vtt_cues_are_deduplicated(self):
        payload = (Path(__file__).parent / 'fixtures' / 'youtube_rolling.vtt').read_text()
        segments = parse_vtt(payload)
        self.assertEqual([s['text'] for s in segments], ['THE SERGEANT AT ARMS: MADAM', 'SPEAKER, THE VICE PRESIDENT AND'])
        self.assertEqual([s['start'] for s in segments], [234.333, 235.334])
        # Independent cues separated by silence must keep repeated speech.
        self.assertEqual(len(parse_vtt(VTT + '\n00:10.000 --> 00:12.000\nHello\n')), 2)

    def test_only_youtube_timestamps_are_linked(self):
        for url in (IG, TT, 'https://x.com/u/status/6748451240264420610'):
            self.assertNotIn('<a ', time_link(12, url))
            self.assertEqual(time_link(12, url, True), '00:12')
        self.assertIn('&t=12', time_link(12, YT, True))

    def test_unique_claim_ids_and_duration_bounds(self):
        data = analysis()
        data['lenses']['claims'].append(copy.deepcopy(data['lenses']['claims'][0]))
        with self.assertRaisesRegex(validation.ValidationError, 'duplicate'):
            validation.validate_analysis(data)
        for lens in ({'moments': [{'t': 11, 'title': 'Late', 'note': 'Late'}]}, {'future': {'nested': [{'t': 11}]}}):
            data = analysis()
            data['lenses'].update(lens)
            with self.assertRaisesRegex(validation.ValidationError, 'duration'):
                validation.validate_analysis(data)
        data = analysis()
        data['lenses']['claims'][0]['t'] = 10
        validation.validate_analysis(data)
        data['video']['duration'] = None
        data['lenses']['claims'][0]['t'] = 1000
        validation.validate_analysis(data)

    def test_metadata_wins_over_analysis_video(self):
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            data = analysis()
            meta = {'title': 'Real title', 'webpage_url': IG, 'platform': 'instagram', 'id': 'DX7lzTOJ1p6', 'duration': 2}
            (run / 'analysis.json').write_text(json.dumps(data))
            (run / 'meta.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(validation.ValidationError, 'duration'):
                write_report(run)
            meta['duration'] = 10
            (run / 'meta.json').write_text(json.dumps(meta))
            with patch('video_intel.report.render_reports', return_value=('html', 'md')) as render:
                write_report(run)
            for key, value in meta.items():
                self.assertEqual(render.call_args.args[0]['video'][key], value)

    def test_shipped_schemas_never_silently_ignore_keywords(self):
        for name in ('analysis', 'compare'):
            schema = json.loads((Path(__file__).parents[1] / 'video_intel' / 'schema' / f'{name}.schema.json').read_text())
            validation.validate_schema_definition(schema)
        with self.assertRaisesRegex(ValueError, 'oneOf'):
            validation.validate_schema_definition({'type': 'string', 'oneOf': [{'const': 'x'}]})

    def test_markdown_block_markers_and_heading_newlines(self):
        for value in ('> quote', '= heading', '---', 'text\n==='):
            escaped = md(value)
            self.assertFalse(any(line.startswith(('>', '=', '---')) for line in escaped.splitlines()))
        data = analysis()
        data['video']['title'] = 'Title\nInjected'
        data['lenses']['future\nInjected'] = {}
        data['lenses']['claims'][0]['claim_reviewed'] = 'Claim\nInjected'
        _, markdown = render_reports(data)
        self.assertIn('# Title Injected\n', markdown)
        self.assertIn('## future Injected\n', markdown)
        self.assertIn('### Claim Injected\n', markdown)

class TestSharedRetryOrder(unittest.TestCase):
    def test_transcript_network_subclasses_retry_before_terminal_base(self):
        # Model the library's actual inheritance: both retryable errors inherit
        # CouldNotRetrieveTranscript and must precede that handler.
        fake = SimpleNamespace()
        fake.CouldNotRetrieveTranscript = type('CouldNotRetrieveTranscript', (Exception,), {})
        for name in ('NoTranscriptFound', 'RequestBlocked', 'TranscriptsDisabled', 'VideoUnavailable', 'YouTubeRequestFailed'):
            setattr(fake, name, type(name, (fake.CouldNotRetrieveTranscript,), {}))
        fake.YouTubeTranscriptApi = Mock()
        source = Path(__file__).parents[1] / 'youtube_transcript' / 'transcript.py'
        spec = importlib.util.spec_from_file_location('_retry_order_regression', source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'youtube_transcript_api': fake, spec.name: module}):
            spec.loader.exec_module(module)
            for error_type in (fake.RequestBlocked, fake.YouTubeRequestFailed):
                with self.subTest(error_type=error_type.__name__):
                    client = SimpleNamespace(list=Mock(side_effect=error_type(
                        'ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error 429: Too Many Requests (https://www.youtube.com/watch?v=dQw4w9WgXcQ)')))
                    sleep = Mock()
                    with self.assertRaisesRegex(module.TranscriptError, 'after retries'):
                        module.fetch_transcript_with_retry('dQw4w9WgXcQ', [], True, api=client, sleep_fn=sleep)
                    self.assertEqual(client.list.call_count, 3)
                    self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])
            client = SimpleNamespace(list=Mock(side_effect=fake.TranscriptsDisabled('disabled')))
            sleep = Mock()
            with self.assertRaisesRegex(module.TranscriptError, 'disabled'):
                module.fetch_transcript_with_retry('dQw4w9WgXcQ', [], True, api=client, sleep_fn=sleep)
            client.list.assert_called_once()
            sleep.assert_not_called()


class TestFrameTransactions(unittest.TestCase):
    def test_frames_fallback_and_publish_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            (run / 'meta.json').write_text(json.dumps({'webpage_url': IG}))
            (run / 'frames').mkdir()
            image = run / 'frames' / '0000.00.jpg'
            image.write_bytes(b'previous')
            manifest = '[{"t": 0, "path": "frames/0000.00.jpg"}]'
            (run / 'frames.json').write_text(manifest)
            def download(options):
                self.assertEqual(options['format'], 'worst*[height>=360][vcodec!=none]/worst*[vcodec!=none]')
                ydl = MagicMock()
                ydl.__enter__.return_value.extract_info.return_value = {'id': 'DX7lzTOJ1p6', 'ext': 'mp4'}
                ydl.__enter__.return_value.prepare_filename.return_value = str(run / 'source.mp4')
                return ydl
            def extract(command, **kwargs):
                self.assertEqual(image.read_bytes(), b'previous')
                Path(command[-1] % 1).write_bytes(b'new')
                return SimpleNamespace(stderr='[Parsed_showinfo_2 @ 0x1] n: 0 pts: 0 pts_time:0')
            original_replace = Path.replace
            def fail_manifest(path, destination):
                if path.name == 'frames.json':
                    raise OSError('disk full')
                return original_replace(path, destination)
            with patch.object(frames, '_youtube_dl', side_effect=download), \
                    patch.object(frames.subprocess, 'run', side_effect=extract), \
                    patch.object(Path, 'replace', fail_manifest), self.assertRaisesRegex(OSError, 'disk full'):
                frames.extract_frames(run)
            self.assertEqual(image.read_bytes(), b'previous')
            self.assertEqual((run / 'frames.json').read_text(), manifest)
            self.assertFalse(list(run.glob('.video-*')))

    def test_rename_failure_cleans_run_reservation_and_staging(self):
        with tempfile.TemporaryDirectory() as root, patch.object(acq, 'fetch_metadata', return_value={'id': 'v'}), \
                patch.object(acq, 'asr_transcript', return_value=CAP), \
                patch.object(Path, 'replace', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                acq.fetch_video(IG, Path(root), asr='force')
            self.assertEqual(list(Path(root).iterdir()), [])

class TestExpansionBoundsAndProtocol(unittest.TestCase):
    def test_frame_times_respect_duration(self):
        with self.assertRaisesRegex(ValueError, 'duration'):
            render_reports(analysis(), frames=[{'t': 11, 'path': 'frames/0011.00.jpg'}])

    def test_compare_times_use_referenced_metadata_duration(self):
        from video_intel.compare import render_compare
        with tempfile.TemporaryDirectory() as root:
            run = Path(root)
            (run / 'meta.json').write_text(json.dumps({'webpage_url': IG, 'duration': 10}))
            data = {'schema_version': 1, 'topic': 'Compare', 'videos': [
                {'id': 'v1', 'title': 'One', 'creator': 'Author', 'run_dir': '.'},
                {'id': 'v2', 'title': 'Two', 'creator': 'Author', 'run_dir': '.'}],
                'common_claims': [], 'contradictions': [], 'who_says_what': [],
                'unique_points': [{'id': 'v1', 't': 11, 'point': 'Late'}], 'verdict_overall': 'Summary'}
            with self.assertRaisesRegex(validation.ValidationError, 'duration'):
                render_compare(data, run)

    def test_doctor_normal_output_preserves_protocol(self):
        result = {'ok': False, 'checks': [{'name': 'impersonation', 'ok': False,
                  'detail': 'curl_cffi\nmissing', 'fix': 'install curl_cffi'}]}
        out, err = io.StringIO(), io.StringIO()
        def diagnose():
            print('library import diagnostic')
            return result
        with patch.object(doctor, 'diagnose', side_effect=diagnose), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(['doctor']), 1)
        self.assertEqual(out.getvalue(), 'FAIL impersonation: curl_cffi missing\n')
        self.assertIn('library import diagnostic', err.getvalue())
        self.assertIn('Fix impersonation:', err.getvalue())
