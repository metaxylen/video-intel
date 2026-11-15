# video-intel

Turn a video link from **YouTube, Instagram, X/Twitter, TikTok** (or any single-video [yt-dlp](https://github.com/yt-dlp/yt-dlp) site) into a timestamped transcript, frame images, and a fact-checked HTML report.

- **Transcript:** platform captions first; when there are none, the audio is transcribed locally with [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (`whisper-large-v3-turbo`, Apple Silicon). No API key, nothing leaves the machine.
- **Frames:** scene-change keyframes so an agent can read on-screen text, slides, code and products (reels are often text-on-screen with music).
- **Report:** a self-contained `report.html` + `report.md` rendered from an `analysis.json` that an agent writes: summary, key moments, fact-checked claims with sources, mentions, actions, tutorial steps, short-video hook analysis, cited sources, tone and sponsorship, plus multi-video comparison.
- **Claude skill included:** [`skills/video-analiz`](skills/video-analiz/SKILL.md) tells an agent how to fetch, analyse with pluggable *lenses*, research claims on the web, and render the report.

The split is deliberate: the CLI does the deterministic work (download, transcribe, validate, render) and is fully tested offline; the agent does the thinking (analysis, web research, verdicts).

## Install

Requirements: Python 3.10+, `ffmpeg` on `PATH` (`brew install ffmpeg`), Apple Silicon for local transcription.

```bash
uv tool install --editable '.[asr]' --force     # from a checkout
# or
uv tool install 'video-intel[asr] @ git+https://github.com/metaxylen/video-intel.git'
```

Check the setup (no network, no downloads):

```bash
video-intel doctor
```

## Quick start

```bash
video-intel fetch --lang tr,en "https://www.youtube.com/watch?v=VIDEO_ID"
video-intel fetch --frames "https://www.instagram.com/reel/SHORTCODE/"
video-intel fetch --file urls.txt                   # one URL per line, # comments allowed
video-intel fetch --start 01:10 --end 02:30 URL     # only a window of a long video
video-intel report ~/video-reports/2026-11-15-youtube-title     # after analysis.json is written
video-intel report --compare ~/video-reports/2026-11-15-compare-topic/compare.json
```

Each URL prints exactly one line on stdout, `OK <url> -> <run_dir>` or `FAIL <url> <CODE> <message>`, then `Summary:`. Diagnostics go to stderr. Exit status is 1 if any URL failed; later URLs still run.

### Verified platforms (live, 2026-11-15)

| Platform | Result |
|---|---|
| YouTube | captions in ~4 s; forced ASR ~20 s for a short clip |
| Instagram reel | anonymous audio track + ASR; old posts that expose only video-only formats return `NO_AUDIO` |
| X / Twitter | ASR |
| TikTok | ASR; some posts return `BLOCKED` for the IP |

## Run directory

`fetch` publishes `YYYY-MM-DD-<platform>-<slug>/` under `--out`, `VIDEO_INTEL_OUT`, or `~/video-reports` (a numeric suffix on collisions; existing runs are never overwritten; failures leave nothing behind):

| File | Content |
|---|---|
| `meta.json` | id, title, uploader, upload date, duration, description, counts, platform |
| `transcript.json` | `source` (`captions-manual`, `captions-auto`, `asr`, `none`), `model`, `language`, `segments` `[{start, end, text}]`, optional `window` |
| `transcript.md` | readable transcript with `[mm:ss]` paragraphs and an ASR caveat |
| `frames/*.jpg`, `frames.json` | with `--frames` / `video-intel frames RUN_DIR`: 512 px JPEGs named by second, `[{t, path}]` |
| `analysis.json` | written by the agent (schema below) |
| `report.html`, `report.md` | written by `video-intel report` |

## Options

| Flag | Meaning |
|---|---|
| `--lang tr,en` | caption language preference (default: the video's original language) |
| `--asr auto\|force\|never` | ASR fallback policy; `--asr-lang auto\|tr\|en`; `--keep-audio` |
| `--frames`, `--max-frames N`, `--every S`, `--keep-video` | frame extraction (scene changes `> 0.3` plus an interval fallback, 24 frames by default) |
| `--start T --end T` | focus window (SS, MM:SS, HH:MM:SS); timestamps stay relative to the full video |
| `--file urls.txt` | batch input |
| `--cookies-from-browser SPEC` | opt-in browser cookies, yt-dlp syntax `BROWSER[+KEYRING][:PROFILE][::CONTAINER]`; off by default because a logged-in session can get the account restricted |
| `--out DIR` | output root |

## Error codes

| Code | Meaning / next step |
|---|---|
| `LOGIN_REQUIRED` | login/age/account gate; use browser cookies only with the account owner's permission |
| `RATE_LIMITED` | too many requests; retry later |
| `BLOCKED` | the platform blocks this IP; cookies or another network |
| `NO_AUDIO` | video served without an audio track; use `--frames` for on-screen text (with `--frames` the fetch continues with `source: "none"`) |
| `UNAVAILABLE` | removed, private or geo-restricted |
| `NO_TRANSCRIPT` | no captions and ASR disabled or not installed |

Invalid cookie specs are usage errors (exit 2).

## Analysis schema and reports

The agent writes `analysis.json` against [`analysis.schema.json`](video_intel/schema/analysis.schema.json) (comparisons: [`compare.schema.json`](video_intel/schema/compare.schema.json)):

```json
{
  "schema_version": 1,
  "transcript_source": "captions-manual",
  "asr_model": null,
  "lenses": {
    "summary": {"tldr": "…", "key_points": ["…"], "audience": null},
    "moments": [{"t": 65, "title": "Key moment", "note": "Why it matters."}],
    "claims": [{
      "id": "c1", "claim_reviewed": "≤75 chars", "quote": "…", "t": 312, "kind": "fact",
      "verdict": "mostly-true", "rating": 4, "confidence": "medium", "rationale": "…",
      "evidence": [{"url": "https://…", "publisher": "…", "published": null, "retrieved": "2026-11-15", "snippet": "≤25 words"}]
    }]
  },
  "caveats": []
}
```

Optional `"report_language": "tr"` or `"report_language": "en"` selects all report interface labels (also supported in `compare.json`). Without it, the renderer uses `transcript.json` language when it is `tr` or `en`, otherwise English; comparison uses the first available transcript. Analysis prose is preserved.

Known lenses (`summary`, `moments`, `claims`, `mentions`, `actions`, `steps`, `hook`, `sources`, `tone`) get dedicated sections; any other lens renders generically, so a new lens needs no code change. Claims follow Google's [ClaimReview](https://developers.google.com/search/docs/appearance/structured-data/factcheck) shape. Metadata from `meta.json` always wins over the agent's copy.

`report.html` is a single file: inline CSS/JS, no external requests (CSP `default-src 'none'`), light/dark, mobile-first at 390 px, sticky table of contents, a proportional verdict bar and five-dot truth meters, claim search and filters, copy-as-Markdown, print layout. The full transcript starts collapsed and can be searched. Frame images are embedded in the HTML as JPEG data URLs, in a lazy-loaded horizontal gallery. All text is escaped and links are restricted to http(s). Timestamps deep-link on YouTube; other platforms show plain times.

## Claude skill

[`skills/video-analiz`](skills/video-analiz) is the agent side: modes (direct answer, report, compare), error handling, lens selection, claim research rules, and [`evals/`](skills/video-analiz/evals) in the `claude plugin eval` layout. Install by copying or symlinking the folder into `~/.claude/skills/video-analiz` (and `~/.codex/skills/` for Codex). Add a lens by adding one `lenses/<name>.md` file.

The copy in this repo is synced from the maintainer's skills folder with `scripts/sync-skill.sh`.

## Tests

```bash
uv tool install --editable '.[asr,dev]' --force
~/.local/share/uv/tools/video-intel/bin/python -m pytest -q
python3 -m unittest discover -s tests -q      # stdlib subset
```

All tests run offline; yt-dlp, ffmpeg and mlx-whisper are mocked.

## Legacy command: `yt-captions-md`

The original YouTube-captions-to-Markdown CLI still ships unchanged:

```bash
yt-captions-md --lang tr,en --timestamps --out ~/yt-transcripts "https://www.youtube.com/watch?v=VIDEO_ID"
yt-captions-md --file urls.txt
```

Flags: `--lang`, `--timestamps`, `--out` (default `./output` or `YT_CAPTIONS_OUT`), `--file/-f`. Output: `OK URL -> path` / `FAIL URL: reason`, exit 1 on any failure. Sample outputs live in [`output/`](output).

## Project layout

```
video_intel/          fetch, ASR, frames, window, doctor, report, compare, validation
video_intel/schema/   analysis + compare JSON schemas
youtube_transcript/   legacy CLI and shared caption helpers
skills/video-analiz/  Claude skill (SKILL.md, lenses/, evals/)
docs/                 design spec
tests/                offline test suite
```

## Note on use

Platform terms restrict downloading and redistribution. Keep outputs private, quote briefly, and do not republish media. Cookies are never read unless you pass `--cookies-from-browser`.

## License

[MIT](LICENSE)
