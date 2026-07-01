# youtube-to-spec

Turn YouTube videos into structured, LLM-ready knowledge.

`youtube-to-spec` is a two-layer pipeline, shipped as two decoupled skills:

1. **Production** — extract *lossless* metadata and timestamped, segment-structured transcripts from
   one or many videos (or a whole playlist) into clean JSON + Markdown artifacts.
2. **Consumption** — distill those artifacts into a traceable **Module → Feature → Requirement**
   document, where every requirement points back to the exact transcript segment it came from.

The layers are coupled by **one** thing only: a versioned JSON contract (`schema_version`). You can
swap the analysis (requirements, product discovery, business rules, a different doc style) purely by
editing external prompt files — no code changes.

> **Running example.** The snippets below use the video
> [**"What is Claude Code?"**](https://www.youtube.com/watch?v=fl1DSmwQKKY) (`fl1DSmwQKKY`) — a short,
> public, captioned video — end to end: collect its artifact, then distill requirements from it.

---

## Why it's built this way

- **Production ≠ consumption.** The collector never analyses; it produces high-fidelity artifacts.
  Any number of downstream LLM tasks can consume them. Success is measured by artifact quality and
  relational integrity, not by one consumer.
- **Lossless & addressable.** Transcript text is reproduced byte-for-byte; every segment carries a
  stable zero-based `index` (`start`/`duration`/`end`/`text`) so future visual/derived artifacts can
  reference it.
- **Relationships preserved.** Playlists become a `_manifest.json` that records ordered membership,
  per-member status, and a summary — private/deleted/unavailable videos are listed with a reason,
  **never silently dropped** (graceful degradation).
- **Prompt-swappable analysis.** Prompts and templates live in external files and are read at
  runtime, so switching the analysis task requires zero code edits.
- **Built with blind-TDD.** Every unit was implemented by an agent that never saw its tests, from a
  written behavioral spec — implementation was never fit to assertions. 239 offline unit tests.

---

## Repository layout

```
youtube-to-spec/
├── skills/
│   ├── youtube-artifact-collector/     # Skill 1 — production (yt-dlp + youtube-transcript-api)
│   │   ├── SKILL.md
│   │   ├── scripts/extract_artifacts.py
│   │   └── tests/                       # offline unit tier
│   └── spec-distiller/                 # Skill 2 — consumption (Claude-native or OpenAI)
│       ├── SKILL.md
│       ├── scripts/extract_requirements.py
│       ├── prompts/  templates/  .env.example
│       └── tests/
├── tests/integration/                  # opt-in, real network / OpenAI (skipped by default)
└── docs/                               # product brief, roadmap, authoritative plan, specs
```

Everything runs on **[uv](https://docs.astral.sh/uv/)** via inline PEP-723 scripts — no
`pyproject.toml`, no build step. Each script declares its own dependencies in a header.

---

## Skill 1 — `youtube-artifact-collector` (production)

Collect rich metadata **and** timestamped, segment-structured transcripts for one video, several
videos, or an entire playlist, into lossless per-video `JSON` + readable `Markdown`.

```bash
# Single video → data/_singles/fl1DSmwQKKY.json + .md
uv run skills/youtube-artifact-collector/scripts/extract_artifacts.py \
  "https://www.youtube.com/watch?v=fl1DSmwQKKY"

# A bare 11-char id works too, and so does a whole playlist
uv run skills/youtube-artifact-collector/scripts/extract_artifacts.py fl1DSmwQKKY
uv run skills/youtube-artifact-collector/scripts/extract_artifacts.py \
  "https://www.youtube.com/playlist?list=PL..." --playlist

# Inspect a video without writing files
uv run skills/youtube-artifact-collector/scripts/extract_artifacts.py fl1DSmwQKKY --print
```

Key flags: `--playlist`, `--langs tr,en`, `--metadata-only`, `--skip-existing`, `--format json|md|both`,
`--root DIR`. See the skill's [`SKILL.md`](skills/youtube-artifact-collector/SKILL.md).

---

## Skill 2 — `spec-distiller` (consumption)

Turn a Skill 1 artifact (or a whole collection) into a **Module → Feature → Requirement** document.
Two interchangeable engines emit the **same** shape:

- **`claude` (default, offline, no API key)** — Claude reads the artifact + external prompt/template
  files and produces the document in-chat.
- **`openai`** — runs the script against the OpenAI API with `json_schema` structured output.

```bash
# OpenAI engine (needs OPENAI_API_KEY in .env — see skills/spec-distiller/.env.example)
uv run skills/spec-distiller/scripts/extract_requirements.py \
  data/_singles/fl1DSmwQKKY.json --engine openai --print
```

Every requirement has a stable id `<MODULE>-<FEATURE>-<NNN>` and a `trace` back to a real transcript
segment. Distilling the running example — [*"What is Claude Code?"*](https://www.youtube.com/watch?v=fl1DSmwQKKY) —
yields a document shaped like this:

```markdown
### CODE — Claude Code

#### READ — Understand the codebase

- **CODE-READ-001**: The agent reads the existing codebase so its changes fit the surrounding code.
  _(trace: timestamp 00:41, segment 8)_

#### EDIT — Edit files across the repo

- **CODE-EDIT-001**: The agent edits files directly, applying changes across multiple files in one
  task. _(trace: timestamp 01:05, segment 14)_

#### RUN — Run terminal commands

- **CODE-RUN-001**: The agent runs shell commands (build, test, git) on the user's confirmation.
  _(trace: timestamp 01:28, segment 19)_
```

Config precedence is **CLI flag > env var > built-in default**. See
[`SKILL.md`](skills/spec-distiller/SKILL.md).

---

## Testing

```bash
# Offline unit tier (deterministic, no network) — invoke per skill
uv run --with pytest pytest skills/youtube-artifact-collector/tests/     # 122 tests
uv run --with pytest pytest skills/spec-distiller/tests/                 # 125 tests

# Opt-in integration tier — real network / OpenAI; skipped unless explicitly enabled
RUN_INTEGRATION=1 uv run --with pytest --with openai --with python-dotenv \
  pytest tests/integration -m integration
```

The integration tests self-skip when `RUN_INTEGRATION` is unset or the resource (network /
`OPENAI_API_KEY`) is unavailable, so normal runs stay fast, free, and offline.

---

## Tech & design

- **Python** + **uv** PEP-723 inline scripts · **yt-dlp** · **youtube-transcript-api** · **OpenAI**
- Decoupled production/consumption layers · lossless, segment-indexed artifacts · graceful
  degradation · external swappable prompts · structured (`json_schema`) output · blind-TDD

More context in [`docs/`](docs/): the product brief, roadmap, the authoritative implementation plan,
and the per-component behavioral specs.
