"""Comparison reports with local run links and absolute source timestamps."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from video_intel.report import claim_controls, esc, link, make_document, md, time_link, verdict_bar
from video_intel.validation import read_json, safe_url, validate_compare


def render_compare(data, base_dir):
    validate_compare(data)
    base_dir = Path(base_dir).resolve()
    videos = {}
    for video in data["videos"]:
        run = Path(video["run_dir"]).expanduser()
        if not run.is_absolute():
            run = base_dir / run
        metadata = read_json(run / "meta.json")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("webpage_url"), str) or not safe_url(metadata["webpage_url"]):
            raise ValueError(f"Invalid source URL in {run / 'meta.json'}")
        videos[video["id"]] = (video, metadata["webpage_url"], quote(os.path.relpath(run / "report.html", base_dir), safe="/"))

    def reference(ref, markdown=False):
        _, url, local = videos[ref["id"]]
        video_link = f"[{md(ref['id'])}]({local})" if markdown else f'<a href="{esc(local)}">{esc(ref["id"])}</a>'
        return video_link + (" · " + time_link(ref["t"], url, markdown) if ref.get("t") is not None else "")

    h = [f"<header><p class=muted>Video comparison</p><h1>{esc(data['topic'])}</h1></header>", "<section><h2>Videos</h2>"]
    m = [f"# {md(data['topic'])}", "", "## Videos", ""]
    for video in data["videos"]:
        h.append(f"<p>{reference(video)} — {esc(video['title'])} · {esc(video['creator'])}</p>")
        m.append(f"- {reference(video, True)} — {md(video['title'])} · {md(video['creator'])}")
    h.append("</section>")
    counts = Counter(item["verdict"] for item in data["common_claims"])
    h.append(verdict_bar(counts))
    if counts:
        m.extend(["", "## Verdict summary", "", *[f"- {verdict.replace('-', ' ')}: {count}" for verdict, count in counts.items()]])
    for title, group in (("Common claims", "common_claims"), ("Contradictions", "contradictions"),
                         ("Who says what", "who_says_what"), ("Unique points", "unique_points")):
        h.append(f"<section><h2>{title}</h2>")
        if group == "common_claims":
            h.append(claim_controls(counts))
        m.extend(["", f"## {title}", ""])
        for item in data[group]:
            label = item.get("claim", item.get("topic", item.get("point", "")))
            attributes = f' data-claim data-verdict="{esc(item["verdict"])}"' if group == "common_claims" else ""
            h.append(f"<article{attributes}><h3>{esc(label)}</h3>")
            m.extend([f"### {md(label)}", ""])
            if group == "unique_points":
                h.append(f"<p>{reference(item)}</p>")
                m.extend([reference(item, True), ""])
            else:
                key = {"common_claims": "videos", "contradictions": "positions", "who_says_what": "stances"}[group]
                for ref in item[key]:
                    text = ref.get("says", f"{ref.get('stance', '')} {ref.get('note', '')}".strip())
                    h.append(f"<p>{reference(ref)} {esc(text)}</p>")
                    m.extend([f"{reference(ref, True)} {md(text)}", ""])
            for key in ("verdict", "note", "resolution"):
                if key in item:
                    h.append(f"<p><strong>{key.title()}:</strong> {esc(item[key])}</p>")
                    m.extend([f"**{key.title()}:** {md(item[key])}", ""])
            for evidence in item.get("evidence", []):
                text = f"{evidence['snippet']} · Retrieved: {evidence['retrieved']}"
                h.append(f"<p>{link(evidence['publisher'], evidence['url'])} — {esc(text)}</p>")
                m.extend([f"- {link(evidence['publisher'], evidence['url'], True)} — {md(text)}", ""])
            h.append("</article>")
        h.append("</section>")
    h.append(f"<section><h2>Overall verdict</h2><p>{esc(data['verdict_overall'])}</p></section>")
    m.extend(["", "## Overall verdict", "", md(data["verdict_overall"]), ""])
    markdown = "\n".join(m)
    return make_document(data["topic"], "\n".join(h), markdown), markdown


def write_compare(path):
    path = Path(path)
    document, markdown = render_compare(read_json(path), path.parent)
    html_path, md_path = path.parent / "compare.html", path.parent / "compare.md"
    html_path.write_text(document, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return html_path, md_path
