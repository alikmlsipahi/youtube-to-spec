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
- [accepted] T-S1-12 — request_delay (jittered inter-request sleep) — verified: test_request_delay.py 10/10, full skill-1 suite 132/132, no regressions; end-to-end live-run verification below (SK1-ORCH v2.2)
- [accepted] T-S1-13 — artifact_basename / common_title_prefix — **[v2.1] naming policy, retrofitted coverage.** 38 cases green. Spec authored from documented policy + signatures/docstrings only (no bodies); tests authored from spec only (no implementation) — so green means the code matches its documented contract, not that the tests match the code. Zero divergences. Guard proven: dropping the pad floor to one digit fails 4 cases.
- [accepted] T-S1-14 — scan_existing — same retrofit route; 24 cases green, zero divergences. Guard proven: removing the `_manifest.json` / `*.requirements.json` exclusion fails 2 cases. Full skill-1 suite 132 → 196.
- [accepted] T-S1-15 — enumerate_playlist — last untested piece of the playlist path; 16 cases green, zero divergences (suite 196 → 212). Same retrofit route (spec from docs + signature/docstring, tests from spec only). Pins order preservation, no-dedup, null-title members kept in place, and warning-coexists-with-complete-listing. Guard proven: filtering null-title entries fails 3 cases. **Speccing it also caught a false claim in 3 places** (docstring + `PLAN_v2:76-77` + `A3-T-S1-10` provenance) that yt-dlp "omits" hidden members — measured false; all corrected.

## Skill 2 — `feature-requirement-extractor` (unit / blind-TDD)

- [green] T-S2-01 — config resolution (CLI > env > default)
- [green] T-S2-02 — fill_prompt
- [green] T-S2-03 — parse_response / render
- [green] T-S2-04 — validate_req_id
- [green] T-S2-05 — composite-key uniqueness
- [green] T-S2-06 — env key loading
- [green] T-S2-07 — input resolution
- [accepted] T-S2-08 — write_outputs — **[v2.1] naming policy, retrofitted coverage.** 24 cases green, zero divergences (tier 125 → 149). Spec from documented policy + signature/docstring only; tests from spec only. Enforces SKILL.md's "Never rebuild the name from the video id" — previously stated in three prose sources and guarded by nothing. Guard proven: restoring the pre-v2.1 `video.id` naming fails 19 of 24.
- [accepted] T-S2-09 — normalize_trace_indexes — **record gap, not a coverage gap.** Tests
  (`test_trace_index_validation.py`) existed from the start; the catalog id and spec did not, so the
  unit was invisible to the record. Catalogued + spec'd 2026-07-15. The spec is **descriptive**
  (transcribed from the docstring after the tests existed), not a blind contract — flagged as such in
  its own header, since presenting a retrofit as blind-TDD would falsify the record a second time.

## Orchestration (non-blind glue; no unit test — integration-gated)

> Additive `main()`/CLI/IO + new glue functions wiring the green helpers into an
> end-to-end flow. Existing functions untouched; verified via the integration gates
> below, not unit tests.
>
> **[2026-07-15]** This "glue needs no unit test" framing cost us: `artifact_basename`,
> `common_title_prefix` and `scan_existing` landed here under it, but the first two are
> *pure functions* carrying the entire [v2.1] naming policy — so when v2.1 changed that
> policy, nothing in any tier objected and I-01 sat red unnoticed. They are now real units
> (T-S1-13/14). The rule to draw: **glue is the I/O and wiring, not every function that
> arrives with it** — a pure function belongs in the unit tier no matter which phase adds it.
>
> `enumerate_playlist` was the follow-on case: genuinely I/O glue, so the framing was right
> about *where* it lives — but it was also the **only** playlist logic no tier ran, and the
> integration gate meant to cover it (I-02) was prose, not code. It is now T-S1-15 (mocked
> subprocess) *and* covered by an automated I-02. The second rule: **"integration-gated" is
> only an excuse if the gate is executable.** Both remaining Skill 2 entries below inherit
> this problem — see `write_outputs`, which SK2-ORCH claims I-03 verifies, though I-03 stops
> at the function immediately before it.

- [done] SK1-ORCH — extract_artifacts.py main/CLI/IO + enumerate_playlist/fetch_transcript/build_artifact/write_* (verified by I-01 ✓, I-02 ✓)
  - [done] **[v2.1]** title-derived artifact filenames — `artifact_basename` re-signed + `common_title_prefix` / `scan_existing` added; `--skip-existing` now resolves via the on-disk id index. `slugify`/`collection_dir_name` (T-S1-04) untouched, so no blind-TDD chain was re-opened. Re-verified: real playlist → `01-tek-tek-ogrenci-yukleme.json` … `19-…`, manifest `summary` unchanged (24/19 ok/5 failed), `--skip-existing` second pass skipped 19 in 0.09s (no network); 247 unit tests green.
  - [done] **[v2.2]** jittered `--sleep-requests` moved to fire before every network-hitting iteration (except the first), gated on a `hit_network` flag; old unconditional end-of-loop sleep removed. Built on new pure helper `request_delay` (T-S1-12, blind-TDD, green: 10/10 own tests, 132/132 full skill-1 suite). Re-verified live: two invalid ids w/ `--sleep-requests 3` → 5.955s then 5.610s on a repeat run (metadata_failed pays the delay now; jitter varies run to run, not fixed); real single-video collect unaffected (3.276s, one network call, no sleep); `--skip-existing` w/ `--sleep-requests 30` still 0.101s (no network → free); default path (no `--sleep-requests`) unchanged at 3.242s.
- [done] SK2-ORCH — extract_requirements.py main/CLI + OpenAI engine (load_prompt_files/build_response_format/call_openai/process_artifact/write_outputs) (verified by I-03 ✓; claude-path ✓)
  - **[correction 2026-07-15]** "verified by I-03" **did not cover `write_outputs`**. I-03 stops at `process_artifact` — the function immediately before it — and writes nothing to disk, so every name in that parenthetical was exercised except this one (and `build_response_format`, reached only when `call_openai` requests json_schema). The row read as full coverage while the function that actually names the output files had none; v2.1 then changed its arity and its naming rule unguarded. Now covered by T-S2-08.
  - [done] **[v2.1]** `write_outputs` names outputs after the source artifact's basename instead of `video.id`, keeping Skill 1 the only owner of naming policy; `SKILL.md` step 6 re-authored to match so both engines agree. Re-verified: `01-tek-tek-ogrenci-yukleme.requirements.{json,md}`; `resolve_inputs` still resolves all 19 members via the manifest.

## Authoring (Phase C — non-blind; prose/assets; test-denylist still applies)

> Lifecycle: pending → drafted → accepted. Accepted at the mapped acceptance gate.

- [accepted] SK1-DOC — youtube-artifact-collector/SKILL.md (Phase C1; gate A-01)
- [accepted] SK2-ASSETS — Skill 2 prompts/{system_prompt,extraction_prompt}.md, templates/requirement_doc.md, .env.example (Phase C2; gates A-03, A-04)
- [accepted] SK2-DOC — feature-requirement-extractor/SKILL.md (Phase C3; gates A-02, A-03)

## Integration tier (`@pytest.mark.integration`, opt-in)

- [green] I-01 — Skill 1 real fl1DSmwQKKY → metadata + title-derived artifact on disk. Split in two (2026-07-15): `writes_titled_artifact` **passes** (verified: `_singles/what-is-claude-code.json` + `.md`, `video.id` matches, basename is the title slug not the id); `fetches_transcript` **skips** from this network — YouTube `IpBlocked` on transcript fetch, so `available_tracks=[en auto]` is read but `transcript.available:false`. Skip ≠ pass: it runs for real on an unblocked network, and zero caption tracks would still fail.
  - **[correction 2026-07-15]** This row previously claimed `60 tr auto segments … available_tracks=[tr]`. That evidence does not describe `fl1DSmwQKKY` ("What is Claude Code?"), which exposes exactly one `en` auto track — measured directly. The claim predates `2bceaa9` swapping in this public video, and the gate was never re-run against it; the stale evidence rode along on the new id. Replaced with what is actually verifiable here.
- [green] I-02 — Skill 1 real playlist → **now an automated test** (`tests/integration/test_skill1_playlist.py`, 2 cases, ~29s). Live run 2026-07-15 against `PLk-DU0q6QMPP7RfYiyhiJY7qQOXoaFKHL`: summary `total:24, ok:19, failed:5`, members ordered 1..24, hidden_unavailable_count 5 — matching the original manual evidence exactly, a year on. Asserts structure + internal consistency (ordering, summary/member agreement, failed members listed w/ reason and `files:null`, ok members' manifest names present on disk, `<position>-<slug>` naming), **not** the upstream counts — pinning 24/5/19 would break when the channel adds a video, which is how I-01's assertion went stale. Guard proven: breaking the stderr anchor regex fails the count assertion; reverting `artifact_basename` to id-naming fails the naming assertion.
  - **[why this mattered]** Until 2026-07-15 this row was green on **manual** evidence — the gate was a prose prompt in `IMPLEMENTATION_GUIDE_v2.md:631-644`, not code. It was the one gate positioned to catch v2.1's `<position>-<slug>` rename, and it caught nothing because it did not exist. It also missed a real yt-dlp wording drift (see T-S1-10). A gate that only a human can run is not a gate.
- [green] I-03 — Skill 2 OpenAI real key → same JSON/MD shape parsed (json_schema; valid ids, composite-unique; model trace accuracy is model-side, not script)

## Acceptance-only (prompt-following & trigger behavior)

- [accepted] A-01 — Skill 1 SKILL.md fires on "collect artifacts for this playlist" (trigger + flag audit vs argparse: exact match)
- [accepted] A-02 — Skill 2 SKILL.md fires on "extract requirements from this artifact" (trigger + flag audit vs argparse: exact match)
- [accepted] A-03 — Claude-native engine yields filled doc: 18 reqs, valid ids, all traces resolve to real segments
- [accepted] A-04 — Swapping extraction_prompt.md changes model prompt with zero code edit (git status of script empty)
