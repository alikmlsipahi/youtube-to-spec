# Plan: Two Claude Code Skills for Phase 1 (Artifact Extractor + Requirement/Feature Extractor)

## Context — why we are doing this

While trialing the existing `youtube-transcript` skill on a real video
(`https://youtu.be/fl1DSmwQKKY`), we hit a concrete limitation: the skill's
script **hard-defaults to English** (`api.fetch(video_id)` → `('en',)`) and the
video only had a **Turkish auto-generated** transcript, so it errored out. We
worked around it manually by calling `youtube-transcript-api` with
`languages=["tr"]`. That failure is exactly the kind of gap Phase 1 of this
project is meant to close (language selection, manual/auto type, multi-language
awareness — see `docs/02_PRODUCT_BRIEF.md` § Transcript Artifact'i).

The user is building a hard-coded Python pipeline separately. **In parallel**,
they want a **modular, reusable, Claude-Code-native** way to deliver the Phase 1
capabilities as **skills**. We will build **two** skills:

1. **Skill 1 — Video Artifact Extractor:** input = single video URL, multiple
   URLs, or a playlist URL → fetch rich **metadata + timestamped segment
   transcript** → save lossless **JSON + readable Markdown** per video, with a
   collection manifest preserving playlist→video relationships. Graceful
   degradation over unavailable videos.
2. **Skill 2 — Requirement/Feature Extractor:** input = Skill 1's artifact JSON
   → analyze → produce a **feature-requirement document** (module→feature→
   requirements, req-codes, mini-summary, timestamp traceability, open
   questions) from a **swappable prompt + template**. Default engine =
   **Claude-native** (Claude reads the artifact in-chat, no API key); optional
   **OpenAI** engine per the brief's LLM-integration spec.

Outcome: Phase 1's three capabilities (metadata collection, structured
transcript collection, LLM integration) delivered as two composable skills whose
only coupling is a versioned JSON contract — keeping production/consumption
decoupled per the brief.

## Decisions locked in this session (from the interview)

| Topic | Decision |
|---|---|
| Skill 2 engine | **Configurable / both.** Default Claude-native (offline, no key); optional OpenAI backend via `--engine`. |
| Skill 2 form | **Packaged skill** (not ad-hoc chat) — reusable, swappable prompt/template. |
| Skill 1 metadata tool | **yt-dlp** (no API key; rich metadata; native playlist + graceful skip) + **youtube-transcript-api** for transcripts. |
| Skill 1 storage | **JSON canonical (lossless) + Markdown view** alongside. |
| Transcript language | **Preference list + fallback** (default `--langs tr,en`; if none match, fall back to first available track). Store one track; record language + manual/auto type + full available-track inventory. |
| Relationship to old skill | **New skill, selectively reuse logic** (copy/adapt URL parse, ID extract, timestamp format, fetch pattern). **No runtime dependency** on old skill. Old skill deprecated/deleted **after** new one is verified. |
| File layout | **Per-collection folder + manifest.** Playlist → folder (slug+id) with `<id>.json`/`<id>.md` per video + manifest. Standalone → user-named folder or default `_singles/`. Auto-create dirs. |
| Save behavior | **Default save**; also support **`--print` / no-save** terminal mode. |
| Skill 2 granularity | **Provisional: Both (features → requirements).** Confirmed by real data: playlist = product module, video = feature/task, transcript = requirements. Terminology/ID/schema **deferred** (live in swappable prompt/template). |
| Prompts/templates | **External swappable files** (brief mandate). |
| Script style | **uv inline PEP-723 scripts** (consistent with existing skill); no `pyproject.toml`. Secrets via `.env`; add `.env.example`. |

## Grounding facts verified against the user's real data

- Playlist `PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` = "example | Kayıt Modülü
  Rehberi" (Registration Module guide), 24 visible entries; each video = one
  module task (single/bulk student upload, add parent, edit, delete, merge,
  assign teacher, …). **Confirms Module→Feature→Requirement hierarchy.**
- yt-dlp prints `WARNING: ... 5 unavailable videos are hidden` and **omits** them
  from the flat list (no null entries). Per-video extraction is where individual
  private/deleted failures surface → **that** is where graceful degradation runs.
- **Two-stage extraction required:** flat playlist dump gives playlist metadata +
  thin per-entry fields (id/title/url/duration); description/tags/chapters/
  upload_date need a **per-video** `--dump-json` call.
- Test video `fl1DSmwQKKY`: one track, `tr`, auto-generated, 60 snippets — the
  Turkish-auto-only case to design against.

## Skill 1 — Video Artifact Extractor

**Location:** `.claude/skills/video-artifact-extractor/` (name TBD — see Open
items). Single PEP-723 script `scripts/extract_artifacts.py` (split a
`_ytutil.py` only if it exceeds ~300 lines).

**Script header:**
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp>=2024.0.0", "youtube-transcript-api>=1.0.0"]
# ///
```

**Responsibilities (functions):**
1. `classify_input()` — detect playlist URL vs single vs multiple. A
   `watch?v=...&list=...` URL = **single by default** unless `--playlist`.
2. `enumerate_playlist()` — `yt-dlp --flat-playlist --dump-single-json`; capture
   playlist id/title/uploader, ordered member ids, and the hidden-unavailable
   count from stderr.
3. `fetch_metadata(video_id)` — `yt-dlp --skip-download --dump-json`; on
   failure return `None` and record it (graceful degradation).
4. `fetch_transcript(video_id, langs)` — `YouTubeTranscriptApi().list()` +
   `find_transcript(langs)`, fallback to first track; record selected
   language/type + **full available-track inventory**; store segments
   `{index,start,duration,end,text}`. **Never modify transcript text.**
5. `render_markdown()` — metadata header + `[MM:SS]`/`[HH:MM:SS]` transcript.
6. `write_artifacts()` + `write_manifest()` — file layout (below).
7. Print mode (`--no-save`/`--print`).

**Reuse from `get_transcript.py`:** `extract_video_id()` and
`format_timestamp()` copied verbatim; transcript fetch pattern **upgraded** from
`api.fetch()` to `api.list()` + `find_transcript()` for the language
preference/fallback; PEP-723 header + `main()`/error conventions.

**yt-dlp invocation:** subprocess (`yt-dlp ... --dump-json`) rather than Python
API — stable JSON surface, isolation makes per-video skip trivial.

**Canonical per-video JSON (`<video_id>.json`):** keys `schema_version`,
`kind`, `extracted_at`, `video{ id,url,title,channel,channel_id,uploader,
upload_date,duration_seconds,description,tags,categories,chapters,
default_language,availability }`, `collection{ type,id,title,uploader,
position,total_members }` (null for true singles), `transcript{ available,
selected{language,language_name,type,is_generated}, available_tracks[],
segment_count, segments[] }`, `extraction{ metadata_ok,transcript_ok,
warnings,tool_versions }`. `schema_version` + nested shape lets future artifact
types (visual/OCR per roadmap) be added as sibling keys without rework.

**File layout:**
```
data/
├── example-kayit-modulu-rehberi-PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/
│   ├── _manifest.json
│   ├── <video_id>.json
│   ├── <video_id>.md
│   └── ...
└── _singles/
    ├── <video_id>.json
    └── <video_id>.md
```
Folder slug = `slugify(playlist_title)-<playlist_id>`. Centralize naming in
`collection_dir_name()` / `artifact_basename()` so deferred naming is a one-edit
change. `mkdir(parents=True, exist_ok=True)` (covered by `uv run *` permission;
no settings change needed).

**`_manifest.json`:** `collection{type,id,title,uploader,source_url,
hidden_unavailable_count}`, `members[]` (each: position, video_id, title,
`status` = ok|metadata_failed|skipped_unavailable, files{json,md}|null,
transcript{available,language,type}), `summary{total,ok,failed,no_transcript}`.
Failed videos are **listed with status+reason**, not silently dropped.

**CLI:** `extract_artifacts.py <url_or_id>... [--playlist] [--langs tr,en]
[--out-dir NAME] [--root data] [--no-save|--print] [--format json|md|both]
[--metadata-only] [--skip-existing]`.

## Skill 2 — Requirement/Feature Extractor

**Location:** `.claude/skills/feature-requirement-extractor/` (name TBD).
```
feature-requirement-extractor/
├── SKILL.md                      # Claude-native engine instructions
├── scripts/extract_requirements.py   # OpenAI engine (PEP-723: openai, python-dotenv)
├── prompts/system_prompt.md
├── prompts/extraction_prompt.md  # {{placeholders}}
└── templates/requirement_doc.md
```

**Configurable engine — `--engine claude|openai` (default `claude`):**
- **Claude-native (default, offline):** *no script runs.* `SKILL.md` instructs
  Claude to read the artifact JSON (+ manifest for module context), read the
  prompt + template files, fill the template (req-codes + `[MM:SS]`+segment
  traceability), and write/print the result. Prompts/templates are genuinely
  swappable because Claude reads them as files at runtime.
- **OpenAI (optional):** `extract_requirements.py` loads the **same** external
  prompts/template, fills placeholders, calls OpenAI with **configurable**
  model/temperature/max_tokens/response_format(json_schema)/timeout/retry (CLI >
  env > default; key via `.env`), requests **structured JSON output**, then
  renders Markdown from it. Long-transcript chunking = a `# TODO` seam only
  (Phase 1 videos are short).

**Both engines emit the same output shape** → consumption stays engine-agnostic.

**Output (provisional, schema deferred):** `<video_id>.requirements.md` +
`.requirements.json`. Doc = source header (video url/title/channel/collection) +
mini-summary + Module→Feature→Requirements (`REQ-<video_id>-NNN`, each with
`text` + `trace{timestamp,segment_index}`) + Assumptions & Open Questions. JSON
mirrors it. **Terminology, granularity, ID scheme all live in the swappable
prompt/template** so they change without touching code.

**Input:** path to a `<video_id>.json` artifact, or a collection folder →
iterate `_manifest.json` members with `status: ok`. Coupling is the JSON schema
only.

## SKILL.md descriptions — auto-trigger without collision

Existing `youtube-transcript` triggers on "transcript/subtitles/captions of *a*
video". The new skills must trigger on **collection / artifact / structured
extraction** and **requirement/feature** intent respectively:
- **Skill 1:** "...extract/collect metadata **AND** transcripts for **multiple
  videos or a playlist**, build structured artifacts (JSON+MD) — **not** a quick
  single-video transcript dump." (The explicit negative de-conflicts.)
- **Skill 2:** "...requirement/feature extraction, product discovery, or spec
  doc **from already-extracted artifacts** (Skill 1 JSON). Claude-native default;
  optional OpenAI." (Consumes JSON, not URLs → no overlap.)

## Build sequence & end-to-end verification

1. **Skill 1 single-video core** → `uv run extract_artifacts.py fl1DSmwQKKY
   --print` → expect 60 Turkish auto segments, `type:"auto"`, full metadata,
   `available_tracks` = [tr]. (Exercises the exact fallback that failed in the
   trial.)
2. **Skill 1 save + layout** → run without `--print` → confirm
   `data/_singles/fl1DSmwQKKY.json` + `.md`; JSON validates against schema.
3. **Skill 1 playlist + graceful degradation** → run on the playlist URL →
   expect `data/example-...-PLk.../` with per-video JSON+MD, `_manifest.json`
   (`hidden_unavailable_count: 5`, ordered members, per-video language/type),
   and any per-video failure recorded with `status` ≠ ok while the run
   **continues**.
4. **Skill 1 SKILL.md** → natural-language trigger test ("collect artifacts for
   this playlist").
5. **Skill 2 Claude-native** (prompts/template/SKILL.md) → point Claude at
   `fl1DSmwQKKY.json` → filled requirement doc with req-codes + `[MM:SS]`+segment
   traces matching real segment times (first ≈ `[00:00]`, segment #0).
6. **Skill 2 OpenAI engine** (`.env.example`) → only if user has a key → same
   JSON/MD shape as Claude path.
7. **Deprecate** `youtube-transcript` (separate user-approved step; update
   `skills-lock.json`).

All runs use `uv run *` (already permitted); no new permissions needed.

## Deferred / open items (intentionally not locked)

- **Skill names** — candidates: Skill 1 `video-artifact-extractor` /
  `youtube-artifact-collector`; Skill 2 `feature-requirement-extractor` /
  `artifact-requirement-analyzer`.
- **Output root** — `data/` (recommended; exists, gitignored) vs `artifacts/`.
- **File/manifest naming** — `_manifest.json`, `<id>.json`/`.md`, `_singles/`,
  slug format (centralized in helpers).
- **Skill 2 terminology / granularity / ID scheme / doc+JSON schema** —
  provisional Module→Feature→Requirement, `REQ-<id>-NNN`; lives in prompt/
  template.
- **Default `--langs`** — proposed `tr,en`.
- **Long-transcript chunking** — seam only for Phase 1.
- **`watch?v=...&list=...`** — single by default (recommended) vs expand.
- **Build OpenAI engine now** vs scaffold Claude-native first, add OpenAI when a
  key exists.

## Risks

- **yt-dlp / YouTube fragility & rate-limiting** on 24 sequential per-video
  calls — subprocess isolation + per-video try/except; consider
  `--sleep-requests`; record `tool_versions`.
- **Schema drift** Skill 1 → Skill 2 — `schema_version` + defensive reads.
- **UTF-8 / Turkish text & long descriptions in Markdown** — write UTF-8; keep
  JSON lossless, trim/fence only the MD *view*.

## Critical files

- `.claude/skills/youtube-transcript/scripts/get_transcript.py` — source of
  copied `extract_video_id` / `format_timestamp` / fetch pattern.
- `.claude/skills/video-artifact-extractor/scripts/extract_artifacts.py` — new.
- `.claude/skills/feature-requirement-extractor/SKILL.md` — Skill 2 Claude-native
  engine instructions — new.
- `.claude/skills/feature-requirement-extractor/scripts/extract_requirements.py`
  — Skill 2 OpenAI engine — new.
- `docs/02_PRODUCT_BRIEF.md` — authoritative requirements the schemas satisfy.
