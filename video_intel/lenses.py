"""Dedicated, timestamp-linked presentation for the six expansion lenses."""

import re

from video_intel.report import esc, link, md, single_line, time_link

TITLES = {"steps": "Steps", "mentions": "Mentions", "hook": "Hook and retention",
          "sources": "Cited sources", "tone": "Tone and persuasion", "actions": "Actions"}


def render_lens(name, lens, url):
    h, m = [], []

    def paragraph(text, t=None):
        stamp = f"{time_link(t, url)} " if t is not None else ""
        stamp_md = f"{time_link(t, url, True)} " if t is not None else ""
        h.append(f"<p>{stamp}{esc(text)}</p>")
        m.extend([stamp_md + md(text), ""])

    def heading(text):
        text = single_line(text)
        h.append(f"<h3>{esc(text)}</h3>")
        m.extend([f"### {md(text)}", ""])

    def bullets(values):
        h.append("<ul>" + "".join(f"<li>{esc(v)}</li>" for v in values) + "</ul>")
        m.extend([*[f"- {md(v)}" for v in values], ""])

    def source(label, destination):
        if destination:
            h.append(f"<p>{link(label, destination)}</p>")
            m.extend([link(label, destination, True), ""])

    if name == "steps":
        paragraph(lens["goal"])
        heading("Prerequisites")
        bullets(lens["prerequisites"])
        for index, step in enumerate(lens["steps"], 1):
            h.append("<article>")
            heading(f"{index}. {step['action']}")
            paragraph("Tools: " + ", ".join(step["tools"]), step["t"])
            if step["command"] is not None:
                h.append(f"<pre><code>{esc(step['command'])}</code></pre>")
                # Pick a fence longer than any run of backticks inside literal code.
                fence = "`" * max(3, 1 + max((len(v) for v in re.findall(r"`+", step["command"])), default=0))
                m.extend([fence, step["command"], fence, ""])
            if step["warning"]:
                paragraph("Warning: " + step["warning"])
            h.append("</article>")
        heading("Outcome")
        paragraph(lens["outcome"])
    elif name == "mentions":
        for item in lens:
            h.append("<article>")
            heading(item["name"])
            paragraph(f"{item['type']} · {item['sentiment']} · {'Verified' if item['verified'] else 'Unverified'}", item["t"])
            paragraph(item["context"])
            source("Official source", item["url"])
            if item["retrieved"]:
                paragraph("Retrieved: " + item["retrieved"])
            h.append("</article>")
    elif name == "sources":
        for item in lens:
            h.append("<article>")
            heading(item["cited_as"])
            paragraph(item["what_is_claimed"], item["t"])
            paragraph(f"Specificity: {item['specificity']} · Found: {item['found']} · Supports: {item['supports']}")
            source(item["publisher"] or "Source", item["url"])
            paragraph(f"Published: {item['published'] or 'unknown'} · Retrieved: {item['retrieved']}")
            paragraph(item["note"])
            h.append("</article>")
    elif name == "actions":
        for item in lens:
            h.append("<article>")
            heading(f"{item['id']}: {item['action']}")
            paragraph(f"Priority: {item['priority']} · Effort: {item['effort']}", item["t"])
            paragraph(item["why"])
            if item["depends_on"] is not None:
                paragraph("Depends on: " + item["depends_on"])
            h.append("</article>")
    elif name == "tone":
        paragraph(", ".join(lens["overall"]["descriptors"]))
        paragraph(lens["overall"]["note"])
        for title, key in (("Tone shifts", "shifts"), ("Persuasion techniques", "techniques"), ("Bias signals", "bias_signals")):
            heading(title)
            for item in lens[key]:
                if key == "shifts":
                    text = f"{item['from']} → {item['to']}"
                else:
                    text = item.get("technique", item.get("signal", ""))
                paragraph(text, item["t"])
                if "quote" in item:
                    paragraph(item["quote"])
                paragraph(item["note"])
        heading("Disclosure")
        disclosure = lens["disclosure"]
        paragraph(f"Sponsored: {disclosure['sponsored']} · Affiliate: {disclosure['affiliate']} · Disclosed: {disclosure['disclosed']}")
        for item in disclosure["evidence"]:
            paragraph(item["quote"], item["t"])
    elif name == "hook":
        hook = lens["hook"]
        heading(f"Opening hook · {hook['type']} · {hook['rating']}/5")
        paragraph(hook["why"], hook["t_end"])
        if hook["spoken"]:
            paragraph("Spoken: " + hook["spoken"])
        paragraph("On screen: " + hook["on_screen"])
        heading("Structure")
        for part in lens["structure"]:
            paragraph(f"{part['part']}: {part['summary']}", part["t_start"])
            paragraph("Ends", part["t_end"])
        heading("Pacing")
        pacing = lens["pacing"]
        paragraph(f"Duration: {pacing['duration']}s · Cuts/10s: {pacing['cuts_per_10s']} · Words/minute: {pacing['words_per_minute'] if pacing['words_per_minute'] is not None else '—'}")
        paragraph(pacing["note"])
        heading("On-screen text")
        for item in lens["on_screen_text"]:
            paragraph(f"{item['role']}: {item['text']}", item["t"])
        heading("Retention tactics")
        for item in lens["retention"]:
            paragraph(f"{item['tactic']}: {item['note']}", item["t"])
        heading("Why it works")
        bullets(lens["why_it_works"])
        heading("Reusable template: " + lens["template"]["name"])
        paragraph(f"Length: {lens['template']['length_s']}s")
        for item in lens["template"]["slots"]:
            paragraph(f"{item['part']}: {item['instruction']}")
            paragraph("Example: " + item["example"])
        heading("Weaknesses")
        bullets(lens["weaknesses"])
    return "\n".join(h), "\n".join(m)
