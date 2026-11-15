# Lenses

A lens is one kind of analysis extracted from a video's transcript (and from frame images when needed) in report mode.

## Available lenses
| Lens | File | When |
|---|---|---|
| summary | `summary.md` | default |
| moments | `moments.md` | default |
| claims | `claims.md` | default; web research |
| mentions | `mentions.md` | default; web research |
| actions | `actions.md` | default |
| hook | `hook.md` | shorts/reels/TikTok, content creation |
| steps | `steps.md` | tutorial/how-to |
| sources | `sources.md` | the video cites sources; web research |
| tone | `tone.md` | persuasion, advertising, bias questions |
| (comparison) | `compare.md` | multiple videos |

When the user asks for "deep" or "all", every lens runs. Selection rules live in SKILL.md.

## Adding a lens
1. Create `lenses/<name>.md` with: what to extract, the rules, the full JSON shape for `lenses.<name>` in `analysis.json` (with field types), a small example, and a completion condition. The main anchor is `t` (seconds).
2. Add one line for it to the lens-selection list in SKILL.md. No code change is needed: `video-intel report` renders known lenses with a dedicated section and unknown lenses generically (key/value pairs and lists).
3. Use flat, small structures the schema accepts: strings, numbers, lists, nesting at most two levels (`hook` and `tone` are the upper limit).
4. When the user asks for specific lenses, run only those; `analysis.json` contains only the lenses that ran.

## Candidate future lenses
- marketing-angle: competitor and marketing angle
- sentiment flow (partly covered by `shifts` in `tone`)
