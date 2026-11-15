# Lens: claims

Checks the video's most consequential, verifiable claims against the web. The shape follows Google's ClaimReview. Write text values in the user's language.

## Selection
- 5-10 claims. Pick the ones that most affect the viewer's decisions or behaviour and that evidence can settle: numbers, dates, scientific, technical, financial or health claims, "X does Y".
- `kind`: `fact`, `opinion`, `prediction` or `advice`. Opinions and predictions cannot be checked: verdict `not-checkable`, `rating` `null`. They may be listed, but the 5-10 quota is filled by checkable claims.
- `claim_reviewed`: the claim stated neutrally and understandable on its own, at most 75 characters. `quote`: a short verbatim quote from the video, with `t` in seconds.

## Research (for each claim)
1. Run WebSearch with at least 3 different queries: the claim, the opposite claim, and the number or name phrased differently. One result is not enough.
2. Open the source with WebFetch and read it. Preference order: primary source (official document, paper, dataset), reputable publisher, expert. The video itself, or a link it gives, counts as a lead and needs independent confirmation.
3. Look for sources on both sides, supporting and contradicting, so the verdict reflects the whole evidence.
4. When sources are missing or conflict, use `not-enough-evidence` with `confidence: low`. A verdict rests on evidence.
5. `snippet`: at most 25 words, in the source's own words. `retrieved`: today's date (`YYYY-MM-DD`). `published`: the page's date when it shows one.
6. In ASR transcripts numbers and names may be garbled. When in doubt, search for the correct spelling first and note it in `rationale`.

## Verdict
`verdict` and `rating`: `true` 5, `mostly-true` 4, `half-true` 3, `mostly-false` 2, `false` 1. For `not-enough-evidence` and `not-checkable`, `rating` is `null`. `rationale` is 1-3 sentences: which evidence led to this verdict and why.

Done when every listed claim has a verdict, and every verdict other than `not-checkable` and `not-enough-evidence` has at least one opened source in `evidence`.

## JSON
```json
"claims": [{
  "id": "c1", "claim_reviewed": "string (<=75 chars)", "quote": "string", "t": 312,
  "kind": "fact|opinion|prediction|advice",
  "verdict": "true|mostly-true|half-true|mostly-false|false|not-enough-evidence|not-checkable",
  "rating": 1, "confidence": "low|medium|high",
  "rationale": "string",
  "evidence": [{"url": "string", "publisher": "string", "published": "string|null", "retrieved": "YYYY-MM-DD", "snippet": "string (<=25 words)"}]
}]
```
