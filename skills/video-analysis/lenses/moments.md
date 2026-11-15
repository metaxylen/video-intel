# Lens: moments

Shows where in the video the viewer should jump to.

## Extract
- 5-15 moments: topic change, main claim, demo, result, call to action (CTA).
- Each moment has `t` (seconds, computed from the nearest `[mm:ss]` in the transcript), a short `title` (at most 8 words) and a one-sentence `note`.

## Rules
- Sort chronologically; `t` stays within the video's `duration`.
- Take `t` from a timestamp that exists in the transcript. This keeps every jump link accurate.
- The title describes what is said, without commentary.

Done when every moment's `t` matches a real transcript timestamp and the list covers each major topic change.

## JSON
```json
"moments": [{"t": 125, "title": "string", "note": "string"}]
```
