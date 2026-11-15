# Lens: summary

Gives someone who never watched the video the gist in 30 seconds. Write all text values in the user's language (default: the language the user wrote in).

## Extract
- `tldr`: 2-3 sentences with the video's main claim and its conclusion.
- `key_points`: 3-8 items, one sentence each, each grounded in something said in the transcript.
- `audience`: who the video addresses, one sentence, or `null` when unclear.

## Rules
- Mark anything you inferred rather than read in the transcript as an inference, so the reader can tell it from what the speaker said.
- Follow the video's own order and merge repetitions.

Done when `tldr` states the claim and conclusion and every key point maps to a passage in the transcript.

## JSON
```json
"summary": {"tldr": "string", "key_points": ["string"], "audience": "string|null"}
```
