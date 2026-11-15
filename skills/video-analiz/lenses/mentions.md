# Lens: mentions

Finds the people, products, tools, companies, books and links named in the video and verifies on the web what they really are. Write text values in the user's language.

## Extract
- For each mention: `name` (correct spelling), `type` (`person|product|tool|company|book|link|other`), `t` (seconds of first mention), `context` (why it comes up in the video, one sentence), `sentiment` (`positive|neutral|negative|ad`; use `ad` when it looks like an advertisement or partnership), `url` (the official page found in research) or `null`, `retrieved` (`YYYY-MM-DD`) or `null`, `verified` (`true|false`).
- A thing mentioned many times gets one row, with `t` of the first mention.
- 3-25 rows: things the viewer would want to look up. Generic words ("a", "internet") do not qualify.

## Research
1. Run WebSearch for each row (name plus a context word from the video). Open the official site, repo or publisher page with WebFetch and confirm that the name and the description match.
2. When found, fill `url` and `retrieved` and set `verified: true`. When not found, set `url: null` and `verified: false`. Candidate URLs you did not open stay out, since an unverified link misleads the reader.
3. ASR garbles proper names ("Klod", "Kursor"). First look for the correct spelling in the frames or the description, otherwise search phonetic variants on the web. Write the corrected form in `name` and note in `context` how ASR rendered it.
4. A link the video itself gives (description, on-screen text) is a lead. Confirm the official domain through independent research. Report shortened links (bit.ly) as they are, without opening them.

Done when every row is either `verified: true` with an opened source, or `verified: false` with `url: null`.

## JSON
```json
"mentions": [{"name": "string", "type": "person|product|tool|company|book|link|other", "t": 140, "context": "string", "sentiment": "positive|neutral|negative|ad", "url": "string|null", "retrieved": "YYYY-MM-DD|null", "verified": true}]
```
Example: `{"name": "yt-dlp", "type": "tool", "t": 140, "context": "Recommended for downloading the video", "sentiment": "positive", "url": "https://github.com/yt-dlp/yt-dlp", "retrieved": "2026-11-15", "verified": true}`
