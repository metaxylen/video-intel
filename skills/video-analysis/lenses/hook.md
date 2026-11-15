# Lens: hook

A creator's view of a short video (Shorts, Reels, TikTok): what holds the viewer and how to adapt the same approach to their own content. Write text values in the user's language.

When there is no speech or only music (common in reels), run the lens on the `frames/*.jpg` frames. An empty transcript is a reason to use the frames.

## Extract
- `hook`: the first 3 seconds. `t_end` (second the hook ends), `type` (`question|bold-claim|pattern-interrupt|story-open|result-first|curiosity-gap|other`), `spoken` (the sentence said, or `null`), `on_screen` (text or visual in the first frames), `rating` (1-5: how hard it makes swiping away in the first 3 seconds) and `why` (one sentence).
- `structure`: sections in order: `{"part": "hook|value|proof|cta|loop", "t_start": sec, "t_end": sec, "summary": "..."}`. Follow the hook, value, CTA skeleton and list only the parts present; describe a missing part in `retention` or `why_it_works`.
- `pacing`: `duration` (sec), `cuts_per_10s` (estimated from frames and transcript; say it is an estimate in `note`), `words_per_minute` (when there is speech) or `null`, `note`.
- `on_screen_text`: text read from frames `[{"t": sec, "text": "...", "role": "hook|label|caption|cta|watermark"}]`. Copy the text exactly as seen in the frame; include only what is legible.
- `retention`: retention tactics used, each `{"t": sec, "tactic": "...", "note": "..."}` (e.g. open loop, counter, cut, text emphasis, sound or music change, "watch to the end" promise, looping ending).
- `why_it_works`: 2-4 items, each naming one mechanism (curiosity gap, fast proof, identity call) with an anchor from the video.
- `template`: a reusable skeleton: `{"name": "...", "slots": [{"part": "hook|value|cta", "instruction": "...", "example": "..."}], "length_s": sec}`. Write it topic-independent, so that applying it only requires filling the slots.
- `weaknesses`: where the video loses viewers (slow start, vague CTA); an empty list when none.

## Rules
- Take every timestamp from the transcript or a frame name (`0012.34.jpg` = 12.34 s). For a moment with no frame or transcript line, leave the entry out, since an invented `t` breaks the anchor.
- The hook is the first thing that holds attention before the speech gets going, which is different from the video's topic.
- Tie every finding to a concrete moment and word from this video; generic advice ("use a good hook") adds nothing.
- When the duration exceeds 3 minutes the lens still runs; add "not a short video" to `caveats`.

Done when `hook`, `structure`, `pacing` and `template` are filled, and every `t` comes from the transcript or a frame name.

## JSON
```json
"hook": {
  "hook": {"t_end": 3, "type": "result-first", "spoken": "string|null", "on_screen": "string", "rating": 4, "why": "string"},
  "structure": [{"part": "hook|value|proof|cta|loop", "t_start": 0, "t_end": 3, "summary": "string"}],
  "pacing": {"duration": 28, "cuts_per_10s": 6, "words_per_minute": 170, "note": "string"},
  "on_screen_text": [{"t": 1, "text": "string", "role": "hook"}],
  "retention": [{"t": 12, "tactic": "string", "note": "string"}],
  "why_it_works": ["string"],
  "template": {"name": "string", "slots": [{"part": "hook", "instruction": "string", "example": "string"}], "length_s": 30},
  "weaknesses": ["string"]
}
```
