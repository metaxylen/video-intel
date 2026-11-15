"""Offline expansion regressions: subprocess/yt-dlp are mocked throughout."""

import contextlib
import copy
import hashlib
import base64
import io
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from importlib.metadata import PackageNotFoundError
from unittest.mock import MagicMock, Mock, patch

import pytest

from video_intel import acquisition as acq, cli, doctor, frames
from video_intel.compare import render_compare, write_compare
from video_intel.errors import VideoIntelError
from video_intel.report import SCRIPT, render_reports, write_report
from video_intel.validation import ValidationError, validate_analysis, validate_compare
from video_intel.window import parse_time, focus_window

URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


def analysis(lenses=None):
    return {'schema_version': 1, 'video': {'title': 'A video', 'webpage_url': URL},
            'transcript_source': 'captions-manual', 'asr_model': None, 'lenses': lenses or {}, 'caveats': []}


LENSES = {
    'steps': {'goal': 'Build it', 'prerequisites': ['Python'], 'steps': [
        {'t': 12, 'action': 'Run command', 'tools': ['terminal'], 'command': 'echo "<hello>"', 'warning': 'Verify flags'}], 'outcome': 'It runs'},
    'mentions': [{'name': 'Python', 'type': 'tool', 't': 12, 'context': 'Used for code', 'sentiment': 'positive',
                  'url': 'https://python.org', 'retrieved': '2026-11-15', 'verified': True}],
    'sources': [{'cited_as': 'A study', 't': 12, 'what_is_claimed': 'It works', 'specificity': 'named',
                 'found': True, 'url': 'https://example.org', 'publisher': 'Publisher', 'published': None,
                 'retrieved': '2026-11-15', 'supports': 'partly', 'note': 'Limited sample'}],
    'actions': [{'id': 'a1', 't': 12, 'action': 'Try Python', 'why': 'Useful', 'effort': 'minutes', 'priority': 'high', 'depends_on': None}],
    'tone': {'overall': {'descriptors': ['calm'], 'note': 'Measured'}, 'shifts': [{'t': 12, 'from': 'calm', 'to': 'urgent', 'note': 'Faster'}],
             'techniques': [{'t': 12, 'technique': 'urgency', 'quote': 'Act now', 'note': 'Time limit'}],
             'bias_signals': [{'t': 12, 'signal': 'One sided', 'note': 'No alternative'}],
             'disclosure': {'sponsored': 'unknown', 'affiliate': 'likely', 'disclosed': None, 'evidence': [{'t': 12, 'quote': 'Link below'}]}},
    'hook': {'hook': {'t_end': 3, 'type': 'question', 'spoken': None, 'on_screen': 'Why?', 'rating': 4, 'why': 'Curiosity'},
             'structure': [{'part': 'hook', 't_start': 0, 't_end': 3, 'summary': 'Opening question'}],
             'pacing': {'duration': 30, 'cuts_per_10s': 2, 'words_per_minute': None, 'note': 'Estimate'},
             'on_screen_text': [{'t': 12, 'text': 'Try it', 'role': 'cta'}],
             'retention': [{'t': 12, 'tactic': 'Open loop', 'note': 'Wait for result'}], 'why_it_works': ['Curiosity gap'],
             'template': {'name': 'Question first', 'slots': [{'part': 'hook', 'instruction': 'Ask', 'example': 'Why?'}], 'length_s': 30}, 'weaknesses': ['Slow middle']},
}


def run_cli(args):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize('raw,expected', [('12.34', 12.34), ('01:02.5', 62.5), ('01:02:03', 3723)])
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


@pytest.mark.parametrize('raw', ['-1', 'nan', 'inf', '1:60', '1:2:3:4', 'abc', ''])
def test_invalid_time(raw):
    with pytest.raises(ValueError):
        parse_time(raw)


@pytest.mark.parametrize('start,end', [(10, 10), (20, 10), (-1, None), (float('nan'), None), (0, float('inf'))])
def test_invalid_window(start, end):
    with pytest.raises(ValueError):
        focus_window(start, end)


def test_file_parsing_reuses_shared_loader(tmp_path):
    path = tmp_path / 'urls.txt'
    path.write_text('\ufeff# ignored\n\n https://x.com/u/status/1 \n# more\nhttps://vimeo.com/2\n')
    with patch.object(cli, 'fetch_video', return_value=Path('run')) as fetch:
        code, out, _ = run_cli(['fetch', URL, '--file', str(path)])
    assert code == 0
    assert [c.args[0] for c in fetch.call_args_list] == [URL, 'https://x.com/u/status/1', 'https://vimeo.com/2']
    assert '3 succeeded' in out


@pytest.mark.parametrize('contents', ['', '# comments only\n'])
def test_empty_file(tmp_path, contents):
    path = tmp_path / 'urls.txt'
    path.write_text(contents)
    assert run_cli(['fetch', '--file', str(path)])[0] == 1


def test_missing_file_and_invalid_window_never_fetch(tmp_path):
    with patch.object(cli, 'fetch_video') as fetch:
        assert run_cli(['fetch', '--file', str(tmp_path/'missing')])[0] == 1
        assert run_cli(['fetch', URL, '--start', '10', '--end', '5'])[0] == 1
        fetch.assert_not_called()


def test_cli_fetch_window_and_frames():
    with patch.object(cli, 'fetch_video', return_value=Path('run')) as fetch:
        assert run_cli(['fetch', URL, '--start', '01:00', '--end', '01:30', '--frames'])[0] == 0
    assert {k:fetch.call_args.kwargs[k] for k in ('start','end','frames')} == {'start':60,'end':90,'frames':True}


def test_caption_window_and_frame_dispatch(tmp_path):
    captions = {'source':'captions-manual','model':None,'language':'en','segments':[
        {'start':1,'end':5,'text':'before'}, {'start':9,'end':13,'text':'overlap'},
        {'start':15,'end':25,'text':'inside'}, {'start':30,'end':35,'text':'after'}]}
    with patch.object(acq, 'fetch_metadata', return_value={'id':'v','title':'Test'}), \
            patch.object(acq, 'youtube_captions', return_value=captions), \
            patch.object(frames, 'extract_frames') as extract:
        run = acq.fetch_video(URL,tmp_path,start=10,end=20,frames=True)
    value = json.loads((run/'transcript.json').read_text())
    assert value['window'] == {'start':10,'end':20}
    assert [(s['start'],s['end']) for s in value['segments']] == [(10,13),(15,20)]
    assert 'before' not in (run/'transcript.md').read_text()
    assert '[00:10]' in (run/'transcript.md').read_text()
    extract.assert_called_once_with(run,cookies=None)
    assert captions['segments'][1]['start'] == 9  # No mutation of shared caption data.


def test_asr_window_is_sliced_and_rebased(tmp_path):
    module = SimpleNamespace(transcribe=Mock(return_value={'language':'en','segments':[{'start':1,'end':4,'text':'Slice'}]}))
    ydl = MagicMock()
    ydl.__enter__.return_value.extract_info.return_value = {'id':'v'}
    ydl.__enter__.return_value.prepare_filename.return_value = str(tmp_path/'audio.m4a')
    with patch.dict(sys.modules, {'mlx_whisper':module}), patch.object(acq,'_youtube_dl',return_value=ydl), \
            patch.object(acq.subprocess,'run',return_value=None) as ffmpeg:
        result = acq.asr_transcript(URL,tmp_path,window={'start':60,'end':90})
    command = ffmpeg.call_args.args[0]
    assert command[command.index('-ss')+1] == '60'
    assert command[command.index('-to')+1] == '90'
    assert result['segments'][0] == {'start':61,'end':64,'text':'Slice'}
    assert not list(tmp_path.glob('.audio-*'))


@pytest.fixture
def frame_run(tmp_path):
    (tmp_path/'meta.json').write_text(json.dumps({'webpage_url':URL}))
    (tmp_path/'transcript.json').write_text(json.dumps({'window':{'start':10,'end':30}}))
    return tmp_path


def mock_frame_download(options):
    ydl = MagicMock()
    client = ydl.__enter__.return_value
    video = Path(options['outtmpl'].replace('%(ext)s','mp4'))
    video.write_bytes(b'video')
    client.extract_info.return_value = {'id':'v','ext':'mp4'}
    client.prepare_filename.return_value = str(video)
    return ydl


def mock_ffmpeg(command, **kwargs):
    pattern = command[-1]
    for i in range(1,4):
        Path(pattern % i).write_bytes(b'jpeg')
    return SimpleNamespace(stderr='[showinfo] n: 0 pts: 0 pts_time:0\n[showinfo] n: 1 pts: 0 pts_time:2.34\n[showinfo] n: 2 pts: 0 pts_time:7.8\n')


@pytest.mark.parametrize('keep', [True, False])
def test_frames_build_names_and_cleanup(frame_run, keep):
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download) as download, \
            patch.object(frames.subprocess,'run',side_effect=mock_ffmpeg) as ffmpeg:
        records = frames.extract_frames(frame_run,max_frames=3,every=5,keep_video=keep)
    assert records == [{'t':10.0,'path':'frames/0010.00.jpg'},{'t':12.34,'path':'frames/0012.34.jpg'},{'t':17.8,'path':'frames/0017.80.jpg'}]
    assert json.loads((frame_run/'frames.json').read_text()) == records
    assert all((frame_run/r['path']).exists() for r in records)
    options = download.call_args.args[0]
    assert options['format'] == 'worst*[height>=360][vcodec!=none]'
    assert options['format_sort'] == ['height', 'tbr'] and options['format_sort_force']
    assert 'cookiesfrombrowser' not in options
    command = ffmpeg.call_args.args[0]
    vf = command[command.index('-vf')+1]
    assert 'gt(scene,0.3)' in vf and 'gte(t-prev_selected_t,5)' in vf and 'scale=512:-2' in vf
    assert command[command.index('-frames:v')+1] == '3'
    assert command[command.index('-ss')+1] == '10'
    assert command[command.index('-to')+1] == '30'
    assert bool(list(frame_run.glob('.video-*/source.mp4'))) == keep


@pytest.mark.parametrize('failure', [FileNotFoundError(), subprocess.CalledProcessError(1,['ffmpeg']), subprocess.TimeoutExpired(['ffmpeg'],600)])
def test_frames_error_cleanup(frame_run, failure):
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download), \
            patch.object(frames.subprocess,'run',side_effect=failure), pytest.raises(VideoIntelError):
        frames.extract_frames(frame_run,keep_video=True)
    assert not list(frame_run.glob('.video-*'))
    assert not (frame_run/'frames.json').exists()


@pytest.mark.parametrize('options', [{'max_frames':0},{'max_frames':-1},{'every':0},{'every':float('nan')},{'every':float('inf')}])
def test_frames_reject_invalid_options(frame_run, options):
    with patch.object(frames,'_youtube_dl') as download, pytest.raises(ValueError):
        frames.extract_frames(frame_run,**options)
    download.assert_not_called()


def test_frames_cli(frame_run):
    with patch.object(frames,'extract_frames',return_value=[{'t':0,'path':'frames/0000.00.jpg'}]) as extract:
        assert run_cli(['frames',str(frame_run),'--max-frames','2','--every','8','--keep-video'])[0] == 0
    extract.assert_called_once_with(frame_run,2,8.0,True)


def test_frames_report_strip(tmp_path):
    (tmp_path/'analysis.json').write_text(json.dumps(analysis()))
    (tmp_path/'frames.json').write_text(json.dumps([{'t':12.34,'path':'frames/0012.34.jpg'}]))
    document = write_report(tmp_path)[0].read_text()
    assert 'src="frames/0012.34.jpg"' in document and 'loading="lazy"' in document
    assert '&amp;t=12' in document


@pytest.mark.parametrize('path', ['../secret.jpg','https://evil.test/a.jpg','/tmp/0000.00.jpg','frames/x.jpg','frames/../0000.00.jpg'])
def test_unsafe_frame_paths_rejected(path):
    with pytest.raises(ValueError):
        render_reports(analysis(),frames=[{'t':0,'path':path}])


@pytest.mark.parametrize('name', list(LENSES))
def test_new_lens_validates_and_renders(name):
    from video_intel.lenses import TITLES
    data = analysis({name:LENSES[name]})
    validate_analysis(data)
    document, markdown = render_reports(data)
    assert TITLES[name] in document and TITLES[name] in markdown
    assert '<dl>' not in document
    if name != 'hook':
        assert '&amp;t=12' in document and '&t=12' in markdown
    else:
        assert 'Reusable template' in document and 'On-screen text' in markdown


@pytest.mark.parametrize('name', list(LENSES))
def test_new_lens_invalid_shapes_rejected(name):
    data = analysis({name:LENSES[name]})
    data = copy.deepcopy(data)
    lens = data['lenses'][name]
    del (lens[0] if isinstance(lens,list) else lens)[next(iter(lens[0] if isinstance(lens,list) else lens))]
    with pytest.raises(ValidationError):
        validate_analysis(data)


@pytest.mark.parametrize('name,key,value', [('mentions','verified',1),('mentions','type','website'),('sources','found','yes'),('sources','supports','true'),('actions','effort','weeks'),('actions','depends_on','missing')])
def test_lens_invalid_field_values(name,key,value):
    lens = copy.deepcopy(LENSES[name])
    lens[0][key] = value
    with pytest.raises(ValidationError):
        validate_analysis(analysis({name:lens}))


def test_cyclic_actions_rejected():
    lens = copy.deepcopy(LENSES['actions'])
    lens[0]['depends_on'] = 'a1'
    with pytest.raises(ValidationError):
        validate_analysis(analysis({'actions':lens}))


@pytest.fixture
def comparison(tmp_path):
    for name,url in [('run one',URL),('run-two','https://x.com/u/status/1')]:
        run = tmp_path/name
        run.mkdir()
        (run/'meta.json').write_text(json.dumps({'webpage_url':url}))
        (run/'report.html').write_text('report')
    return {'schema_version':1,'topic':'Shared topic','videos':[
        {'id':'v1','run_dir':'run one','title':'Video one','creator':'Author one'},
        {'id':'v2','run_dir':str(tmp_path/'run-two'),'title':'Video two','creator':'Author two'}],
        'common_claims':[{'claim':'Shared claim','videos':[{'id':'v1','t':12},{'id':'v2','t':20}], 'verdict':'not-checked','note':'Not researched'}],
        'contradictions':[{'topic':'Different numbers','positions':[{'id':'v1','t':12,'says':'Ten'},{'id':'v2','t':20,'says':'Twenty'}],
                           'resolution':'unclear','evidence':[{'url':'https://example.org','publisher':'A source','retrieved':'2026-11-15','snippet':'Limited evidence'}]}],
        'who_says_what':[{'point':'A point','stances':[{'id':'v1','stance':'supports','t':12,'note':'Yes'}, {'id':'v2','stance':'silent','t':None,'note':'Not discussed'}]}],
        'unique_points':[{'id':'v1','t':40,'point':'Unique idea'}], 'verdict_overall':'Both help in different ways'}


def test_compare_schema_and_render(tmp_path, comparison):
    validate_compare(comparison)
    path = tmp_path/'compare.json'
    path.write_text(json.dumps(comparison))
    html_path, md_path = write_compare(path)
    document, markdown = html_path.read_text(), md_path.read_text()
    for text in ['Shared topic','Common claims','Contradictions','Who says what','Unique points','Overall verdict','not-checked','Author one']:
        assert text in document and text in markdown
    assert 'href="run%20one/report.html">v1</a>' in document
    assert '[v1](run%20one/report.html)' in markdown
    assert '&amp;t=12' in document and 'https://x.com/u/status/1?t=20' in document
    assert 'not checked: 1' in document and 'id="claim-search"' in document
    assert run_cli(['report','--compare',str(path)])[0] == 0


@pytest.mark.parametrize('mutation', ['version','missing','verdict','stance','time','reference','duplicate','matrix','snippet','date','url','single-video'])
def test_compare_schema_invalid(comparison,mutation):
    data = copy.deepcopy(comparison)
    if mutation == 'version': data['schema_version'] = 2
    elif mutation == 'missing': del data['verdict_overall']
    elif mutation == 'verdict': data['common_claims'][0]['verdict'] = 'maybe'
    elif mutation == 'stance': data['who_says_what'][0]['stances'][0]['stance'] = 'agrees'
    elif mutation == 'time': data['unique_points'][0]['t'] = -1
    elif mutation == 'reference': data['unique_points'][0]['id'] = 'v3'
    elif mutation == 'duplicate': data['videos'][1]['id'] = 'v1'
    elif mutation == 'matrix': data['who_says_what'][0]['stances'].pop()
    elif mutation == 'single-video': data['videos'].pop()
    else:
        evidence = data['contradictions'][0]['evidence'][0]
        evidence[{'snippet':'snippet','date':'retrieved','url':'url'}[mutation]] = {
            'snippet':' '.join(['word']*26),'date':'2026-02-30','url':'javascript:alert(1)'}[mutation]
    with pytest.raises(ValidationError):
        validate_compare(data)


def test_compare_invalid_does_not_overwrite(tmp_path):
    path = tmp_path/'compare.json'
    path.write_text('{}')
    (tmp_path/'compare.html').write_text('old')
    assert run_cli(['report','--compare',str(path)])[0] == 1
    assert (tmp_path/'compare.html').read_text() == 'old'


def test_report_argument_exclusivity(tmp_path):
    assert run_cli(['report'])[0] == 1
    assert run_cli(['report',str(tmp_path),'--compare',str(tmp_path/'compare.json')])[0] == 1


class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.tags = []
        self.remote = []
        self.handlers = []
    def handle_starttag(self,tag,attrs):
        attrs = dict(attrs)
        self.tags.append((tag,attrs))
        if tag == 'script': self.scripts.append(attrs)
        for key,value in attrs.items():
            if key.startswith('on'): self.handlers.append(key)
            if tag != 'a' and key in ('src','href','data','poster') and value.startswith(('http:','https:','//')):
                self.remote.append((tag,value))


def test_all_lenses_escape_and_no_external_resources(tmp_path,comparison):
    attack = '</textarea><script src="https://evil.test/x.js"></script><img src="https://evil.test/x" onerror="alert(1)">'
    def poison(value):
        if isinstance(value,dict): return {k:poison(v) for k,v in value.items()}
        if isinstance(value,list): return [poison(v) for v in value]
        return attack if value in ('Build it','Python','A study','Try Python','Measured','Curiosity') else value
    data = analysis(poison(copy.deepcopy(LENSES)))
    data['lenses']['future <script>'] = {'nested':[attack]}
    document, markdown = render_reports(data)
    comparison['topic'] = attack
    comparison['contradictions'][0]['positions'][0]['says'] = attack
    compare_html, compare_md = render_compare(comparison,tmp_path)
    for output in [document,compare_html]:
        audit = Audit()
        audit.feed(output)
        assert audit.scripts == [{}]
        assert audit.remote == [] and audit.handlers == []
        assert '&lt;script' in output
    assert '<script' not in markdown and '<script' not in compare_md


def test_controls_counts_copy_payload_csp_and_print():
    claim = {'id':'c1','claim_reviewed':'Claim','quote':'Quote','t':0,'kind':'fact','verdict':'true',
             'rating':5,'confidence':'high','rationale':'Evidence','evidence':[]}
    data = analysis({'claims':[claim,dict(claim,id='c2'),dict(claim,id='c3',verdict='false',rating=1)]})
    document, markdown = render_reports(data)
    assert 'true: 2' in document and 'false: 1' in document
    assert 'id="claim-search"' in document and 'id="claim-verdict"' in document
    assert 'Copy as Markdown' in document and 'aria-label="Table of contents"' in document
    digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    assert digest in document
    assert 'min-height:44px' in document and '@media print' in document
    import html
    content = re.search(r'<textarea[^>]*>(.*?)</textarea>',document,re.S).group(1)
    assert html.unescape(content) == markdown


def test_doctor_all_checks_offline(tmp_path):
    cache = tmp_path/'.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/snapshots/rev'
    cache.mkdir(parents=True)
    (cache/'config.json').write_text('{}')
    (cache/'weights.safetensors').write_bytes(b'weights')
    with patch.object(doctor.Path,'home',return_value=tmp_path), \
            patch.object(doctor,'version',return_value='2026.1'), \
            patch.object(doctor.importlib,'import_module'), \
            patch.object(doctor.subprocess,'run',return_value=SimpleNamespace(stdout='ffmpeg version test\n')) as ffmpeg:
        result = doctor.diagnose(tmp_path/'new-output')
    assert result['ok'] and result['missing'] == []
    assert len(result['checks']) == 5 and all(set(c)=={'name','ok','detail','fix'} for c in result['checks'])
    assert ffmpeg.call_args.args[0] == ['ffmpeg','-version']
    assert not (tmp_path/'new-output').exists()


def test_doctor_missing_and_empty_cache(tmp_path):
    (tmp_path/'.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo').mkdir(parents=True)
    with patch.object(doctor.Path,'home',return_value=tmp_path), \
            patch.object(doctor,'version',side_effect=PackageNotFoundError('yt-dlp')), \
            patch.object(doctor.importlib,'import_module',side_effect=ImportError('missing')), \
            patch.object(doctor.subprocess,'run',side_effect=FileNotFoundError()), \
            patch.object(doctor.tempfile,'TemporaryFile',side_effect=PermissionError('read-only')):
        result = doctor.diagnose(tmp_path)
    assert not result['ok'] and len(result['missing']) == 5
    assert all(c['fix'] for c in result['checks'])


@pytest.mark.parametrize('ok', [True,False])
def test_doctor_cli_json_and_exit(ok):
    result = {'ok':ok,'checks':[],'missing':[] if ok else ['ffmpeg']}
    with patch.object(doctor,'diagnose',return_value=result):
        code, out, _ = run_cli(['doctor','--json'])
    assert code == (0 if ok else 1) and json.loads(out) == result


def test_frames_rerun_cleans_only_previous_owned_files(frame_run):
    destination = frame_run/'frames'
    destination.mkdir()
    for name in ['0000.00.jpg','0001.00.jpg','handmade.jpg']:
        (destination/name).write_bytes(b'old')
    outside = frame_run/'untouched.jpg'
    outside.write_bytes(b'keep')
    (frame_run/'frames.json').write_text(json.dumps([
        {'t':0,'path':'frames/0000.00.jpg'}, {'t':1,'path':'frames/0001.00.jpg'},
        {'t':0,'path':'../untouched.jpg'}]))
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download), \
            patch.object(frames.subprocess,'run',side_effect=mock_ffmpeg):
        records = frames.extract_frames(frame_run,max_frames=1)
    assert records == [{'t':10.0,'path':'frames/0010.00.jpg'}]
    assert not (destination/'0000.00.jpg').exists() and not (destination/'0001.00.jpg').exists()
    assert (destination/'handmade.jpg').exists() and outside.exists()


def test_failed_frames_rerun_preserves_previous_outputs(frame_run):
    (frame_run/'frames').mkdir()
    image = frame_run/'frames/0000.00.jpg'
    image.write_bytes(b'original')
    old = json.dumps([{'t':0,'path':'frames/0000.00.jpg'}])
    (frame_run/'frames.json').write_text(old)
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download), \
            patch.object(frames.subprocess,'run',side_effect=FileNotFoundError()), pytest.raises(VideoIntelError):
        frames.extract_frames(frame_run)
    assert image.read_bytes() == b'original' and (frame_run/'frames.json').read_text() == old


def test_asr_no_speech_frames_still_extracted(tmp_path):
    module = SimpleNamespace(transcribe=Mock(return_value={'language':'en','segments':[]}))
    ydl = MagicMock()
    ydl.__enter__.return_value.extract_info.return_value = {'id':'v'}
    ydl.__enter__.return_value.prepare_filename.return_value = str(tmp_path/'audio.m4a')
    with patch.dict(sys.modules,{'mlx_whisper':module}), \
            patch.object(acq,'fetch_metadata',return_value={'id':'v','title':'Silent reel'}), \
            patch.object(acq,'_youtube_dl',return_value=ydl), \
            patch.object(acq.subprocess,'run',return_value=None), \
            patch.object(frames,'extract_frames') as extract:
        run = acq.fetch_video('https://instagram.com/reel/1',tmp_path,asr='force',frames=True)
    assert json.loads((run/'transcript.json').read_text())['segments'] == []
    extract.assert_called_once_with(run,cookies=None)


def test_asr_empty_without_frames_remains_a_failure(tmp_path):
    module = SimpleNamespace(transcribe=Mock(return_value={'language':'en','segments':[]}))
    ydl = MagicMock()
    ydl.__enter__.return_value.extract_info.return_value = {'id':'v'}
    ydl.__enter__.return_value.prepare_filename.return_value = str(tmp_path/'audio.m4a')
    with patch.dict(sys.modules,{'mlx_whisper':module}), patch.object(acq,'_youtube_dl',return_value=ydl), \
            patch.object(acq.subprocess,'run',return_value=None), pytest.raises(VideoIntelError,match='no speech'):
        acq.asr_transcript(URL,tmp_path)


def test_frames_no_window_default_interval_and_lazy_metadata(frame_run):
    (frame_run/'transcript.json').unlink()
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download) as download, \
            patch.object(frames.subprocess,'run',side_effect=mock_ffmpeg) as ffmpeg:
        records = frames.extract_frames(frame_run)
    command = ffmpeg.call_args.args[0]
    assert '-ss' not in command and '-to' not in command
    assert 'gte(t-prev_selected_t,30.0)' in command[command.index('-vf')+1]
    assert records[0] == {'t':0,'path':'frames/0000.00.jpg'}


def test_frames_missing_showinfo_is_failure(frame_run):
    with patch.object(frames,'_youtube_dl',side_effect=mock_frame_download), \
            patch.object(frames.subprocess,'run',return_value=SimpleNamespace(stderr='')), \
            pytest.raises(VideoIntelError,match='no timestamped frames'):
        frames.extract_frames(frame_run)
    assert not list(frame_run.glob('.video-*'))
