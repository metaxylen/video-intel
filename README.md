# YT Captions MD

A small CLI that turns YouTube video captions into **Markdown** files in one command.

No API key required. Captions come from [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api); title and channel metadata from [yt-dlp](https://github.com/yt-dlp/yt-dlp) (metadata only — no video download).

## Features

- **URL formats:** `youtube.com/watch`, `youtu.be`, `shorts`, extra query params (`&t=`, `&list=`, …)
- **Caption selection:** Manual captions first, then auto-generated; optional `--lang` preference order
- **Readable text:** Merges caption fragments and deduplicates common auto-caption overlaps
- **Markdown output:** Title, URL, channel, language, and caption type in the header
- **Safe filenames:** Derived from the video title; on collision, the video ID is appended (no silent overwrite)
- **Resilience:** Skips bad URLs and missing captions; retries network errors up to 3 times with exponential backoff

## Requirements

- Python **3.10+**
- Network access

## Install

### Global CLI (any directory, any terminal)

Install once so agents and shells can call `yt-captions-md` without opening this repo:

```bash
pip install --user /path/to/yt-captions-md
# or from GitHub:
pip install --user git+https://github.com/metaxylen/yt-captions-md.git
```

Ensure your user scripts directory is on `PATH` (macOS/Linux), e.g. `~/.local/bin` or `~/Library/Python/3.x/bin`.

Optional: default output folder everywhere (instead of `./output` in the current directory):

```bash
export YT_CAPTIONS_OUT="$HOME/yt-transcripts"
```

### Development (repo checkout)

```bash
git clone https://github.com/metaxylen/yt-captions-md.git
cd yt-captions-md
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

```bash
# After global install (from anywhere)
yt-captions-md "https://www.youtube.com/watch?v=VIDEO_ID"
python -m youtube_transcript URL

# From a repo checkout
python main.py URL

# Multiple videos
yt-captions-md URL1 URL2

# From a file (one URL per line; blank lines and # comments ignored)
yt-captions-md --file urls.txt

# Language preference, paragraph timestamps, output directory
yt-captions-md --lang tr,en --timestamps --out ~/yt-transcripts URL
```

### Calling from another agent or terminal

An agent with shell access can run this tool directly. After the global install
above, it can call the following command from any working directory:

```bash
yt-captions-md --lang tr,en --timestamps \
  --out "$HOME/yt-transcripts" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Replace `VIDEO_ID` with the actual video ID. Keep the URL quoted so shell
characters such as `&` are passed to the tool correctly.

If the tool is installed in the repo's `.venv` instead, use the executable's
absolute path. This works without activating the virtual environment or changing
the agent's working directory:

```bash
"/absolute/path/to/yt-captions-md/.venv/bin/yt-captions-md" \
  --lang tr,en --timestamps \
  --out "/absolute/path/to/transcripts" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Replace both example paths with paths on the agent's machine. The checkout and
its installed dependencies must be accessible in that agent's environment.
Use an absolute `--out` path to choose where the Markdown files are saved;
otherwise the default `output` folder is relative to the working directory
(unless `YT_CAPTIONS_OUT` is set).

Example instruction to give another agent:

> Run `/absolute/path/to/yt-captions-md/.venv/bin/yt-captions-md` with the supplied
> YouTube URL, `--lang tr,en --timestamps`, and
> `--out /absolute/path/to/transcripts`. Read the generated Markdown file from
> the path printed in the `OK` message.

Use `--help` to inspect the available options. The command exits with `0` when
all videos succeed and `1` when any video fails. It prints successful file paths
as `OK URL -> path` and reports failures as `FAIL URL: reason`.

### Options

| Flag | Description |
|------|-------------|
| `--lang tr,en` | Comma-separated language codes; manual captions preferred over auto-generated |
| `--timestamps` | Prefix each paragraph with `[mm:ss]` |
| `--out <dir>` | Output directory (default: `./output`, or `YT_CAPTIONS_OUT` if set) |
| `--file`, `-f` | Path to a URL list file |

## Example output

```markdown
# Video Title

- URL: https://www.youtube.com/watch?v=...
- Channel: Channel Name
- Language: en
- Type: manual

---

Transcript body here, one paragraph per line without blank lines between them...
```

## Project layout

```
├── main.py                 # CLI entrypoint
├── youtube_transcript/
│   ├── urls.py             # Video ID parsing
│   ├── transcript.py       # Fetch captions and retries
│   ├── metadata.py         # Title / channel via yt-dlp
│   ├── markdown.py         # Merge logic and document format
│   ├── files.py            # Filename sanitization and writes
│   └── cli.py              # CLI implementation
├── video_intel/            # Multi-platform fetch and offline report commands
│   └── schema/             # Bundled analysis v1 JSON schema
├── tests/
├── pyproject.toml
└── requirements.txt
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)

## video-intel

`video-intel` adds multi-platform transcript acquisition and offline analysis
reports. `yt-captions-md` continues to work as before. Supported platforms include
YouTube, Instagram, X/Twitter, TikTok, and other single-video yt-dlp URLs.

```bash
video-intel fetch --lang tr,en "https://www.youtube.com/watch?v=VIDEO_ID"
video-intel fetch --asr never --out ./video-reports URL1 URL2
video-intel fetch --asr force --asr-lang tr --keep-audio URL
# Equivalent from a checkout, without installing the console script:
python -m video_intel fetch --lang tr,en URL
```

Acquisition tries the existing YouTube caption API first, then yt-dlp manual
subtitles or automatic captions (VTT/srv3), then local speech recognition (ASR).
`--lang` lists preferred caption languages; `--asr auto|force|never` controls
fallback, and `--asr-lang auto|tr|en` controls speech recognition. Manual captions
are preferred within each caption provider.

ASR requires Apple Silicon, `ffmpeg` on `PATH`, and the optional extra:

```bash
uv tool install --editable '.[asr]' --force
```

The ASR model is explicitly `mlx-community/whisper-large-v3-turbo`, never Whisper's
tiny default. An existing model cache is reused; the first uncached use may
download model weights. ASR audio is converted to 16 kHz mono WAV and cleaned up
on both success and failure, unless `--keep-audio` retains it in the run's `audio/`
folder. Without the extra, caption acquisition and report rendering still work;
an ASR attempt reports an actionable `NO_TRANSCRIPT` error.

Each fetch reserves a new `YYYY-MM-DD-<platform>-<slug>/` directory, appending a
numeric suffix on collisions. It contains `meta.json`, timestamped
`transcript.json` segments (`start`, `end`, `text`), and merged `transcript.md`.
The output root is `--out`, then `VIDEO_INTEL_OUT`, then `~/video-reports`.
Interrupted or failed ASR runs can leave a reserved directory; retrying creates
a new directory without overwriting it.

Cookies are disabled by default. Explicitly opt in only when appropriate:

```bash
video-intel fetch --cookies-from-browser 'chrome:Profile 1' URL
```

This forwards yt-dlp's `BROWSER[+KEYRING][:PROFILE][::CONTAINER]` syntax.
Using a logged-in account may expose it to platform restrictions. Failures use
`LOGIN_REQUIRED`, `RATE_LIMITED`, `UNAVAILABLE`, or `NO_TRANSCRIPT` codes.
Transient network failures retry with backoff. Each URL prints `OK URL -> RUN_DIR`
or `FAIL URL ERROR_CODE MESSAGE`, followed by a `Summary:` line. One failed URL
makes the batch exit with status 1; later URLs still run.

### Analysis and reports

Part A does not generate analyses or perform web fact-checking. An agent or a
human writes `analysis.json` inside the run directory using the shipped
[v1 schema](video_intel/schema/analysis.schema.json). Minimal example (video
metadata is merged from `meta.json`):

```json
{
  "schema_version": 1,
  "transcript_source": "captions-manual",
  "asr_model": null,
  "lenses": {
    "summary": {
      "tldr": "A short, transcript-grounded summary.",
      "key_points": ["The main takeaway."],
      "audience": null
    },
    "moments": [{"t": 65, "title": "Key moment", "note": "Why it matters."}],
    "claims": []
  },
  "caveats": []
}
```

```bash
video-intel report ./video-reports/YYYY-MM-DD-youtube-title
python -m video_intel report ./video-reports/YYYY-MM-DD-youtube-title
```

Validation uses a small built-in validator, with no `jsonschema` dependency.
Validation errors exit nonzero before writing reports. Known lenses (`summary`,
`moments`, `claims`) receive dedicated sections; future lenses render recursively
as keys and lists. Claim titles are limited to 75 characters and evidence snippets
to 25 words, with dates, verdicts, ratings, and confidence validated.

`report.html` uses inline CSS, system fonts, automatic light/dark colours, and a
responsive layout for 390px screens. It makes no external resource requests.
Transcript and claim text are escaped, source links use HTTP(S), and timestamps
link to the source (`&t=` on YouTube). `report.md` carries the same analysis,
evidence, and transcript. Report generation replaces generated report files but
does not modify the input analysis, metadata, or transcript.

Run all tests without network access (yt-dlp and ASR integrations are mocked):

```bash
python3 -m pytest -q
```

## Note

This tool only uses publicly available YouTube caption data. You are responsible for complying with copyright and YouTube’s terms of use.
