# Compare mode

When two or more videos (run directories) cover the same topic, write one `compare.json`. Write text values in the user's language.

## Step 1: one analysis per video
Run Report mode for each video first: at least `summary` and `claims`, researched, written to that run's `analysis.json` and rendered with `video-intel report RUN_DIR`. The comparison links each video id to that run's `report.html`, and its verdicts reuse the per-video claim research, so skipping this step leaves dead links and unresearched verdicts. Step 1 is done when every run directory has `analysis.json` and `report.html`.

## Step 2: the comparison

### Fields
- `schema_version`: `1`; `report_language`: `tr` or `en` (sets the comparison page's labels).
- `topic`: the shared topic (one sentence).
- `videos`: `[{"id": "v1", "run_dir": "...", "title": "...", "creator": "..."}]`. Keep `id` short and stable; every other field refers to videos by it.
- `common_claims`: a claim at least two videos make: `{"claim": "...", "videos": [{"id": "v1", "t": sec}, ...], "verdict": "...", "note": "..."}`. `verdict` is one of the `claims` lens values or `not-checked`.
- `contradictions`: where videos disagree: `{"topic": "...", "positions": [{"id": "v1", "t": sec, "says": "..."}, {"id": "v2", "t": sec, "says": "..."}], "resolution": "which side the evidence supports, or unclear", "evidence": [{"url": "...", "publisher": "...", "retrieved": "YYYY-MM-DD", "snippet": "<=25 words"}]}`.
- `who_says_what`: a matrix by point: `[{"point": "...", "stances": [{"id": "v1", "stance": "supports|opposes|nuanced|silent", "t": sec|null, "note": "..."}]}]`; every video appears under every `point`.
- `unique_points`: a valuable point only one video brings: `[{"id": "v1", "t": sec, "point": "..."}]`.
- `verdict_overall`: 2-4 sentences: which video explains what better, and which to trust or distrust and why.

## Rules
- Match agreements and disagreements by meaning, beyond text overlap. When two videos give different numbers, record it under `contradictions` and resolve it with a source.
- Research each contradiction on the web, following the `claims.md` rules. Without evidence, set `resolution` to "unclear".
- Every entry carries an `id` and `t`, so each statement can be traced to a moment in a video.

Done when every shared or conflicting point from the per-video analyses appears in `common_claims` or `contradictions`, every contradiction is researched, and `compare.json` passes the renderer's schema check.

## Output
Write `~/video-reports/YYYY-MM-DD-compare-<slug>/compare.json` with `videos[].run_dir` as absolute paths. Then render it:
```bash
video-intel report --compare ~/video-reports/YYYY-MM-DD-compare-<slug>/compare.json
```
This writes `compare.html` and `compare.md` next to `compare.json`. On a schema error, read the error lines, fix `compare.json` and run again until none remain.
