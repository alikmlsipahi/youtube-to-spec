# Implementation Plan — Progress Checklist

> Living, crash-resilient build tracker for `docs/IMPLEMENTATION_PLAN.md`.
> One line per catalog id. `state ∈ pending | spec | test-written | code-written | green | accepted`.
> Rules: advance a row **only on real evidence** (tests actually run). **Never** copy assertion
> text into this file (keeps the blind-TDD barrier intact). On resume, continue from the first
> non-`green` row. In-session, mirror rows as Task items for live visibility; this file is the
> durable source of truth.

## Skill 1 — `youtube-artifact-collector` (unit / blind-TDD)

- [code-written] T-S1-01 — extract_video_id
- [code-written] T-S1-02 — format_timestamp
- [code-written] T-S1-03 — classify_input
- [code-written] T-S1-04 — slugify / collection_dir_name
- [pending] T-S1-05 — build_video_block
- [pending] T-S1-06 — select_transcript_track
- [pending] T-S1-07 — build_segments
- [pending] T-S1-08 — render_markdown
- [pending] T-S1-09 — build_manifest
- [pending] T-S1-10 — parse_hidden_unavailable
- [pending] T-S1-11 — graceful degradation (fetch_metadata)

## Skill 2 — `feature-requirement-extractor` (unit / blind-TDD)

- [pending] T-S2-01 — config resolution (CLI > env > default)
- [pending] T-S2-02 — fill_prompt
- [pending] T-S2-03 — parse_response / render
- [pending] T-S2-04 — validate_req_id
- [pending] T-S2-05 — composite-key uniqueness
- [pending] T-S2-06 — env key loading
- [pending] T-S2-07 — input resolution

## Integration tier (`@pytest.mark.integration`, opt-in)

- [pending] I-01 — Skill 1 real fl1DSmwQKKY → 60 tr auto segments
- [pending] I-02 — Skill 1 real playlist → hidden_unavailable_count:5, ordered members
- [pending] I-03 — Skill 2 OpenAI real key → same JSON/MD shape

## Acceptance-only (prompt-following & trigger behavior)

- [pending] A-01 — Skill 1 SKILL.md fires on "collect artifacts for this playlist"
- [pending] A-02 — Skill 2 SKILL.md fires on "extract requirements from this artifact"
- [pending] A-03 — Claude-native engine yields filled doc with codes + matching traces
- [pending] A-04 — Swapping extraction_prompt.md changes output without code edits
