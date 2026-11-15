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

from video_intel.presentation import CSS, SCRIPT, VERDICTS, label, platform_name, report_language


def make_document(title, body, markdown, language="en"):
    """Shared offline shell; untrusted text never enters the trusted inline script."""
    headings = []

    def anchor(match):
        key = f"section-{len(headings)}"
        headings.append((key, match.group(1)))
        return f'<h2 id="{key}">{match.group(1)}</h2>'

    body = re.sub(r"<h2>(.*?)</h2>", anchor, body, flags=re.S)
    # Observe sections rather than short heading elements so long sections stay active.
    body = re.sub(r'(<section[^>]*>)<h2 id="(section-\d+)"',
                  lambda m: m.group(1)[:-1] + f' id="{m.group(2)}"><h2', body)
    toc = (f'<nav class="toc" aria-label="{esc(label("toc", language))}">'
           f'<h2>{esc(label("contents", language))}</h2><ul>'
           + "".join(f'<li><a href="#{key}" aria-current="{str(i == 0).lower()}">{text}</a></li>'
                     for i, (key, text) in enumerate(headings)) + "</ul></nav>")

    def actions(mobile=False):
        return (f'<div class="actions{ " mobile-actions" if mobile else ""}">'
                f'<button type="button" data-copy-markdown>{esc(label("copy", language))}</button>'
                f'<button type="button" data-print>{esc(label("print", language))}</button></div>')

    status = '<span id="copy-status" role="status" aria-live="polite"></span>'
    header, rest = body.split('</header>', 1)
    header = header.replace('<header>', '<header class="report-header">', 1)
    header += actions(True) + status + '</header>'
    digest = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    csp = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
           f"script-src 'sha256-{digest}'; connect-src 'none'; base-uri 'none'; form-action 'none'")
    data = ' '.join(f'data-{key}="{esc(label(value, language))}"' for key, value in
                    (("count", "count"), ("copied", "copied"), ("copy-failed", "copy_failed")))
    return (f'<!doctype html><html lang="{language}" {data}><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{esc(csp)}">'
            f'<title>{esc(title)} — {esc(label("report", language))}</title><style>{CSS}</style></head><body>'
            '<div class="layout">' + header + '<aside class="rail">' + toc + actions() + '</aside>'
            + '<main>' + rest + '</main></div>'
            + f'<textarea id="markdown-source" aria-label="{esc(label("markdown", language))}" hidden>{esc(markdown)}</textarea>'
            + f'<script>{SCRIPT}</script></body></html>\n')


def verdict_legend(counts, language="en"):
    return '<div class="verdict-legend">' + "".join(
        f'<button type="button" data-filter-verdict="{verdict}" aria-pressed="false" '
        f'style="--verdict:var(--{verdict})"><span class="swatch" aria-hidden="true"></span>'
        f'<span><strong>{counts[verdict]}</strong> {esc(label(verdict, language))}</span></button>'
        for verdict in VERDICTS if counts.get(verdict)) + '</div>'


def verdict_bar(counts, language="en"):
    if not counts:
        return ""
    total = sum(counts.values())
    minimum_width = 44 * total / min(counts.values()) + 3 * (len(counts) - 1)
    return (f'<div class="verdict-summary"><h2 class="verdict-heading">{esc(label("verdict_summary", language))}</h2>'
            f'<div class="verdict-scroll"><div class="verdict-bar" style="min-width:{minimum_width:g}px" role="group" aria-label="{esc(label("verdict_summary", language))}">'
            + "".join(f'<button type="button" class="verdict-segment" data-filter-verdict="{verdict}" '
                      f'data-count="{counts[verdict]}" aria-pressed="false" '
                      f'aria-label="{esc(label(verdict, language))}: {counts[verdict]}" '
                      f'style="--count:{counts[verdict]};--verdict:var(--{verdict});width:{counts[verdict] / total * 100:.4f}%">'
                      f'{counts[verdict]}</button>' for verdict in VERDICTS if counts.get(verdict))
            + '</div></div>' + verdict_legend(counts, language) + '</div>')


def truth_meter(verdict, rating, language="en"):
    rated = verdict not in ("not-checkable", "not-enough-evidence", "not-checked") and rating is not None
    accessible = f'{label("rating", language)}: {rating}/5' if rated else label("unrated", language)
    return (f'<span class="truth-meter" role="img" aria-label="{esc(accessible)}">'
            + "".join(f'<i class="{ "filled" if rated and i < rating else ""}" aria-hidden="true"></i>'
                      for i in range(5)) + '</span>')


def claim_controls(counts, language="en"):
    return (f'<div class="controls"><label>{esc(label("search_claims", language))}<input id="claim-search" type="search" '
            f'placeholder="{esc(label("search_hint", language))}"></label><label>{esc(label("verdict", language))}'
            f'<select id="claim-verdict"><option value="">{esc(label("all_verdicts", language))}</option>'
            + "".join(f'<option value="{verdict}">{esc(label(verdict, language))}</option>'
                      for verdict in VERDICTS if counts.get(verdict))
            + '</select></label><span id="claim-count" role="status" aria-live="polite"></span></div>'
            + f'<p id="claim-empty" role="status" hidden>{esc(label("empty", language))}</p>')


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


def lens_text(value, url=""):
    """Escape arbitrary text and link valid bracketed timestamps without parsing HTML."""
    parts, end = [], 0
    for match in re.finditer(r"\[(?:(\d+):)?(\d{1,2}):([0-5]\d)\]", str(value)):
        hours, minutes, seconds = match.groups()
        if hours is not None and int(minutes) >= 60:
            continue
        offset = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
        parts.extend([esc(str(value)[end:match.start()]),
                      '<span class="time">' + link(match.group(0), timestamp_url(url, offset)) + '</span>'])
        end = match.end()
    return "".join(parts) + esc(str(value)[end:])


def generic(value, markdown=False, depth=0, url="", language="en") -> str:
    """Render nested future lenses as dictionaries and lists, never executable markup."""
    if isinstance(value, dict):
        if markdown:
            lines = []
            for key, child in value.items():
                prefix = f"{'  ' * depth}- **{md(label(key, language))}:**"
                if isinstance(child, (dict, list)):
                    lines.extend([prefix, generic(child, True, depth + 1, url, language)])
                else:
                    lines.append(f"{prefix} {generic(child, True, url=url, language=language).lstrip()}")
            return "\n".join(lines)
        return "<dl>" + "".join(f"<dt>{esc(label(key, language))}</dt><dd>{generic(child, url=url, language=language)}</dd>" for key, child in value.items()) + "</dl>"
    if isinstance(value, list):
        if markdown:
            lines = []
            for child in value:
                if isinstance(child, (dict, list)):
                    lines.extend(["  " * depth + "-", generic(child, True, depth + 1, url, language)])
                else:
                    lines.append("  " * depth + "- " + generic(child, True, url=url, language=language).lstrip())
            return "\n".join(lines)
        return "<ul>" + "".join(f"<li>{generic(child, url=url, language=language)}</li>" for child in value) + "</ul>"
    text = "—" if value is None else str(value)
    return ("  " * depth + md(text)) if markdown else lens_text(text, url)


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


def render_reports(analysis: dict, transcript=None, frames=None, *, frame_images=None) -> tuple[str, str]:
    validate_analysis(analysis)
    segments = _transcript_segments(transcript)
    language = report_language(analysis, transcript)
    tr = lambda key: label(key, language)
    video = analysis["video"]
    title, url = single_line(video["title"]), video["webpage_url"]
    text = lambda value: lens_text(value, url)
    source, model = analysis["transcript_source"], analysis["asr_model"]
    channel = video.get("channel") or video.get("uploader") or tr("unknown_channel")
    counts = Counter(claim["verdict"] for claim in analysis["lenses"].get("claims", []))
    metadata_line = [esc(channel)]
    if video.get("upload_date"):
        date = video["upload_date"]
        if re.fullmatch(r"\d{8}", date):
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        metadata_line.append(esc(date))
    if video.get("duration") is not None:
        metadata_line.append(f'<span class="time">{esc(format_timestamp(video["duration"]))}</span>')
    platform = platform_name(video["platform"]) if video.get("platform") else tr("report")
    h = [f'<header><span class="chip">{esc(platform)}</span><h1>{esc(title)}</h1>',
         '<div class="meta">' + '<span aria-hidden="true">·</span>'.join(f'<span>{v}</span>' for v in metadata_line) + '</div>',
         f'<div class="source-row"><span class="chip">{esc(tr(source))}</span>{link(tr("watch"), url)}</div>']
    m = [f"# {md(title)}", "", f"- {tr('source')}: {link(tr('watch'), url, True)}",
         f"- {tr('channel')}: {md(channel)}", f"- {tr('transcript')}: {md(tr(source))}"]
    if model:
        h.append(f'<p class="source-caveat">{esc(tr("asr_model"))}: {esc(model)}</p>')
        m.append(f"- {tr('asr_model')}: {md(model)}")
    if source == "asr":
        h.append(f'<p class="source-caveat">{esc(tr("asr_caveat"))}</p>')
    h.extend([verdict_bar(counts, language), "</header>"])
    if counts:
        m.extend(["", f"## {tr('verdict_summary')}", "",
                  *[f"- {tr(v)}: {counts[v]}" for v in VERDICTS if counts.get(v)]])
    metadata = {key: video[key] for key in ("platform", "upload_date", "duration", "view_count", "like_count", "description")
                if video.get(key) is not None}
    if metadata:
        h.append(f'<details><summary>{esc(tr("details"))}</summary>{generic(metadata, url=url, language=language)}</details>')
        m.extend(["", f"## {tr('details')}", "", generic(metadata, True, language=language)])
    if frames is not None:
        if not isinstance(frames, list):
            raise ValueError("frames.json: expected an array")
        h.append(f'<section><h2>{esc(tr("frames"))}</h2><div class="frame-strip">')
        m.extend(["", f"## {tr('frames')}", ""])
        for frame in frames:
            if (not isinstance(frame, dict) or type(frame.get("t")) not in (int, float)
                    or not math.isfinite(frame["t"]) or frame["t"] < 0
                    or not isinstance(frame.get("path"), str)
                    or not re.fullmatch(r"frames/\d{4,}\.\d{2}\.jpg", frame["path"])):
                raise ValueError("frames.json: expected nonnegative t and a relative timestamp JPEG path")
            if video.get("duration") is not None and frame["t"] > video["duration"]:
                raise ValueError("frames.json: timestamp exceeds video.duration")
            stamp = format_timestamp(frame["t"])
            # Only bytes supplied by the local file writer can become image data.
            image = (frame_images or {}).get(frame["path"])
            if image is not None:
                encoded = base64.b64encode(image).decode("ascii")
                h.append(f'<figure><img src="data:image/jpeg;base64,{encoded}" '
                         f'alt="{esc(tr("frame_at"))} {esc(stamp)}" loading="lazy" width="512" height="288">'
                         f'<figcaption>{time_link(frame["t"], url)}</figcaption></figure>')
            else:
                h.append(f'<figure><figcaption>{esc(tr("frame_at"))} {time_link(frame["t"], url)}</figcaption></figure>')
            m.extend([f"![{md(tr('frame_at'))} {md(stamp)}]({frame['path']}) {time_link(frame['t'], url, True)}", ""])
        h.append("</div></section>")
    for name, lens in analysis["lenses"].items():
        heading = tr(name)
        if name == "summary":
            h.append(f'<section><h2>{esc(heading)}</h2><p>{text(lens["tldr"])}</p><ul>')
            h.extend(f"<li>{text(point)}</li>" for point in lens["key_points"])
            h.append("</ul>")
            m.extend(["", f"## {heading}", "", md(lens["tldr"]), ""])
            m.extend(f"- {md(point)}" for point in lens["key_points"])
            if lens["audience"] is not None:
                h.append(f'<p class="muted">{esc(tr("audience"))}: {text(lens["audience"])}</p>')
                m.extend(["", f"{tr('audience')}: {md(lens['audience'])}"])
            h.append("</section>")
        elif name == "moments":
            h.append(f"<section><h2>{esc(heading)}</h2>")
            m.extend(["", f"## {heading}", ""])
            for moment in lens:
                h.append(f'<div class="moment">{time_link(moment["t"], url)}<div>'
                         f'<h3>{text(single_line(moment["title"]))}</h3><p>{text(moment["note"])}</p></div></div>')
                m.extend([f"### {time_link(moment['t'], url, True)} {md(single_line(moment['title']))}", "", md(moment["note"]), ""])
            h.append("</section>")
        elif name == "claims":
            h.append(f'<section><h2>{esc(heading)}</h2><div id="claim-list">')
            h.append(claim_controls(counts, language))
            m.extend(["", f"## {heading}", ""])
            for claim in lens:
                verdict = claim["verdict"]
                details = f"{tr(claim['kind'])} · {tr('confidence')}: {tr(claim['confidence'])}"
                h.append(f'<article data-claim data-verdict="{verdict}" style="--verdict:var(--{verdict});'
                         f'--verdict-text:var(--{verdict}-text,var(--{verdict}))">'
                         f'<div class="claim-verdict"><span>{esc(tr(verdict))}</span>{truth_meter(verdict, claim["rating"], language)}</div>'
                         f'<h3>{text(single_line(claim["claim_reviewed"]))}</h3>'
                         f'<p class="claim-meta">{time_link(claim["t"], url)} · {esc(details)}</p>'
                         f'<blockquote>{text(claim["quote"])}</blockquote><p>{text(claim["rationale"])}</p>')
                m.extend([f"### {md(single_line(claim['claim_reviewed']))}", "", f"**{tr('verdict')}: {tr(verdict)}**",
                          f"{time_link(claim['t'], url, True)} · {md(details)} · {tr('rating')}: {claim['rating'] or '—'}/5", "",
                          md(claim["quote"]), "", md(claim["rationale"]), ""])
                if claim["evidence"]:
                    h.append('<ul class="evidence">')
                for evidence in claim["evidence"]:
                    dates = f"{tr('published')}: {evidence['published'] or tr('unknown')} · {tr('retrieved')}: {evidence['retrieved']}"
                    h.append(f'<li><strong>{link(evidence["publisher"], evidence["url"])}</strong>'
                             f'<p>{text(evidence["snippet"])}</p><p class="muted">{esc(dates)}</p></li>')
                    m.extend([f"- {link(evidence['publisher'], evidence['url'], True)} — {md(dates)}",
                              f"  {md(evidence['snippet'])}", ""])
                if claim["evidence"]:
                    h.append('</ul>')
                h.append("</article>")
            h.append("</div></section>")
        elif name in ("steps", "mentions", "hook", "sources", "tone", "actions"):
            from video_intel.lenses import render_lens

            lens_html, lens_md = render_lens(name, lens, url, language)
            h.append(f'<section><h2>{esc(heading)}</h2>{lens_html}</section>')
            m.extend(["", f"## {heading}", "", lens_md])
        else:
            h.append(f'<section><h2>{esc(single_line(name))}</h2>{generic(lens, url=url, language=language)}</section>')
            m.extend(["", f"## {md(single_line(name))}", "", generic(lens, True, language=language)])
    caveats = list(analysis["caveats"])
    if source == "asr":
        caveats.append(tr("asr_caveat"))
    if caveats:
        h.append(f'<section><h2>{esc(tr("caveats"))}</h2><ul>' + "".join(f"<li>{text(c)}</li>" for c in caveats) + "</ul></section>")
        m.extend(["", f"## {tr('caveats')}", ""] + [f"- {md(c)}" for c in caveats])
    if segments:
        h.append(f'<section class="transcript"><h2>{esc(tr("transcript"))}</h2>'
                 f'<details id="full-transcript"><summary>{esc(tr("show_transcript"))} '
                 f'<span class="muted">· {len(segments)} {esc(tr("segments"))}</span></summary>'
                 f'<label class="transcript-search">{esc(tr("search_transcript"))}<input id="transcript-search" type="search"></label>')
        m.extend(["", f"## {tr('transcript')}", ""])
        for segment in segments:
            h.append(f'<p data-transcript-segment>{time_link(segment["start"], url)} {esc(segment["text"])}</p>')
            m.extend([f"{time_link(segment['start'], url, True)} {md(segment['text'])}", ""])
        h.append("</details></section>")
    markdown = "\n".join(m) + "\n"
    return make_document(title, "\n".join(h), markdown, language), markdown


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
    images = {}
    if isinstance(frames, list):
        for frame in frames:
            path = frame.get("path") if isinstance(frame, dict) else None
            if isinstance(path, str) and re.fullmatch(r"frames/\d{4,}\.\d{2}\.jpg", path):
                image_path = (run_dir / path).resolve()
                if not image_path.is_relative_to(run_dir.resolve()):
                    raise ValueError("Frame image must remain inside the run directory")
                images[path] = image_path.read_bytes()
    document, markdown = render_reports(analysis, transcript, frames, frame_images=images)
    html_path, md_path = run_dir / "report.html", run_dir / "report.md"
    html_path.write_text(document, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return html_path, md_path
