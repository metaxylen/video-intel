"""Offline HTML and Markdown reports, including forward-compatible lenses."""

from __future__ import annotations

import html
import base64
import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from youtube_transcript.markdown import format_timestamp
from youtube_transcript.urls import extract_video_id

from video_intel.validation import read_json, safe_url, validate_analysis

CSS = """
:root { color-scheme: light dark; --bg:#f6f7f9; --surface:#fff; --text:#1c2430;
  --muted:#536174; --line:#d9dfe7; --link:#1554ad; --good:#17653a; --good-bg:#e4f4ea;
  --bad:#a52929; --bad-bg:#fce8e8; --warn:#805300; --warn-bg:#fff1cf; --neutral-bg:#e9edf2; }
@media(prefers-color-scheme:dark) { :root { --bg:#14171c; --surface:#1d222a;
  --text:#e7ebf1; --muted:#b0bdcf; --line:#394351; --link:#91bdff; --good:#91d8ac;
  --good-bg:#203c2b; --bad:#ffabab; --bad-bg:#452526; --warn:#f2d28a; --warn-bg:#41351e;
  --neutral-bg:#303945; } }
* { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--text);
  font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width:960px; margin:auto; padding:40px 28px 72px; overflow-wrap:anywhere; }
header { padding-bottom:28px; border-bottom:1px solid var(--line); }
h1 { font-size:clamp(1.75rem,5vw,2.5rem); line-height:1.2; margin:8px 0 20px; }
h2 { margin:36px 0 16px; font-size:1.35rem; line-height:1.3; }
h3 { margin:12px 0; font-size:1.1rem; line-height:1.4; }
p { margin:10px 0; } a { color:var(--link); text-underline-offset:3px; }
a:focus-visible,summary:focus-visible { outline:3px solid var(--link); outline-offset:4px; }
.muted,dt { color:var(--muted); } .meta { display:flex; flex-wrap:wrap; gap:8px 20px; }
.chip { display:inline-block; border-radius:5px; padding:3px 9px; background:var(--neutral-bg);
  color:var(--text); font-size:.85rem; font-weight:600; }
.good { background:var(--good-bg); color:var(--good); }
.bad { background:var(--bad-bg); color:var(--bad); }
.warn { background:var(--warn-bg); color:var(--warn); }
article { background:var(--surface); padding:22px; border:1px solid var(--line); margin:16px 0; border-radius:8px; }
blockquote { margin:14px 0; padding:4px 16px; border-left:3px solid var(--line); }
ul,ol { padding-left:24px; } li { margin:8px 0; } dl { margin:12px 0; }
dt { font-weight:600; } dd { margin:0 0 16px; } dd dl, dd ul { padding-left:16px; }
.time { font-variant-numeric:tabular-nums; white-space:nowrap; }
.moment { padding:12px 0; border-bottom:1px solid var(--line); }
summary { cursor:pointer; padding:12px 0; font-weight:600; }
.transcript p { padding:8px 0; } .evidence { padding-top:12px; border-top:1px solid var(--line); }
@media(max-width:480px) { main { padding:24px 16px 48px; } article { padding:16px; } }
@media print { body { background:white; color:black; } main { max-width:none; } article { break-inside:avoid; } }
/* Reflow at phone widths, including long URLs and literal tutorial commands. */
main,section,article,details { min-width:0; }
a { display:inline-block; min-height:44px; min-width:44px; padding-block:8px; vertical-align:middle; }
button,input,select { font:inherit; min-height:44px; min-width:44px; max-width:100%;
  border:1px solid var(--line); border-radius:6px; padding:8px 12px;
  background:var(--surface); color:var(--text); }
button { cursor:pointer; } button:focus-visible,input:focus-visible,select:focus-visible {
  outline:3px solid var(--link); outline-offset:3px; }
.controls,.verdict-bar { display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin:16px 0; }
.controls label { display:grid; gap:4px; flex:1 1 200px; min-width:0; }
.toc ul { display:flex; flex-wrap:wrap; gap:4px 20px; list-style:none; padding:0; }
.toc li { margin:0; } .frame-strip { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr)); gap:12px; }
figure { margin:0; min-width:0; } img { max-width:100%; width:100%; height:auto; border-radius:6px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--neutral-bg); padding:12px; border-radius:6px; }
code { font-size:.9em; } [hidden] { display:none!important; }
@media print { .controls,.toc,.verdict-bar,button { display:none!important; }
  [data-claim][hidden] { display:block!important; } a { min-height:0; padding:0; }
  .frame-strip { grid-template-columns:repeat(3,1fr); } header { border-color:#999; }
  :root { color-scheme:light; --surface:#fff; --text:#000; --muted:#333; --link:#000;
    --neutral-bg:#eee; --good-bg:#eee; --bad-bg:#eee; --warn-bg:#eee;
    --good:#000; --bad:#000; --warn:#000; }
}
"""

SCRIPT = """
(() => {
  const search = document.getElementById('claim-search');
  const verdict = document.getElementById('claim-verdict');
  const cards = Array.from(document.querySelectorAll('[data-claim]'));
  function filterClaims() {
    const query = search.value.toLocaleLowerCase();
    let visible = 0;
    cards.forEach(card => {
      card.hidden = !(card.textContent.toLocaleLowerCase().includes(query) &&
        (!verdict.value || card.dataset.verdict === verdict.value));
      if (!card.hidden) visible++;
    });
    document.getElementById('claim-count').textContent = visible + ' of ' + cards.length + ' claims';
  }
  if (search && verdict) {
    search.addEventListener('input', filterClaims);
    verdict.addEventListener('change', filterClaims);
    filterClaims();
  }
  document.getElementById('copy-markdown').addEventListener('click', async () => {
    const text = document.getElementById('markdown-source');
    const status = document.getElementById('copy-status');
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text.value);
      else {
        text.hidden = false;
        text.select();
        const copied = document.execCommand('copy');
        text.hidden = true;
        if (!copied) throw new Error('copy unavailable');
      }
      status.textContent = 'Markdown copied';
    } catch (_) {
      text.hidden = true;
      status.textContent = 'Copy unavailable. Open the adjacent Markdown file.';
    }
  });
})();
"""


def make_document(title, body, markdown):
    """Shared offline shell; the CSP permits only this exact inline script."""
    headings = []

    def anchor(match):
        index = len(headings)
        headings.append((f"section-{index}", match.group(1)))
        return f'<h2 id="section-{index}">{match.group(1)}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", anchor, body, flags=re.S)
    toc = ('<nav class="toc" aria-label="Table of contents"><h2>Contents</h2><ul>'
           + "".join(f'<li><a href="#{key}">{label}</a></li>' for key, label in headings) + "</ul></nav>")
    controls = ('<div class="controls"><button id="copy-markdown" type="button">Copy as Markdown</button>'
                '<span id="copy-status" role="status" aria-live="polite"></span></div>')
    digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    csp = ("default-src 'none'; style-src 'unsafe-inline'; img-src 'self' file:; "
           f"script-src 'sha256-{digest}'; connect-src 'none'; base-uri 'none'; form-action 'none'")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{esc(csp)}">'
            f'<title>{esc(title)} — Video analysis</title><style>{CSS}</style></head><body><main>'
            + controls + toc + body + f'<textarea id="markdown-source" aria-label="Report Markdown" hidden>{esc(markdown)}</textarea>'
            + f'</main><script>{SCRIPT}</script></body></html>\n')


def verdict_bar(counts):
    return ('<aside aria-label="Verdict summary" class="verdict-bar">' + "".join(
        f'<span class="chip">{esc(verdict.replace("-", " "))}: {count}</span>'
        for verdict, count in counts.items()) + "</aside>") if counts else ""


def claim_controls(counts):
    return ('<div class="controls"><label>Search claims<input id="claim-search" type="search" '
            'placeholder="Search text, evidence or rationale"></label><label>Verdict'
            '<select id="claim-verdict"><option value="">All verdicts</option>' + "".join(
                f'<option value="{esc(verdict)}">{esc(verdict.replace("-", " "))}</option>' for verdict in counts)
            + '</select></label><span id="claim-count" role="status" aria-live="polite"></span></div>')


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def md(value) -> str:
    # Markdown may itself be rendered as HTML by downstream viewers.
    text = html.escape(str(value).replace("\r\n", "\n").replace("\r", "\n"), quote=False)
    text = re.sub(r"([\\`*_{}\[\]|])", r"\\\1", text)
    text = re.sub(r"(?m)^(\s*)([#+~>=-]|\d+[.)])", r"\1\\\2", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "  \n")


def single_line(value) -> str:
    """Keep untrusted headings within a single physical line."""
    return " ".join(str(value).split())


def timestamp_url(url: str, seconds: float) -> str:
    if not safe_url(url):
        return ""
    video_id = extract_video_id(url)
    if video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        return ""
    return f"{url}&t={int(seconds)}"


def link(label, url, markdown=False) -> str:
    url = safe_url(url)
    if markdown:
        destination = quote(url, safe=":/?#@!$&'*+,;=%")
        return f"[{md(label)}]({destination})" if url else md(label)
    return f'<a href="{esc(url)}">{esc(label)}</a>' if url else esc(label)


def time_link(seconds, url, markdown=False):
    label = format_timestamp(seconds)
    content = link(label, timestamp_url(url, seconds), markdown)
    return content if markdown else f'<span class="time">{content}</span>'


def generic(value, markdown=False, depth=0) -> str:
    """Render nested future lenses as dictionaries and lists, never executable markup."""
    if isinstance(value, dict):
        if markdown:
            lines = []
            for key, child in value.items():
                prefix = f"{'  ' * depth}- **{md(key)}:**"
                if isinstance(child, (dict, list)):
                    lines.extend([prefix, generic(child, True, depth + 1)])
                else:
                    lines.append(f"{prefix} {generic(child, True).lstrip()}")
            return "\n".join(lines)
        return "<dl>" + "".join(f"<dt>{esc(key)}</dt><dd>{generic(child)}</dd>" for key, child in value.items()) + "</dl>"
    if isinstance(value, list):
        if markdown:
            lines = []
            for child in value:
                if isinstance(child, (dict, list)):
                    lines.extend(["  " * depth + "-", generic(child, True, depth + 1)])
                else:
                    lines.append("  " * depth + "- " + generic(child, True).lstrip())
            return "\n".join(lines)
        return "<ul>" + "".join(f"<li>{generic(child)}</li>" for child in value) + "</ul>"
    text = "—" if value is None else str(value)
    return ("  " * depth + md(text)) if markdown else esc(text)


def _transcript_segments(transcript):
    if transcript is None:
        return []
    if not isinstance(transcript, dict) or not isinstance(transcript.get("segments"), list):
        raise ValueError("transcript.json: expected an object with a segments array")
    for segment in transcript["segments"]:
        if (not isinstance(segment, dict) or not isinstance(segment.get("text"), str)
                or type(segment.get("start")) not in (int, float)
                or (type(segment["start"]) is float and not math.isfinite(segment["start"]))
                or segment["start"] < 0):
            raise ValueError("transcript.json: each segment needs text and a finite nonnegative start")
    return transcript["segments"]


def render_reports(analysis: dict, transcript=None, frames=None) -> tuple[str, str]:
    validate_analysis(analysis)
    segments = _transcript_segments(transcript)
    video = analysis["video"]
    title, url = single_line(video["title"]), video["webpage_url"]
    source = analysis["transcript_source"]
    model = analysis["asr_model"]
    channel = video.get("channel") or video.get("uploader") or "Unknown channel"
    h = [f'<header><p class="muted">Video analysis</p><h1>{esc(title)}</h1>',
         f'<div class="meta"><span>{esc(channel)}</span><span class="chip">{esc(source)}</span></div>',
         f'<p>{link("Watch source video", url)}</p>']
    m = [f"# {md(title)}", "", f"- Source: {link('Watch video', url, True)}",
         f"- Channel: {md(channel)}", f"- Transcript: {md(source)}"]
    if model:
        h.append(f'<p class="muted">ASR model: {esc(model)}</p>')
        m.append(f"- ASR model: {md(model)}")
    h.append("</header>")
    metadata = {key: video[key] for key in ("platform", "upload_date", "duration", "view_count", "like_count", "description")
                if video.get(key) is not None}
    if metadata:
        h.append(f"<details><summary>Video details</summary>{generic(metadata)}</details>")
        m.extend(["", "## Video details", "", generic(metadata, True)])
    if frames is not None:
        if not isinstance(frames, list):
            raise ValueError("frames.json: expected an array")
        h.append('<section><h2>Frames</h2><div class="frame-strip">')
        m.extend(["", "## Frames", ""])
        for frame in frames:
            if (not isinstance(frame, dict) or type(frame.get("t")) not in (int, float)
                    or not math.isfinite(frame["t"]) or frame["t"] < 0
                    or not isinstance(frame.get("path"), str)
                    or not re.fullmatch(r"frames/\d{4,}\.\d{2}\.jpg", frame["path"])):
                raise ValueError("frames.json: expected nonnegative t and a relative timestamp JPEG path")
            if video.get("duration") is not None and frame["t"] > video["duration"]:
                raise ValueError("frames.json: timestamp exceeds video.duration")
            label = format_timestamp(frame["t"])
            h.append(f'<figure><img src="{esc(frame["path"])}" alt="Frame at {esc(label)}" '
                     f'loading="lazy" width="512"><figcaption>{time_link(frame["t"], url)}</figcaption></figure>')
            m.extend([f"![Frame at {md(label)}]({frame['path']}) {time_link(frame['t'], url, True)}", ""])
        h.append("</div></section>")
    counts = Counter(claim["verdict"] for claim in analysis["lenses"].get("claims", []))
    if counts:
        h.append(verdict_bar(counts))
        m.extend(["", "## Verdict summary", "", *[f"- {verdict.replace('-', ' ')}: {count}" for verdict, count in counts.items()]])
    for name, lens in analysis["lenses"].items():
        if name == "summary":
            h.append(f'<section><h2>Summary</h2><p>{esc(lens["tldr"])}</p><ul>')
            h.extend(f"<li>{esc(point)}</li>" for point in lens["key_points"])
            h.append("</ul>")
            m.extend(["", "## Summary", "", md(lens["tldr"]), ""])
            m.extend(f"- {md(point)}" for point in lens["key_points"])
            if lens["audience"] is not None:
                h.append(f'<p class="muted">Audience: {esc(lens["audience"])}</p>')
                m.extend(["", f"Audience: {md(lens['audience'])}"])
            h.append("</section>")
        elif name == "moments":
            h.append("<section><h2>Key moments</h2>")
            m.extend(["", "## Key moments", ""])
            for moment in lens:
                h.append(f'<div class="moment">{time_link(moment["t"], url)} '
                         f'<strong>{esc(moment["title"])}</strong><p>{esc(moment["note"])}</p></div>')
                m.extend([f"### {time_link(moment['t'], url, True)} {md(single_line(moment['title']))}", "", md(moment["note"]), ""])
            h.append("</section>")
        elif name == "claims":
            h.append("<section><h2>Claims</h2>")
            h.append(claim_controls(counts))
            m.extend(["", "## Claims", ""])
            for claim in lens:
                verdict = claim["verdict"]
                colour = ("good" if verdict in ("true", "mostly-true") else "bad" if verdict in ("false", "mostly-false")
                          else "warn" if verdict in ("half-true", "not-enough-evidence") else "")
                label = verdict.replace("-", " ")
                details = f"{claim['kind']} · Confidence: {claim['confidence']} · Rating: {claim['rating'] if claim['rating'] is not None else '—'}/5"
                h.append(f'<article data-claim data-verdict="{esc(verdict)}"><span class="chip {colour}">{esc(label)}</span>'
                         f'<h3>{esc(single_line(claim["claim_reviewed"]))}</h3>'
                         f'<p class="muted">{esc(claim["id"])} · {time_link(claim["t"], url)} · {esc(details)}</p>'
                         f'<blockquote>{esc(claim["quote"])}</blockquote><p>{esc(claim["rationale"])}</p>')
                m.extend([f"### {md(single_line(claim['claim_reviewed']))}", "", f"**Verdict: {md(label)}**",
                          f"{md(claim['id'])} · {time_link(claim['t'], url, True)} · {md(details)}", "",
                          md(claim["quote"]), "", md(claim["rationale"]), ""])
                for evidence in claim["evidence"]:
                    dates = f"Published: {evidence['published'] or 'unknown'} · Retrieved: {evidence['retrieved']}"
                    h.append(f'<div class="evidence"><p>{link(evidence["publisher"], evidence["url"])}</p>'
                             f'<p>{esc(evidence["snippet"])}</p><p class="muted">{esc(dates)}</p></div>')
                    m.extend([f"- {link(evidence['publisher'], evidence['url'], True)} — {md(dates)}",
                              f"  {md(evidence['snippet'])}", ""])
                h.append("</article>")
            h.append("</section>")
        elif name in ("steps", "mentions", "hook", "sources", "tone", "actions"):
            from video_intel.lenses import TITLES, render_lens

            lens_html, lens_md = render_lens(name, lens, url)
            h.append(f'<section><h2>{TITLES[name]}</h2>{lens_html}</section>')
            m.extend(["", f"## {TITLES[name]}", "", lens_md])
        else:
            h.append(f"<section><h2>{esc(single_line(name))}</h2>{generic(lens)}</section>")
            m.extend(["", f"## {md(single_line(name))}", "", generic(lens, True)])
    caveats = list(analysis["caveats"])
    if source == "asr":
        caveats.append("Machine transcription may distort names and numbers; check the source audio.")
    if caveats:
        h.append("<section><h2>Caveats</h2><ul>" + "".join(f"<li>{esc(c)}</li>" for c in caveats) + "</ul></section>")
        m.extend(["", "## Caveats", ""] + [f"- {md(c)}" for c in caveats])
    if segments:
        h.append('<section class="transcript"><h2>Transcript</h2>')
        m.extend(["", "## Transcript", ""])
        for segment in segments:
            h.append(f'<p>{time_link(segment["start"], url)} {esc(segment["text"])}</p>')
            m.extend([f"{time_link(segment['start'], url, True)} {md(segment['text'])}", ""])
        h.append("</section>")
    markdown = "\n".join(m) + "\n"
    return make_document(title, "\n".join(h), markdown), markdown


def write_report(run_dir: Path) -> tuple[Path, Path]:
    run_dir = Path(run_dir)
    analysis = read_json(run_dir / "analysis.json")
    meta_path = run_dir / "meta.json"
    if isinstance(analysis, dict) and meta_path.is_file():
        metadata = read_json(meta_path)
        if not isinstance(metadata, dict):
            raise ValueError("meta.json: expected an object")
        if "video" not in analysis:
            analysis["video"] = metadata
        elif isinstance(analysis["video"], dict):
            analysis["video"] = dict(analysis["video"], **metadata)
    transcript_path = run_dir / "transcript.json"
    transcript = read_json(transcript_path) if transcript_path.is_file() else None
    frames_path = run_dir / "frames.json"
    frames = read_json(frames_path) if frames_path.is_file() else None
    document, markdown = render_reports(analysis, transcript, frames)
    html_path, md_path = run_dir / "report.html", run_dir / "report.md"
    html_path.write_text(document, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return html_path, md_path
