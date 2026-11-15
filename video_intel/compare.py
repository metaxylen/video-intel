"""Comparison reports with local run links and absolute source timestamps."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from video_intel.report import claim_controls, esc, link, make_document, md, single_line, time_link, verdict_bar, truth_meter, lens_text
from video_intel.presentation import label, report_language, VERDICTS
from video_intel.validation import ValidationError, read_json, safe_url, validate_compare, validate_timestamps


def render_compare(data, base_dir):
    validate_compare(data)
    base_dir = Path(base_dir).resolve()
    videos = {}
    transcript = None
    durations = {}
    for video in data["videos"]:
        run = Path(video["run_dir"]).expanduser()
        if not run.is_absolute():
            run = base_dir / run
        metadata = read_json(run / "meta.json")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("webpage_url"), str) or not safe_url(metadata["webpage_url"]):
            raise ValueError(f"Invalid source URL in {run / 'meta.json'}")
        if transcript is None and (run / "transcript.json").is_file():
            candidate = read_json(run / "transcript.json")
            if isinstance(candidate, dict):
                transcript = candidate
        durations[video["id"]] = metadata.get("duration")
        videos[video["id"]] = (video, metadata["webpage_url"], quote(os.path.relpath(run / "report.html", base_dir), safe="/"))

    def check_references(value):
        if isinstance(value, dict):
            duration = durations.get(value.get("id"))
            if type(duration) in (int, float):
                errors = validate_timestamps(value, duration, "compare")
                if errors:
                    raise ValidationError(errors)
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    check_references(data)
    language = report_language(data, transcript)
    tr = lambda key: label(key, language)
    counts = Counter(item["verdict"] for item in data["common_claims"])

    def reference(ref, markdown=False):
        _, url, local = videos[ref["id"]]
        video_link = f"[{md(ref['id'])}]({local})" if markdown else f'<a href="{esc(local)}">{esc(ref["id"])}</a>'
        return video_link + (" · " + time_link(ref["t"], url, markdown) if ref.get("t") is not None else "")

    h = [f'<header><span class="chip">{esc(tr("comparison"))}</span><h1>{esc(single_line(data["topic"]))}</h1>',
         verdict_bar(counts, language), f'</header><section><h2>{esc(tr("videos"))}</h2>']
    m = [f"# {md(single_line(data['topic']))}", "", f"## {tr('videos')}", ""]
    for video in data["videos"]:
        h.append(f"<p>{reference(video)} — {esc(video['title'])} · {esc(video['creator'])}</p>")
        m.append(f"- {reference(video, True)} — {md(video['title'])} · {md(video['creator'])}")
    h.append("</section>")
    if counts:
        m.extend(["", f"## {tr('verdict_summary')}", "", *[f"- {tr(v)}: {counts[v]}" for v in VERDICTS if counts.get(v)]])
    for group in ("common_claims", "contradictions", "who_says_what", "unique_points"):
        h.append(f"<section><h2>{esc(tr(group))}</h2>")
        if group == "common_claims":
            h.extend(['<div id="claim-list">', claim_controls(counts, language)])
        m.extend(["", f"## {tr(group)}", ""])
        for item in data[group]:
            title = item.get("claim", item.get("topic", item.get("point", "")))
            verdict = item.get("verdict")
            attributes = (f' data-claim data-verdict="{verdict}" style="--verdict:var(--{verdict})"'
                          if group == "common_claims" else "")
            h.append(f"<article{attributes}>")
            if verdict:
                # Comparison has no independent numerical rating; derive the ordinal only for checked verdicts.
                rating = {"false":1, "mostly-false":2, "half-true":3, "mostly-true":4, "true":5}.get(verdict)
                h.append(f'<div class="claim-verdict"><span>{esc(tr(verdict))}</span>{truth_meter(verdict, rating, language)}</div>')
            h.append(f"<h3>{lens_text(single_line(title))}</h3>")
            m.extend([f"### {md(single_line(title))}", ""])
            if group == "unique_points":
                _, url, _ = videos[item["id"]]
                h.append(f"<p>{reference(item)}</p>")
                m.extend([reference(item, True), ""])
            else:
                key = {"common_claims": "videos", "contradictions": "positions", "who_says_what": "stances"}[group]
                for ref in item[key]:
                    _, url, _ = videos[ref["id"]]
                    text = ref.get("says", f"{tr(ref['stance']) if 'stance' in ref else ''} {ref.get('note', '')}".strip())
                    h.append(f"<p>{reference(ref)} {lens_text(text, url)}</p>")
                    m.extend([f"{reference(ref, True)} {md(text)}", ""])
            # Unattributed comparison prose has no unambiguous video timestamp destination.
            for key in ("verdict", "note", "resolution"):
                if key in item:
                    content = tr(item[key]) if key in ("verdict", "resolution") else item[key]
                    h.append(f"<p><strong>{esc(tr(key))}:</strong> {lens_text(content)}</p>")
                    m.extend([f"**{tr(key)}:** {md(content)}", ""])
            if item.get("evidence"):
                h.append('<ul class="evidence">')
            for evidence in item.get("evidence", []):
                dates = f"{tr('published')}: {evidence.get('published') or tr('unknown')} · {tr('retrieved')}: {evidence['retrieved']}"
                h.append(f'<li><strong>{link(evidence["publisher"], evidence["url"])}</strong>'
                         f'<p>{lens_text(evidence["snippet"])}</p><p class="muted">{esc(dates)}</p></li>')
                m.extend([f"- {link(evidence['publisher'], evidence['url'], True)} — {md(evidence['snippet'])} · {md(dates)}", ""])
            if item.get("evidence"):
                h.append('</ul>')
            h.append("</article>")
        if group == "common_claims":
            h.append('</div>')
        h.append("</section>")
    h.append(f"<section><h2>{esc(tr('overall'))}</h2><p>{lens_text(data['verdict_overall'])}</p></section>")
    m.extend(["", f"## {tr('overall')}", "", md(data["verdict_overall"]), ""])
    markdown = "\n".join(m)
    return make_document(data["topic"], "\n".join(h), markdown, language, counts), markdown


def write_compare(path):
    path = Path(path)
    document, markdown = render_compare(read_json(path), path.parent)
    html_path, md_path = path.parent / "compare.html", path.parent / "compare.md"
    html_path.write_text(document, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return html_path, md_path
