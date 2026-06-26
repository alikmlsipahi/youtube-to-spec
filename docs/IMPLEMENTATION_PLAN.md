# Implementation Plan — Two Phase-1 Skills: `youtube-artifact-collector` + `feature-requirement-extractor`

> Status: **implementation-ready.** This supersedes `docs/claude_plans/implementation-plan-draft.md`
> by locking every previously-deferred decision (interview, this session) and folding in the
> verified grounding from `02_PRODUCT_BRIEF.md` / `03_ROADMAP.md` and the existing skill code.

## Context — why we are building this

Phase 1 of this project (see `CLAUDE.md`, `docs/02_PRODUCT_BRIEF.md`) requires three capabilities:
metadata collection, structured timestamped transcript collection, and LLM integration. The existing
`youtube-transcript` skill is too narrow — its script hard-defaults to English
(`api.fetch(video_id)`), so a Turkish auto-generated-only video (`fl1DSmwQKKY`) errors out. We deliver
Phase 1 as **two composable, Claude-Code-native skills** whose only coupling is a versioned JSON
contract, keeping the **production layer** (artifact extraction) decoupled from the **consumption
layer** (requirement analysis) exactly as the brief mandates.

- **Skill 1 — `youtube-artifact-collector`:** single URL / multiple URLs / playlist → rich metadata +
  timestamped segment transcript → lossless JSON + readable Markdown per video, with a per-collection
  manifest preserving playlist→video relationships and graceful degradation over unavailable videos.
- **Skill 2 — `feature-requirement-extractor`:** Skill 1's artifact JSON → Module→Feature→Requirement
  document via a swappable external prompt + template. Default **Claude-native** engine (offline, no
  API key, reads files in-chat); **OpenAI** engine built fully alongside it.

## Locked decisions

From the original interview (carried over from the draft):

| Topic | Decision |
|---|---|
| Skill 2 engine | Configurable; default Claude-native (offline), optional OpenAI via `--engine`. |
| Skill 2 form | Packaged skill with external swappable prompt/template. |
| Skill 1 tooling | **yt-dlp** (metadata, playlist, graceful skip) + **youtube-transcript-api** (transcripts). |
| Storage | JSON canonical (lossless) + Markdown view alongside. |
| Transcript language | Preference list + fallback to first available track; store one track + full inventory. |
| Old skill | New skill, selectively reuse logic, no runtime dependency; deprecate `youtube-transcript` after verification. |
| Layout | Per-collection folder + manifest; standalone → `_singles/`. Auto-create dirs. |
| Save behavior | Default save; also `--print` / no-save terminal mode. |
| Prompts/templates | External swappable files. |
| Script style | uv inline PEP-723 scripts; no `pyproject.toml`. Secrets via `.env` + `.env.example`. |

Newly locked this session:

| Open item | **Decision** |
|---|---|
| **Skill 1 name** | **`youtube-artifact-collector`** |
| **Skill 2 name** | **`feature-requirement-extractor`** |
| **Output root** | **`data/`** (already exists, already gitignored — `.gitignore:34`) |
| **Default `--langs`** | **`tr,en`** (then fallback to first available track) |
| **`watch?v=…&list=…`** | **Single video by default**; whole playlist only with explicit `--playlist`. |
| **OpenAI engine** | **Build fully now** (configurable model/temp/max_tokens/response_format/timeout/retry, json_schema structured output). |
| **Long-transcript chunking** | **Seam + `# TODO` only** for Phase 1 (brief says "evaluate", not "implement"). |
| **Skill 2 ID scheme** | **Custom domain-coded `<MODULE>-<FEATURE>-<NNN>`** — see Skill 2 below. |
| **File/manifest naming** | `_manifest.json`, `<video_id>.json` / `<video_id>.md`, `_singles/`, slug = `slugify(title)-<id>` — centralized in helpers so it stays a one-edit change. |

## Grounding verified against the brief & real data

- **Segment addressability is load-bearing.** `03_ROADMAP.md:53` requires future screenshot artifacts to
  reference a specific transcript segment/chunk. Each transcript segment therefore carries a stable
  `index` that downstream artifact types address — keep it now even though visuals are out of scope.
- Brief transcript requirements (`02_PRODUCT_BRIEF.md` §Transcript Artifact'i): full text, preserved
  timestamps, auto-caption support, **multi-language distinguishable**, language recorded, **type
  manual|auto recorded**, segment-based structure. Our `transcript{}` block satisfies all.
- Brief metadata requirements (§Metadata Artifact'i): id, url, title, playlist/collection, channel,
  description, publish date, duration, chapters, tags, "other meaningful fields" + schema must accept
  new fields later → our open-ended `video{}` block + `schema_version` satisfy this.
- Brief LLM config surface (§LLM Entegrasyonu): model, temperature, max tokens, response format,
  timeout, retry, batch/concurrency, **+ extensible**; secrets via env; prompts external & swappable;
  send transcript+metadata; single/multi video; structured/parseable output. OpenAI engine honors all.
- Relational integrity (§İlişkisel Bütünlük): every artifact explicitly linked to its video and
  collection; playlist grouping is a first-class preserved relation → `collection{}` block + manifest.
- Two-stage yt-dlp extraction confirmed: `--flat-playlist` gives playlist meta + thin per-entry fields;
  description/tags/chapters/upload_date need a per-video `--dump-json`. yt-dlp omits the 5 hidden
  unavailable videos from the flat list and warns on stderr.

## Reuse from the existing skill (verified locations)

Source: `.claude/skills/youtube-transcript/scripts/get_transcript.py`
- `extract_video_id()` (lines 19–29) — **copy verbatim**.
- `format_timestamp()` (lines 32–39) — **copy verbatim** (already does MM:SS / HH:MM:SS).
- PEP-723 header (lines 1–5) + `main()`/argparse/`except Exception → stderr → sys.exit(1)` convention
  (lines 55–72) — **copy the pattern**.
- Transcript fetch (lines 42–52) uses `YouTubeTranscriptApi().fetch()` (v1.x, `.snippets` with
  `.start`/`.text`) — **upgrade** to `.list()` + `find_transcript(langs)` + fallback to first track.

SKILL.md frontmatter convention (`.claude/skills/youtube-transcript/SKILL.md:1-4`): YAML `---` with
`name` + `description`; description = capability sentence + explicit `Use when …` trigger clause.

`skills-lock.json` lives at **repo root** (not under `.claude/`); only the GitHub-sourced
`youtube-transcript` has an entry. Hand-authored skills need no lock entry; deprecation step edits this.

`.gitignore`: `data/` ignored (line 34); `.env`/`.env.*` ignored but `!.env.example` un-ignored
(lines 18–21) — env workflow already prepared.

---

## Skill 1 — `youtube-artifact-collector`

**Location:** `.claude/skills/youtube-artifact-collector/`
- `SKILL.md`
- `scripts/extract_artifacts.py` (single PEP-723 script; split a `_ytutil.py` only if >~300 lines)

**Script header:**
```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp>=2024.0.0", "youtube-transcript-api>=1.0.0"]
# ///
```

**Functions:**
1. `classify_input(args)` — playlist URL vs single vs multiple. `watch?v=…&list=…` → **single** unless `--playlist`.
2. `enumerate_playlist(url)` — `yt-dlp --flat-playlist --dump-single-json`; capture playlist id/title/uploader, ordered member ids, and `hidden_unavailable_count` parsed from stderr WARNING.
3. `fetch_metadata(video_id)` — `yt-dlp --skip-download --dump-json` via subprocess; on failure return `None` + record (graceful degradation). Subprocess (not Python API) for stable JSON + per-video isolation.
4. `fetch_transcript(video_id, langs)` — `YouTubeTranscriptApi().list()` + `find_transcript(langs)`, fallback to first track; record selected language/type + **full available-track inventory**; segments `{index,start,duration,end,text}`. **Never modify transcript text.**
5. `render_markdown(artifact)` — metadata header + `[MM:SS]`/`[HH:MM:SS]` transcript via `format_timestamp`.
6. `write_artifacts()` + `write_manifest()` — layout below; `mkdir(parents=True, exist_ok=True)`.
7. Helpers `collection_dir_name()` / `artifact_basename()` — centralize all naming.
8. Print mode (`--no-save` / `--print`).

**Canonical per-video JSON (`<video_id>.json`):**
```jsonc
{
  "schema_version": "1.0",
  "kind": "video_artifact",
  "extracted_at": "<iso8601>",
  "video": { "id","url","title","channel","channel_id","uploader",
             "upload_date","duration_seconds","description","tags",
             "categories","chapters","default_language","availability" },
  "collection": { "type","id","title","uploader","position","total_members" }, // null for true singles
  "transcript": {
    "available": true,
    "selected": { "language","language_name","type","is_generated" },
    "available_tracks": [ /* full inventory: lang, name, is_generated, is_translatable */ ],
    "segment_count": 60,
    "segments": [ { "index":0,"start":0.0,"duration":3.2,"end":3.2,"text":"…" } ] // index = stable addressable id
  },
  "extraction": { "metadata_ok","transcript_ok","warnings","tool_versions" }
}
```
`schema_version` + nested shape lets roadmap artifact types (visual/OCR/segmentation/entities) be added
as sibling keys without rework. `transcript.segments[].index` is the stable address roadmap §53 needs.

**File layout (root = `data/`):**
```
data/
├── <slug(title)>-<playlist_id>/
│   ├── _manifest.json
│   ├── <video_id>.json
│   ├── <video_id>.md
│   └── …
└── _singles/
    ├── <video_id>.json
    └── <video_id>.md
```

**`_manifest.json`:** `collection{type,id,title,uploader,source_url,hidden_unavailable_count}`,
`members[]` (position, video_id, title, `status` = ok|metadata_failed|skipped_unavailable,
`files{json,md}`|null, `transcript{available,language,type}`), `summary{total,ok,failed,no_transcript}`.
Failed videos are **listed with status+reason**, never silently dropped.

**CLI:**
```
extract_artifacts.py <url_or_id>… [--playlist] [--langs tr,en] [--out-dir NAME]
  [--root data] [--no-save|--print] [--format json|md|both] [--metadata-only]
  [--skip-existing] [--sleep-requests N]
```

**SKILL.md trigger** (de-conflict with `youtube-transcript`): "…collect metadata **AND** transcripts for
**multiple videos or a playlist** and build structured artifacts (JSON+MD) — **not** a quick
single-video transcript dump." Explicit negative prevents collision.

---

## Skill 2 — `feature-requirement-extractor`

**Location:** `.claude/skills/feature-requirement-extractor/`
```
feature-requirement-extractor/
├── SKILL.md                          # Claude-native engine instructions + trigger
├── scripts/extract_requirements.py   # OpenAI engine (PEP-723: openai, python-dotenv)
├── prompts/system_prompt.md
├── prompts/extraction_prompt.md      # {{placeholders}} + the module/action code lookup table
├── templates/requirement_doc.md
└── .env.example                      # OPENAI_API_KEY=…
```

**Engine — `--engine claude|openai` (default `claude`):**
- **Claude-native (default, offline):** *no script runs.* `SKILL.md` instructs Claude to read the
  artifact JSON (+ `_manifest.json` for module context), read the prompt + template files, fill the
  template, and write/print the result. Genuinely swappable because Claude reads the files at runtime.
- **OpenAI (built fully now):** `extract_requirements.py` loads the **same** external prompts/template,
  fills placeholders, calls OpenAI with **configurable** model / temperature / max_tokens /
  response_format(json_schema) / timeout / retry / concurrency (**precedence CLI > env > default**; key
  from `.env`), requests **structured JSON output**, then renders Markdown from it. Long-transcript
  chunking = a single `# TODO` seam only.

**Both engines emit the same output shape** → consumption stays engine-agnostic.

**Requirement ID scheme (locked) — `<MODULE>-<FEATURE>-<NNN>`:**
- **MODULE** — 3–6 char uppercase; the LLM normalizes it from the playlist/collection title
  (e.g. "Kayıt Modülü" → `REG`, exam → `EXAM`, attendance → `ATTND`).
- **FEATURE** — 3–10 char, `ACTION` or `ACTION-ENTITY`, derived from video title + transcript
  (e.g. `ADD-STU`, `BULK-DEL`, `GRADE`).
- **NNN** — **video-local**, starts at `001`.
- **Cross-video uniqueness** is guaranteed by the **composite key `requirement_id` + `source_video_id`**,
  not by embedding the video id in the code. `video_id` **never** appears in the ID; it lives in the
  `trace{}` block.
- A **module/action lookup table lives in the prompt file** so codes evolve without touching code.
- **Consolidation / global renumbering is a separate, later stage** (not Phase 1).

**Output:** `<video_id>.requirements.md` + `<video_id>.requirements.json`. Doc = source header
(video url/title/channel/collection) + mini-summary + Module→Feature→Requirements (each requirement:
`id`=`<MODULE>-<FEATURE>-<NNN>`, `text`, `source_video_id`, `trace{timestamp,segment_index}`) +
Assumptions & Open Questions. JSON mirrors the doc. Terminology, granularity, and the code lookup all
live in the swappable prompt/template.

**Input:** path to a `<video_id>.json` artifact, **or** a collection folder → iterate `_manifest.json`
members with `status: ok`. Coupling is the JSON schema (`schema_version`) only; defensive reads.

**SKILL.md trigger:** "…requirement/feature extraction, product discovery, or spec doc **from
already-extracted artifacts** (Skill 1 JSON). Claude-native default; optional OpenAI." (Consumes JSON,
not URLs → no overlap with the other skills.)

---

## Test strategy & bias-free (blind) TDD workflow

**Core rule (user mandate):** for every *testable* requirement that needs code, a unit test is written
**first**, by an agent whose context is then discarded; the implementation is then written by a
**separate, fresh agent that is structurally prevented from ever seeing the tests** (path denylist).
Code is written only from a natural-language **behavioral spec** + acceptance criteria + the canonical
schema — never from assertions. This prevents "teach-to-the-test" code that passes assertions but
breaks on real input. A single context cannot truly *forget* what it read, so isolation is realized as
**distinct agents with no shared context**, not as self-discipline.

**Tech stack**
- Runner: `pytest`, invoked `uv run --with pytest pytest <path>` (no pyproject; matches PEP-723 style).
- Mocks: pytest `monkeypatch` + captured JSON fixtures (no live network in the unit tier).
- Tiers: **unit** (offline, deterministic, default) and **integration** (`@pytest.mark.integration`,
  real network/OpenAI, **skipped by default**, run with `-m integration`; OpenAI ones auto-skip without a key).
- Layout per skill: `.claude/skills/<skill>/tests/` with `test_*.py`, `conftest.py`,
  `fixtures/inputs/` (captured real yt-dlp / transcript / OpenAI samples) and `fixtures/expected/`
  (golden outputs — **test-only**).

**Roles — each a fresh agent, no shared context**
1. **Spec author (orchestrator):** per testable unit, writes a behavioral contract — signature, inputs,
   expected behavior in prose, edge cases, acceptance criteria. Contains **no test code**.
2. **Test-writer agent:** reads spec + acceptance criteria, captures fixtures, writes `tests/`. Returns
   only file paths + test counts (**never** assertion text). Context discarded after.
3. **Implementer agent:** given the spec + signatures + canonical schema **only**. **Denylist:** must
   not open `tests/**`, `**/conftest.py`, `**/fixtures/**`. Writes the script; does **not** run tests.
4. **Verifier agent:** runs the suite and **translates each failure into a plain-language behavioral
   gap** (e.g. "does not emit HH:MM:SS past one hour"), stripping all assertion/line detail.
5. **Reviser = fresh implementer:** receives only the NL behavioral gaps + spec + current code (no
   tests). Loop verifier↔reviser, **max 3 iterations**, then escalate to the human.

**Anti-leak rules**
- No code-writing context (orchestrator, implementer, reviser) ever reads files under `tests/`. **Only
  the Verifier reads tests**, and it emits NL gaps only — assertion text never reaches a writer.
- Fixtures split: `fixtures/inputs/` (real inputs the code parses — not biasing) vs `fixtures/expected/`
  (golden outputs — the bias risk). The implementer sees neither; spec + schema carry input-shape knowledge.
- The progress checklist records only states, never assertions.

**Per-component loop:** spec → test-writer → (fresh) blind implementer → verifier (NL gaps) → reviser
loop → green → tick checklist.

## Testable requirements → unit tests (catalog)

Each row = one requirement with a stable id used by the checklist. **Pure/offline unless noted.**

*Skill 1 — `youtube-artifact-collector` (`scripts/extract_artifacts.py`):*
| id | unit | what the test pins down |
|---|---|---|
| T-S1-01 | `extract_video_id` | all URL forms + raw 11-char id; `watch?v=…&list=…` → video id; invalid → `ValueError` |
| T-S1-02 | `format_timestamp` | `MM:SS` under 1h; `HH:MM:SS` at/over 1h; `0`→`00:00`; fractional floored |
| T-S1-03 | `classify_input` | single / multiple / playlist; `watch?v=…&list=…`→single; `--playlist`→playlist |
| T-S1-04 | `slugify`/`collection_dir_name` | Turkish chars (ı ş ğ ü ö ç) → ascii; spaces→`-`; appends `-<playlist_id>` |
| T-S1-05 | `build_video_block` | captured yt-dlp JSON → canonical `video{}` keys; missing optional fields tolerated |
| T-S1-06 | `select_transcript_track` | preference match; fallback to first when no pref; records lang/type/is_generated + full inventory (mocked tracks) |
| T-S1-07 | `build_segments` | snippets → `{index,start,duration,end,text}`; index from 0; **text byte-identical**; `end=start+duration` |
| T-S1-08 | `render_markdown` | header has title/url/channel/collection; first line `[00:00]`; >1h uses `HH:MM:SS` |
| T-S1-09 | `build_manifest` | ok + failed members; failed carry status+reason, `files=null`; summary counts correct; order preserved |
| T-S1-10 | `parse_hidden_unavailable` | extracts `5` from stderr WARNING; `0` when absent |
| T-S1-11 | graceful degradation | `fetch_metadata` returns `None` on nonzero subprocess (mocked) → run records `metadata_failed` and continues |

*Skill 2 — `feature-requirement-extractor` (OpenAI engine `scripts/extract_requirements.py`):*
| id | unit | what the test pins down |
|---|---|---|
| T-S2-01 | config resolution | precedence **CLI > env > default** for model/temperature/max_tokens/timeout/retry |
| T-S2-02 | `fill_prompt` | every `{{placeholder}}` replaced from artifact; no residual `{{…}}` |
| T-S2-03 | `parse_response`/`render` | captured json_schema response → Markdown (REQ ids + trace) and mirrored JSON |
| T-S2-04 | `validate_req_id` | `^[A-Z0-9]{3,6}-[A-Z0-9-]{3,10}-\d{3}$`; video-local `NNN` from `001`; video_id **absent** from id |
| T-S2-05 | composite-key uniqueness | dedup on `(requirement_id, source_video_id)`; same req-id across two videos is **allowed** |
| T-S2-06 | env key loading | missing `OPENAI_API_KEY` → clear error, no crash, no secret leak |
| T-S2-07 | input resolution | artifact path vs collection folder → iterates manifest members `status==ok`; defensive `schema_version` read |

*Integration tier (`@pytest.mark.integration`, network, opt-in):*
| id | scenario |
|---|---|
| I-01 | Skill 1 real `fl1DSmwQKKY` → 60 `tr` auto segments, `type:auto`, `available_tracks=[tr]` |
| I-02 | Skill 1 real playlist → `hidden_unavailable_count:5`, ordered members, per-video lang/type |
| I-03 | Skill 2 OpenAI with real key → same JSON/MD shape (auto-skip if no key) |

*Acceptance-only (no unit test — Claude-native/prompt-following & trigger behavior):*
| id | criterion |
|---|---|
| A-01 | Skill 1 SKILL.md fires on "collect artifacts for this playlist", **not** `youtube-transcript` |
| A-02 | Skill 2 SKILL.md fires on "extract requirements from this artifact" |
| A-03 | Claude-native engine yields a filled doc with `<MODULE>-<FEATURE>-NNN` codes + traces matching real segment times (human review) |
| A-04 | Swapping `prompts/extraction_prompt.md` changes output **without** code edits |

## Acceptance criteria (capability-level, mapped to the brief)
- **Metadata collection:** every brief-required field (id,url,title,collection,channel,description,
  publish date,duration,chapters?,tags?) present in `video{}`; unknown-but-present yt-dlp fields preserved. *(T-S1-05)*
- **Structured transcript:** segment-based with per-segment timestamps + stable `index`; language and
  manual/auto type recorded; full track inventory kept; text lossless; multi-track distinguishable. *(T-S1-06,07; I-01)*
- **Graceful degradation:** an unavailable video in a batch is recorded with status+reason and the run
  continues; hidden-unavailable count captured. *(T-S1-09,10,11; I-02)*
- **Relational integrity:** every artifact carries its `collection{}` link; manifest preserves
  playlist→ordered-member relationships. *(T-S1-09; I-02)*
- **LLM integration (OpenAI):** all configurable params resolve by precedence; prompts/templates
  external & swappable; structured json_schema output parsed & stored; secrets only via `.env`. *(T-S2-01..03,06; A-04)*
- **Engine-agnostic output:** Claude-native and OpenAI engines emit the same shape. *(T-S2-03; A-03)*

## Trackable progress checklist (crash-resilient)
The implementer maintains a living file **`docs/claude_plans/recursive-booping-penguin-progress.md`**,
updated after **every** atomic transition (so a crash mid-build is resumable by re-reading it). One line
per catalog id:
```
[state] <id> — <unit>     state ∈ pending | spec | test-written | code-written | green | accepted
```
Rules: advance a row only on real evidence (tests actually run); **never** copy assertion text into this
file (keeps the blind barrier intact); on resume, continue from the first non-`green` row. In-session,
mirror rows as Task items (TaskCreate/TaskUpdate) for live visibility, but the markdown file is the
durable source of truth.

---

## Build & verification sequence

Two layers, in order; all via `uv run *` (already permitted). **Unit / blind-TDD layer first**, then
**integration + acceptance gates** (these need network / an OpenAI key).

**A. Per-component blind-TDD** — run the per-component loop for each, in order; tick the checklist per
id; advance a component only when its tests are green via the verifier:
- **A1** Skill 1 pure helpers — T-S1-01..04
- **A2** Skill 1 metadata + transcript + segments — T-S1-05..07
- **A3** Skill 1 markdown + manifest + degradation — T-S1-08..11
- **A4** Skill 2 config + prompt + id scheme — T-S2-01,02,04,05
- **A5** Skill 2 response render + input resolution + env — T-S2-03,06,07

**B. Integration + acceptance gates** (after the relevant unit work is green):
1. **Skill 1 single-video core** → `uv run extract_artifacts.py fl1DSmwQKKY --print` → 60 Turkish auto
   segments, `selected.type:"auto"`, full metadata, `available_tracks=[tr]` *(I-01)*.
2. **Skill 1 save + layout** → without `--print` → `data/_singles/fl1DSmwQKKY.json` + `.md`; segments carry `index`.
3. **Skill 1 playlist + graceful degradation** → real playlist → `data/<slug>-PLk…/` + `_manifest.json`
   (`hidden_unavailable_count:5`, ordered members), per-video failures recorded, run **continues** *(I-02)*.
4. **Skill 1 `watch?v=…&list=…`** → single by default; `--playlist` expands. SKILL.md trigger test *(A-01)*.
5. **Skill 2 Claude-native** → point at `fl1DSmwQKKY.json` → filled doc with `<MODULE>-<FEATURE>-NNN`
   codes, `source_video_id` set, traces matching real segment times *(A-02, A-03)*.
6. **Skill 2 OpenAI** → with `.env` key → same JSON/MD shape, configurable params honored *(I-03)*.
7. **Deprecate `youtube-transcript`** → separate user-approved step; update root `skills-lock.json`.

## Risks & mitigations

- **yt-dlp / YouTube fragility & rate-limiting** over ~24 sequential per-video calls → subprocess
  isolation + per-video try/except + `--sleep-requests`; record `tool_versions`.
- **Schema drift** Skill 1 → Skill 2 → `schema_version` + defensive reads in Skill 2.
- **UTF-8 / Turkish text & long descriptions** → write UTF-8 everywhere; keep JSON lossless, trim/fence
  only the Markdown *view*.
- **Module/feature code collisions across videos** → mitigated by the composite key
  (`requirement_id`+`source_video_id`); true global dedup deferred to the later consolidation stage.

## Critical files

- `.claude/skills/youtube-transcript/scripts/get_transcript.py` — source of copied
  `extract_video_id` (19–29) / `format_timestamp` (32–39) / fetch pattern (42–52) / PEP-723 + main (1–5, 55–72).
- `.claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py` — **new** (Skill 1).
- `.claude/skills/youtube-artifact-collector/SKILL.md` — **new**.
- `.claude/skills/feature-requirement-extractor/SKILL.md` — **new** (Skill 2 Claude-native engine).
- `.claude/skills/feature-requirement-extractor/scripts/extract_requirements.py` — **new** (OpenAI engine).
- `.claude/skills/feature-requirement-extractor/{prompts/*,templates/*,.env.example}` — **new**.
- `.claude/skills/youtube-artifact-collector/tests/{test_*.py,conftest.py,fixtures/inputs/*,fixtures/expected/*}` — **new** (test-writer agent; **denylisted** for implementer).
- `.claude/skills/feature-requirement-extractor/tests/{test_*.py,conftest.py,fixtures/inputs/*,fixtures/expected/*}` — **new** (test-writer agent; **denylisted** for implementer).
- `docs/claude_plans/recursive-booping-penguin-progress.md` — **new** living crash-resilient checklist (created at build start).
- `skills-lock.json` (repo root) — edited only at the deprecation step.
- `docs/02_PRODUCT_BRIEF.md` / `docs/03_ROADMAP.md` — authoritative requirements the schemas satisfy.
