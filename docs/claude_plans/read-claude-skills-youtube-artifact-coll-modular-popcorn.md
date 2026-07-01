# Plan — Add the orchestration layer to both Phase-1 skills

## Context

All 18 blind-TDD units are green (239 unit tests pass), but **both skill scripts
are pure-helper libraries** — neither has a `main()`, `argparse`, file I/O, or any
network/API call, and the declared deps (`youtube_transcript_api`, `openai`,
`python-dotenv`) are never imported. So the skills can be imported and unit-tested
but **cannot run end-to-end**, and the integration/acceptance gates
(`I-01..03`, `A-01..04`) that invoke `uv run …` are blocked. The blind-TDD catalog
has no row for this orchestration glue — it is genuine missing work, not unfinished
units.

This plan adds the orchestration **additively**: every existing function in both
scripts stays byte-for-byte unchanged; we only add new glue functions, imports,
`argparse`, and a `main()` that wires the existing helpers into a working flow.
Scope (confirmed with the user): **Full** — including real playlist enumeration and
the **full plan §CLI** flag set for both skills.

## Locked decisions

- **Full playlist support** for Skill 1 (new `enumerate_playlist` + `_manifest.json`).
- **Full §CLI** flag sets for both skills (matches the `SKILL.md` files already authored in Phase C).
- **yt-dlp stays subprocess-based** (consistent with the existing `fetch_metadata`
  and the plan's "subprocess for per-video isolation + stable JSON" mandate), so we
  add **only** the `youtube_transcript_api` import — *not* a `yt_dlp` python import.
  *(Deliberate deviation from the task's literal "import yt_dlp".)*
- **`--engine claude`** in the script prints an informative message (Claude-native
  is driven by `SKILL.md` in-chat, not this script) and exits; the script
  implements the **OpenAI** engine only. Default engine value stays `claude` per the plan.
- **No unit tests** are added for the glue (consistent with the `[done]` marking and
  "only add wiring"); like Phase C, it is verified by the integration/acceptance
  gates. A `if __name__ == "__main__"` guard keeps module import side-effect-free so
  the existing 239 unit tests stay green.
- **Consolidation/global dedupe is deferred** (plan says "later, not Phase 1"), so
  `dedupe_requirements` is left available but not wired into the per-video flow.

## Skill 1 — `.claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py`

Existing helpers reused unchanged: `extract_video_id`, `classify_input`,
`collection_dir_name`, `slugify`, `build_video_block`, `select_transcript_track`,
`build_segments`, `render_markdown`, `build_manifest`, `parse_hidden_unavailable`,
`fetch_metadata`, `format_timestamp`.

**Add imports:** `argparse`, `sys`, `time`, `from datetime import datetime, timezone`,
`from pathlib import Path`, `from youtube_transcript_api import YouTubeTranscriptApi`.

**Add new glue functions (additive only):**
- `enumerate_playlist(url) -> dict | None` — subprocess `yt-dlp --flat-playlist
  --dump-single-json <url>`; parse JSON for playlist id/title/uploader + ordered
  entries; derive `hidden_unavailable_count` via the existing
  `parse_hidden_unavailable(stderr)`. `None` on failure.
- `fetch_transcript(video_id, langs) -> dict` — `YouTubeTranscriptApi().list(video_id)`
  → `select_transcript_track(tracks, langs)` → `track.fetch()` → `build_segments(...)`;
  assemble the canonical `transcript{}` block (`available`, `selected`,
  `available_tracks`, `segment_count`, `segments`). Never raises — on no-transcript/error
  returns an `available: False` block (graceful degradation).
- `artifact_basename(video_id) -> str` — centralized naming (the helper CLAUDE.md references).
- `build_artifact(meta, transcript_block, collection_block) -> dict` — assemble the
  canonical per-video JSON: `schema_version "1.0"`, `kind "video_artifact"`,
  `extracted_at` (ISO-8601 UTC), `video = build_video_block(meta)`, `collection`,
  `transcript`, `extraction{metadata_ok, transcript_ok, warnings, tool_versions}`.
- `resolve_out_dir(root, collection, out_dir_override) -> Path` — `data/<slug>-<playlist_id>/`
  for playlists (via `collection_dir_name`), `data/_singles/` for standalone, or the override.
- `write_artifacts(artifact, out_dir, fmt) -> dict` — `mkdir(parents=True, exist_ok=True)`;
  write `<id>.json` and/or `<id>.md` (via `render_markdown`) per `--format`; return the
  `files{json,md}` dict for the manifest.
- `write_manifest(collection, members, out_dir) -> None` — `build_manifest(...)` then
  write `_manifest.json`.
- `main(argv=None) -> int` — `argparse` with the full §CLI:
  `urls…` (nargs="+"), `--playlist`, `--langs tr,en`, `--out-dir`, `--root data`,
  `--no-save`/`--print`, `--format json|md|both`, `--metadata-only`, `--skip-existing`,
  `--sleep-requests N`. Flow: `classify_input(args)` → build the work list
  (playlist → `enumerate_playlist`; single/multiple → `_singles`) → per video:
  `fetch_metadata` (None → record `metadata_failed`, continue) → `fetch_transcript`
  (unless `--metadata-only`) → `build_artifact` → `write_artifacts` (unless `--print`)
  → record member status; honor `--skip-existing` and `--sleep-requests`; for playlists
  `write_manifest` at the end. End with `if __name__ == "__main__": sys.exit(main())`.

## Skill 2 — `.claude/skills/feature-requirement-extractor/scripts/extract_requirements.py`

Existing helpers reused unchanged: `resolve_config`, `fill_prompt`, `validate_req_id`,
`parse_response`, `render_markdown`, `require_api_key`, `resolve_inputs`,
`load_artifact` (and `dedupe_requirements`, left unwired).

**Add imports:** `argparse`, `os`, `sys`, `from openai import OpenAI`,
`from dotenv import load_dotenv` (`Path`/`json`/`re` already imported).

**Add new glue functions (additive only):**
- `load_prompt_files() -> (system_prompt, extraction_template)` — read
  `prompts/system_prompt.md` and `prompts/extraction_prompt.md` relative to the script
  (`Path(__file__).resolve().parent.parent`). *(These were authored in Phase C2.)*
- `build_response_format(mode) -> dict | None` — when `response_format == "json_schema"`,
  the strict JSON schema matching what `parse_response`/`render_markdown` consume
  (`summary`; `modules[]→features[]→requirements[]` with `id/text/source_video_id/
  trace{timestamp,segment_index}`; `assumptions[]`; `open_questions[]`); else text.
- `call_openai(client, config, system_prompt, user_prompt)` — `client.chat.completions.create`
  with `model/temperature/max_tokens/messages/response_format/timeout` from `config`,
  wrapped in a `config["retries"]` retry loop. Returns the raw response.
- `process_artifact(path, config, system_prompt, template, client) -> (doc, md)` —
  `load_artifact` → `fill_prompt(template, artifact)` → `call_openai` →
  `parse_response` → `render_markdown(doc, artifact)`.
- `write_outputs(artifact_path, doc, md, out_dir, no_save)` — write
  `<video_id>.requirements.json` + `.requirements.md` alongside the source (or `--out-dir`),
  unless printing.
- `main(argv=None) -> int` — `load_dotenv()`; `argparse` with the full §CLI
  (`input`, `--engine claude|openai`, `--model`, `--temperature`, `--max-tokens`,
  `--response-format`, `--timeout`, `--retries`, `--concurrency`, `--out-dir`,
  `--no-save`/`--print`); `config = resolve_config(cli_dict, os.environ)`. If
  `--engine claude`: print the in-chat guidance and exit. Else: `require_api_key(os.environ)`
  → `OpenAI(...)` client → `resolve_inputs(input)` → process each artifact (a
  `ThreadPoolExecutor(max_workers=config["concurrency"])` over the input list) →
  `write_outputs`. End with `if __name__ == "__main__": sys.exit(main())`.

## Progress update

Append to `docs/IMPLEMENTATION_PLAN-progress.md` a short **Orchestration (non-blind glue;
no unit test)** section with two rows:
- `[done] SK1-ORCH — extract_artifacts.py main/CLI/IO + enumerate_playlist/fetch_transcript/write_* (verified by I-01,I-02)`
- `[done] SK2-ORCH — extract_requirements.py main/CLI + OpenAI engine/IO (verified by I-03)`

## Methodology caveats (surface to reviewer)

- This glue is **not unit-tested** by design; it is integration-gated. Skill 1's
  end-to-end path needs real network (yt-dlp + transcript API); Skill 2's OpenAI path
  needs a real `OPENAI_API_KEY` — neither can be fully verified locally/offline.
- Existing functions are untouched; all changes are additive, so the 239 existing unit
  tests must still pass (the `__main__` guard guarantees import stays side-effect-free).

## Verification

1. **No regression:** `uv run --with pytest pytest .claude/skills/youtube-artifact-collector/tests/`
   and `.../feature-requirement-extractor/tests/` → still 122 + 117 green.
2. **Skill 1 single (I-01):** `uv run .../extract_artifacts.py fl1DSmwQKKY --print` →
   per-video JSON with ~60 Turkish auto segments, `transcript.selected.type == "auto"`.
3. **Skill 1 save + playlist (I-02):** run on a real playlist URL with `--playlist` →
   `data/<slug>-<id>/` with `_manifest.json` (ordered members, `hidden_unavailable_count`),
   a failed/unavailable member recorded (not dropped), run completes.
4. **Skill 2 claude path:** `uv run .../extract_requirements.py <artifact.json> --engine claude`
   → prints the in-chat guidance and exits cleanly.
5. **Skill 2 OpenAI (I-03, needs key):** with `.env` set,
   `uv run .../extract_requirements.py <artifact.json> --engine openai --print` → a filled
   Module→Feature→Requirement doc whose `id`s match `<MODULE>-<FEATURE>-NNN` and whose
   traces reference real segment times; mirrored `.requirements.json` written.
