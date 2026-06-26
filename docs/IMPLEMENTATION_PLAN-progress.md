# Implementation Plan — Progress Checklist

> Living, crash-resilient build tracker for `docs/IMPLEMENTATION_PLAN_v2.md` (authoritative; v1 superseded).
> One line per catalog id. `state ∈ pending | spec | test-written | code-written | green | accepted`.
> Authoring rows (Phase C) use the simpler lifecycle `pending | drafted | accepted` (no unit tests).
> Rules: advance a row **only on real evidence** (tests actually run). **Never** copy assertion
> text into this file (keeps the blind-TDD barrier intact). On resume, continue from the first
> non-`green` row. In-session, mirror rows as Task items for live visibility; this file is the
> durable source of truth.

## Skill 1 — `youtube-artifact-collector` (unit / blind-TDD)

- [green] T-S1-01 — extract_video_id
- [green] T-S1-02 — format_timestamp
- [green] T-S1-03 — classify_input
- [green] T-S1-04 — slugify / collection_dir_name
- [green] T-S1-05 — build_video_block
- [green] T-S1-06 — select_transcript_track
- [green] T-S1-07 — build_segments
- [green] T-S1-08 — render_markdown
- [green] T-S1-09 — build_manifest
- [green] T-S1-10 — parse_hidden_unavailable
- [green] T-S1-11 — graceful degradation (fetch_metadata)

## Skill 2 — `feature-requirement-extractor` (unit / blind-TDD)

- [green] T-S2-01 — config resolution (CLI > env > default)
- [green] T-S2-02 — fill_prompt
- [green] T-S2-03 — parse_response / render
- [green] T-S2-04 — validate_req_id
- [green] T-S2-05 — composite-key uniqueness
- [green] T-S2-06 — env key loading
- [green] T-S2-07 — input resolution

## Orchestration (non-blind glue; no unit test — integration-gated)

> Additive `main()`/CLI/IO + new glue functions wiring the green helpers into an
> end-to-end flow. Existing functions untouched; verified via the integration gates
> below, not unit tests.

- [done] SK1-ORCH — extract_artifacts.py main/CLI/IO + enumerate_playlist/fetch_transcript/build_artifact/write_* (verified by I-01 ✓; I-02 pending)
- [done] SK2-ORCH — extract_requirements.py main/CLI + OpenAI engine (load_prompt_files/build_response_format/call_openai/process_artifact/write_outputs) (verified by I-03 pending; claude-path exit ✓)

## Authoring (Phase C — non-blind; prose/assets; test-denylist still applies)

> Lifecycle: pending → drafted → accepted. Accepted at the mapped acceptance gate.

- [drafted] SK1-DOC — youtube-artifact-collector/SKILL.md (Phase C1; gate A-01)
- [drafted] SK2-ASSETS — Skill 2 prompts/{system_prompt,extraction_prompt}.md, templates/requirement_doc.md, .env.example (Phase C2; gates A-03, A-04)
- [drafted] SK2-DOC — feature-requirement-extractor/SKILL.md (Phase C3; gates A-02, A-03)

## Integration tier (`@pytest.mark.integration`, opt-in)

- [green] I-01 — Skill 1 real fl1DSmwQKKY → 60 tr auto segments (verified: segment_count 60, selected type=auto, available_tracks=[tr])
- [pending] I-02 — Skill 1 real playlist → hidden_unavailable_count:5, ordered members
- [pending] I-03 — Skill 2 OpenAI real key → same JSON/MD shape

## Acceptance-only (prompt-following & trigger behavior)

- [pending] A-01 — Skill 1 SKILL.md fires on "collect artifacts for this playlist"
- [pending] A-02 — Skill 2 SKILL.md fires on "extract requirements from this artifact"
- [pending] A-03 — Claude-native engine yields filled doc with codes + matching traces
- [pending] A-04 — Swapping extraction_prompt.md changes output without code edits
