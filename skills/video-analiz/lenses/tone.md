# Lens: tone

Describes how the speaker talks and steers the audience: tone, persuasion techniques, bias signals, sponsorship or affiliate disclosure. It assesses form, while `claims` assesses whether the content is true. Write text values in the user's language.

## Extract
- `overall`: the dominant tone as 2-4 descriptors (e.g. "smug, fast, anxiety-inducing") plus a one-sentence rationale.
- `shifts`: tone changes `[{"t": sec, "from": "...", "to": "...", "note": "..."}]`; an empty list when there are none.
- `techniques`: persuasion techniques `[{"t": sec, "technique": "scarcity|urgency|social-proof|authority|fear|anecdote|false-dichotomy|emotional-appeal|flattery|other", "quote": "short verbatim quote", "note": "..."}]`.
- `bias_signals`: signs of one-sided presentation `[{"t": sec, "signal": "...", "note": "..."}]` (opposing view never mentioned, selective statistics, loaded wording, vague "experts").
- `disclosure`: `{"sponsored": "yes|likely|no|unknown", "affiliate": "yes|likely|no|unknown", "disclosed": true|false|null, "evidence": [{"t": sec, "quote": "..."}]}`. Indicators: "this video is sponsored by", a discount code, "link below", disproportionate praise of a product, a partnership note in the description. Check the description (`meta.json`) and on-screen text as well.

## Rules
- Support every finding with a verbatim quote and `t`. A general verdict like "persuasive" without a quote carries no evidence.
- Name the technique and describe what is said, leaving intent unread ("uses scarcity" rather than "manipulates"). Use `likely` only when a concrete indicator exists.
- A speaker can use a persuasion technique while saying something true. List the technique and keep any judgment measured, in `note`.

Done when every entry in `shifts`, `techniques`, `bias_signals` and `disclosure.evidence` has a `t` and quote, and `disclosure` is filled after checking transcript, description and frames.

## JSON
```json
"tone": {
  "overall": {"descriptors": ["string"], "note": "string"},
  "shifts": [{"t": 60, "from": "string", "to": "string", "note": "string"}],
  "techniques": [{"t": 45, "technique": "urgency", "quote": "string", "note": "string"}],
  "bias_signals": [{"t": 120, "signal": "string", "note": "string"}],
  "disclosure": {"sponsored": "unknown", "affiliate": "likely", "disclosed": false, "evidence": [{"t": 300, "quote": "string"}]}
}
```
