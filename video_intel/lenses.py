"""Dedicated, timestamp-linked presentation for the six expansion lenses."""

import re

from video_intel.report import esc, link, md, single_line, time_link, lens_text
from video_intel.presentation import label

TITLES = {"steps": "Steps", "mentions": "Mentions", "hook": "Hook and retention",
          "sources": "Cited sources", "tone": "Tone and persuasion", "actions": "Actions"}


def render_lens(name, lens, url, language="en"):
    h, m = [], []
    tr = lambda key: label(key, language)

    def paragraph(text, t=None):
        stamp = f"{time_link(t, url)} " if t is not None else ""
        stamp_md = f"{time_link(t, url, True)} " if t is not None else ""
        h.append(f"<p>{stamp}{lens_text(text, url)}</p>")
        m.extend([stamp_md + md(text), ""])

    def heading(text):
        text = single_line(text)
        h.append(f"<h3>{lens_text(text, url)}</h3>")
        m.extend([f"### {md(text)}", ""])

    def bullets(values):
        h.append("<ul>" + "".join(f"<li>{lens_text(v, url)}</li>" for v in values) + "</ul>")
        m.extend([*[f"- {md(v)}" for v in values], ""])

    def source(label, destination):
        if destination:
            h.append(f"<p>{link(label, destination)}</p>")
            m.extend([link(label, destination, True), ""])

    if name == "steps":
        paragraph(lens["goal"])
        heading(tr("prerequisites"))
        bullets(lens["prerequisites"])
        for index, step in enumerate(lens["steps"], 1):
            h.append("<article>")
            heading(f"{index}. {step['action']}")
            paragraph(tr("tools") + ": " + ", ".join(step["tools"]), step["t"])
            if step["command"] is not None:
                h.append(f"<pre><code>{esc(step['command'])}</code></pre>")
                # Pick a fence longer than any run of backticks inside literal code.
                fence = "`" * max(3, 1 + max((len(v) for v in re.findall(r"`+", step["command"])), default=0))
                m.extend([fence, step["command"], fence, ""])
            if step["warning"]:
                paragraph(tr("warning") + ": " + step["warning"])
            h.append("</article>")
        heading(tr("outcome"))
        paragraph(lens["outcome"])
    elif name == "mentions":
        for item in lens:
            h.append("<article>")
            heading(item["name"])
            paragraph(f"{tr(item['type'])} · {tr(item['sentiment'])} · {tr('verified') if item['verified'] else tr('unverified')}", item["t"])
            paragraph(item["context"])
            source(tr("official"), item["url"])
            if item["retrieved"]:
                paragraph(tr("retrieved") + ": " + item["retrieved"])
            h.append("</article>")
    elif name == "sources":
        for item in lens:
            h.append("<article>")
            heading(item["cited_as"])
            paragraph(item["what_is_claimed"], item["t"])
            paragraph(f"{tr('specificity')}: {tr(item['specificity'])} · {tr('found')}: {tr(item['found'])} · {tr('supports')}: {tr(item['supports'])}")
            source(item["publisher"] or tr("source"), item["url"])
            paragraph(f"{tr('published')}: {item['published'] or tr('unknown')} · {tr('retrieved')}: {item['retrieved']}")
            paragraph(item["note"])
            h.append("</article>")
    elif name == "actions":
        for item in lens:
            h.append("<article>")
            heading(f"{item['id']}: {item['action']}")
            paragraph(f"{tr('priority')}: {tr(item['priority'])} · {tr('effort')}: {tr(item['effort'])}", item["t"])
            paragraph(item["why"])
            if item["depends_on"] is not None:
                paragraph(tr("depends_on") + ": " + item["depends_on"])
            h.append("</article>")
    elif name == "tone":
        paragraph(", ".join(lens["overall"]["descriptors"]))
        paragraph(lens["overall"]["note"])
        for title, key in ((tr("shifts"), "shifts"), (tr("techniques"), "techniques"), (tr("bias_signals"), "bias_signals")):
            heading(title)
            for item in lens[key]:
                if key == "shifts":
                    text = f"{item['from']} → {item['to']}"
                else:
                    text = item.get("technique", item.get("signal", ""))
                paragraph(tr(text), item["t"])
                if "quote" in item:
                    paragraph(item["quote"])
                paragraph(item["note"])
        heading(tr("disclosure"))
        disclosure = lens["disclosure"]
        paragraph(f"{tr('sponsored')}: {tr(disclosure['sponsored'])} · {tr('affiliate')}: {tr(disclosure['affiliate'])} · {tr('disclosed')}: {tr(disclosure['disclosed'])}")
        for item in disclosure["evidence"]:
            paragraph(item["quote"], item["t"])
    elif name == "hook":
        hook = lens["hook"]
        heading(f"{tr('opening')} · {tr(hook['type'])} · {hook['rating']}/5")
        paragraph(hook["why"], hook["t_end"])
        if hook["spoken"]:
            paragraph(tr("spoken") + ": " + hook["spoken"])
        paragraph(tr("on_screen") + ": " + hook["on_screen"])
        heading(tr("structure"))
        for part in lens["structure"]:
            paragraph(f"{tr(part['part'])}: {part['summary']}", part["t_start"])
            paragraph(tr("ends"), part["t_end"])
        heading(tr("pacing"))
        pacing = lens["pacing"]
        paragraph(f"{tr('duration')}: {pacing['duration']}s · {tr('cuts')}: {pacing['cuts_per_10s']} · {tr('wpm')}: {pacing['words_per_minute'] if pacing['words_per_minute'] is not None else '—'}")
        paragraph(pacing["note"])
        heading(tr("on_screen_text"))
        for item in lens["on_screen_text"]:
            paragraph(f"{tr(item['role'])}: {item['text']}", item["t"])
        heading(tr("retention"))
        for item in lens["retention"]:
            paragraph(f"{tr(item['tactic'])}: {item['note']}", item["t"])
        heading(tr("why_it_works"))
        bullets(lens["why_it_works"])
        heading(tr("template") + ": " + lens["template"]["name"])
        paragraph(f"{tr('length')}: {lens['template']['length_s']}s")
        for item in lens["template"]["slots"]:
            paragraph(f"{tr(item['part'])}: {item['instruction']}")
            paragraph(tr("example") + ": " + item["example"])
        heading(tr("weaknesses"))
        bullets(lens["weaknesses"])
    return "\n".join(h), "\n".join(m)
