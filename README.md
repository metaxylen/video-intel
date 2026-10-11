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

## Note

This tool only uses publicly available YouTube caption data. You are responsible for complying with copyright and YouTube’s terms of use.
