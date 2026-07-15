---
name: youtube-artifact-collector
description: >-
  Collect rich metadata AND timestamped, segment-structured transcripts for
  multiple YouTube videos or a whole playlist, and build lossless structured
  artifacts (per-video JSON + readable Markdown) plus a per-collection manifest
  that preserves playlist→video relationships and degrades gracefully over
  private/deleted/unavailable videos. Use when the user wants to collect,
  archive, or build a dataset/knowledge base from several videos or a playlist —
  e.g. "collect artifacts for this playlist", "extract metadata and transcripts
  for these videos", "build a structured dataset from this channel's tutorials".
  This is NOT a quick single-video transcript dump — for just reading one
  video's captions, use the `youtube-transcript` skill instead.
---

# youtube-artifact-collector

Skill 1 of the YouTube intelligence pipeline — the **production layer**. It turns
one or more video sources into high-quality, LLM-friendly artifacts and never
performs analysis itself. (Downstream analysis is the job of the consumption
layer, e.g. the `spec-distiller` skill.)

## When to use this skill

Use it when the request is about **producing structured artifacts from video
sources**, especially across **multiple videos or a playlist**:

- "Collect metadata and transcripts for this playlist."
- "Build a dataset from these tutorial videos."
- "Archive these videos as structured JSON I can feed to an LLM."

**Do not** use it for a quick one-off "just give me the transcript of this
video" — that is the narrower `youtube-transcript` skill. This skill deliberately
collects metadata **and** transcripts and writes a relational artifact set.

## What it produces

For every video, a lossless canonical **`<slug>.json`** plus a readable
**`<slug>.md`** view, where `<slug>` is the video's title slugified — collection
members are additionally numbered by playlist position (`01-<slug>.json`). For a
collection (playlist or multi-URL run), a **`_manifest.json`** that records the
ordered membership, per-member status, and a summary — failed/unavailable videos
are **listed with their status and reason, never silently dropped**.

Key properties (see `docs/IMPLEMENTATION_PLAN_v2.md` for the canonical schema):

- `schema_version` on every artifact — the only contract the consumption layer
  depends on.
- Transcripts are **segment-based**: each segment carries a stable zero-based
  `index`, `start`, `duration`, `end`, and verbatim `text`. The `index` is a
  load-bearing stable address (future visual/derived artifacts reference it).
- The **selected** transcript track is recorded (language, manual vs. auto)
  alongside the **full track inventory** (`available_tracks`).
- The `collection{}` block links each video to its playlist/collection, and the
  manifest preserves the playlist→ordered-member relationship.
- Transcript text is reproduced **byte-for-byte** — never edited, summarized, or
  reflowed.

## How to invoke

The skill is a single PEP-723 `uv` script — dependencies resolve from the script
header; there is no separate install step.

```bash
uv run skills/youtube-artifact-collector/scripts/extract_artifacts.py \
  <url_or_id>… [flags]
```

`<url_or_id>…` accepts one or more YouTube **video URLs**, bare **11-character
video IDs**, or a **playlist URL**, mixed freely.

### Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--playlist` | off | Treat a `watch?v=…&list=…` URL as the **whole playlist**. By default such a URL is collected as the **single video** only. |
| `--langs tr,en` | `tr,en` | Transcript language preference list, in order. Within a language a **manual** track is preferred over an **auto** one; if no preferred language matches, falls back to the **first available** track. |
| `--out-dir NAME` | derived | Override the collection directory name (default is `<slug(title)>-<playlist_id>`). |
| `--root DIR` | `data` | Output root directory, resolved relative to the current working directory. |
| `--no-save` / `--print` | off | Print the artifacts to stdout instead of writing files to disk. |
| `--format json\|md\|both` | `both` | Which per-video artifact files to write. |
| `--metadata-only` | off | Skip transcript fetching; collect metadata only. |
| `--skip-existing` | off | Skip videos whose artifact files already exist under the output root. |
| `--sleep-requests N` | off | Jittered sleep before each yt-dlp request (except the first) — a random delay in `[N, 2*N)` seconds, not a fixed `N`, to avoid a bot-like fixed-interval pattern. Applies before failed requests too (so repeated failures don't hot-loop); `--skip-existing` hits never touch the network and stay free. |

### Examples

```bash
# Single video → data/_singles/what-is-claude-code.json + .md
uv run …/extract_artifacts.py fl1DSmwQKKY

# A watch?v=…&list=… URL, collected as just the video (default)
uv run …/extract_artifacts.py "https://www.youtube.com/watch?v=fl1DSmwQKKY&list=PLxxxx"

# The same URL, but collect the entire playlist
uv run …/extract_artifacts.py "https://www.youtube.com/watch?v=fl1DSmwQKKY&list=PLxxxx" --playlist

# Several videos at once, preferring English transcripts
uv run …/extract_artifacts.py vid1 vid2 vid3 --langs en,tr

# Inspect one video without writing files
uv run …/extract_artifacts.py fl1DSmwQKKY --print
```

## Output layout

```
data/
├── <slug(title)>-<playlist_id>/      # one folder per collection
│   ├── _manifest.json                #   ordered membership + status + summary
│   ├── 01-<slug>.json                #   lossless canonical artifact
│   ├── 01-<slug>.md                  #   readable view
│   ├── 02-<slug>.json
│   └── …
└── _singles/                         # standalone (true single) videos
    ├── <slug>.json
    └── <slug>.md
```

## Artifact naming

A basename is the video's title, slugified — the same `slugify` that builds the
collection folder name, so Turkish characters transliterate to ASCII and the result
is filesystem-safe.

- **Collection members** are prefixed with their playlist position (`01-`, `02-`, …),
  zero-padded to the member count so lexical order matches playlist order. Standalone
  videos get no prefix.
- **A boilerplate prefix shared by every member's title is dropped.** A series whose
  titles all read `edesis | Kayıt Modülü Nasıl Kullanılır? …` yields
  `01-tek-tek-ogrenci-yukleme.json`, not a 55-character prefix repeated 19 times. The
  prefix is only dropped when at least three titles agree on it and no member would be
  left with an empty name.
- **The video id is the fallback**, used whenever a title yields no usable slug — a
  private/deleted member with no title, an emoji-only title, or a script that
  transliterates away entirely. It is also appended to disambiguate two standalone
  videos that share a title.

`_manifest.json` records each member's actual filenames under `files{json,md}`, so
consumers resolve artifacts through the manifest rather than reconstructing names.

## Graceful degradation

Each video is fetched in isolation. A private, deleted, or otherwise
unavailable video does **not** abort the run: its metadata fetch returns nothing,
the run records the member as `metadata_failed` (or `skipped_unavailable`) with a
reason, and continues. Playlists also report `hidden_unavailable_count` — the
number of members YouTube hides from the listing — parsed from yt-dlp's warning.

## Tooling

- **yt-dlp** — metadata and playlist enumeration (run via subprocess for stable
  JSON and per-video isolation).
- **youtube-transcript-api** — transcript tracks and segments.

Two helpers (`extract_video_id`, `format_timestamp`) are copied verbatim from the
older `youtube-transcript` skill; there is no runtime dependency on it.

## Scope

Phase 1 only collects **metadata** and **transcripts**. Visual/OCR/entity and
other derived artifact types are out of scope (see `docs/03_ROADMAP.md`), but the
`schema_version`'d artifact model is designed to host them later as sibling keys
without reworking existing types.
