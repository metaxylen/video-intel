# Lens: sources

Extracts the sources the speaker says they rely on (study, report, person, book, data, "according to a study") and checks that each source exists and says what is claimed. It differs from `claims`: that lens asks whether a claim is true, this one asks whether the cited source really supports it. Write text values in the user's language.

## Extract
- For each citation: `cited_as` (as said in the video, a short quote), `t`, `what_is_claimed` (what is attributed to the source, one sentence), `specificity` (`named|vague`; "studies show" is vague), `found` (`true|false`), `url` or `null`, `publisher`, `published` or `null`, `retrieved` (`YYYY-MM-DD`), `supports` (`yes|partly|no|unclear`), `note` (1-2 sentences: what the source actually says and where it differs).
- List vague citations too, with `found: false`, `supports: unclear`, and what you searched for in `note`.

## Research
1. Run WebSearch on the source's title, author, institution or figure, with at least 2 queries: one with the exact title in quotes, one with author plus year.
2. Open the page with WebFetch and locate the attributed sentence or data. A summary page is not enough. Prefer the primary source (paper, official report, dataset) over secondary coverage; when you only found a secondary one, say so in `note`.
3. Judge `supports` only from the text you opened: does the figure match, do sample and scope fit the video's use, is there a contrary result. When the page could not be opened, use `unclear`.
4. Put a short quote from the source (at most 25 words) in `note`. `retrieved` is today's date.
5. For a garbled name from ASR (author, journal), search for the correct spelling first. When still in doubt, set `found: false` and state why.
6. A link in the video's own description is a starting lead. Confirm through independent sources.

Done when each citation has `found` and `supports` set from an opened page, or `supports: unclear` with the reason in `note`.

## JSON
```json
"sources": [{"cited_as": "string", "t": 205, "what_is_claimed": "string", "specificity": "named|vague", "found": true, "url": "string|null", "publisher": "string|null", "published": "string|null", "retrieved": "YYYY-MM-DD", "supports": "yes|partly|no|unclear", "note": "string"}]
```
Example: `{"cited_as": "Stanford 2023 study", "t": 205, "what_is_claimed": "Sleep deprivation reduces attention by 30%", "specificity": "named", "found": true, "url": "https://...", "publisher": "Stanford", "published": "2023-05-02", "retrieved": "2026-11-15", "supports": "partly", "note": "The study reports an 18% drop."}`
