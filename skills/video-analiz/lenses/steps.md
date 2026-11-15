# Lens: steps

Turns a tutorial or how-to video into steps the viewer can follow without opening the video. Write text values in the user's language; keep commands and code exactly as shown.

## Extract
- `goal`: the outcome the video teaches (one sentence).
- `prerequisites`: what is needed before starting (account, installed tool, version, file); an empty list when none.
- `steps`: in order, one action each. Each step has `t` (seconds), `action` (imperative, one sentence), `tools` (tool, menu or site used in the step), `command` (the command or code spoken or shown on screen, verbatim) or `null`, `warning` (a pitfall the video flags) or `null`.
- `outcome`: what should work after the last step.

## Rules
- Write commands and code exactly as in the transcript or as read from on-screen text in the frames. When an ASR-sourced command is doubtful (a flag, a package name), keep it as heard and put "verify" in `warning`, so the reader checks it instead of trusting a guess.
- When the video skips a step that is needed (for example installation), leave it out of `steps` and record the gap in `caveats`.
- Where on-screen text matters (code, URL, setting name), read `frames/*.jpg`. A spoken "click here" often has its target in the frame.
- Follow the video's real flow: keep its step boundaries unless splitting or merging has a concrete reason.

Done when every step has a `t`, each command is verbatim from a transcript line or frame, and `outcome` states a checkable end state.

## JSON
```json
"steps": {
  "goal": "string", "prerequisites": ["string"],
  "steps": [{"t": 95, "action": "string", "tools": ["string"], "command": "string|null", "warning": "string|null"}],
  "outcome": "string"
}
```
Example step: `{"t": 95, "action": "Install the dependencies", "tools": ["terminal"], "command": "npm install", "warning": null}`
