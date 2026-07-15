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
- [accepted] T-S1-11 — graceful degradation (fetch_metadata) — **[v2.3] re-signed** to `(meta, failure)`; 12 cases green (was 4). The old contract — *"non-zero exit → `None`"* — was not worked around, it was the thing fixed: one sentinel made "video is private" and "YouTube blocked us" the same value at the only boundary where the difference was still knowable (stderr, which the code captured and discarded). Retry is not implementable on top of it. Precedent for re-signing rather than bolting a sibling alongside: `artifact_basename` in v2.1. Pins the pair that justifies it — the same return code classified oppositely on stderr alone.
- [accepted] T-S1-12 — request_delay (jittered inter-request sleep) — verified: test_request_delay.py 10/10, full skill-1 suite 132/132, no regressions; end-to-end live-run verification below (SK1-ORCH v2.2)
- [accepted] T-S1-13 — artifact_basename / common_title_prefix — **[v2.1] naming policy, retrofitted coverage.** 38 cases green. Spec authored from documented policy + signatures/docstrings only (no bodies); tests authored from spec only (no implementation) — so green means the code matches its documented contract, not that the tests match the code. Zero divergences. Guard proven: dropping the pad floor to one digit fails 4 cases.
- [accepted] T-S1-14 — scan_existing — same retrofit route; 24 cases green, zero divergences. Guard proven: removing the `_manifest.json` / `*.requirements.json` exclusion fails 2 cases. Full skill-1 suite 132 → 196.
- [accepted] T-S1-15 — enumerate_playlist — last untested piece of the playlist path; 16 cases green, zero divergences (suite 196 → 212). Same retrofit route (spec from docs + signature/docstring, tests from spec only). Pins order preservation, no-dedup, null-title members kept in place, and warning-coexists-with-complete-listing. Guard proven: filtering null-title entries fails 3 cases. **Speccing it also caught a false claim in 3 places** (docstring + `PLAN_v2:76-77` + `A3-T-S1-10` provenance) that yt-dlp "omits" hidden members — measured false; all corrected.
  - [accepted] **[v2.3]** re-signed to `(playlist, failure)` and brought into the retry budget; 22 cases green (was 16 — order preservation, null-title members and `hidden_unavailable_count` all preserved, adapted to the tuple). This **closes the open `[NEEDS CLARIFICATION]`** the unit carried on whether the rate-limit machinery reaches the enumeration call: it does, and it is the highest-stakes call to get right — one 429 here kills a playlist collect before it fetches anything, where the same 429 per-video costs one video. Not preceded by a pace: nothing precedes it.

- [accepted] T-S1-16 — classify_failure — **[v2.3] the precondition for retry.** 52 cases green. String-based on `(name, text)`, not exception classes: the tier stubs the network deps in `sys.modules`, so an `except` on a stubbed attribute would take the whole tier down. **The blind implementer caught what the spec author missed** — YouTube ships the bot check with a typographic apostrophe (U+2019) while the spec's signal was ASCII, so the highest-consequence transient signal would have silently failed to match its own real text and classified `"permanent"`. Folded into the spec as contract and pinned after the fact. Guard proven: dropping the fold fails 5 of 52.
- [accepted] T-S1-17 — backoff_delay — 25 cases green. Delegates jitter to `request_delay` (T-S1-12) rather than forking the policy. Exponent verified by pinning `rng` to `0.0`, so no test waits. Full jitter rejected on the record: a near-zero wait after a 429 is the behavior that escalates a throttle.
- [accepted] T-S1-18 — escalate_pacing — 25 cases green. **The test author found a real contract bug before any code existed:** the spec let a negative ceiling produce a negative pacing, which — fed back in as the next `current` — would trip the opt-out branch and silently disable pacing for the rest of the run, i.e. cause the ban it exists to prevent. Now floored at `0.0`.
- [accepted] T-S1-19 — atomic_write_text — 32 cases green. Local-I/O unit, following `scan_existing`'s precedent that I/O helpers which never touch the network belong in the unit tier. Debris assertions are directory-listing equality, so they hold for any temp-naming choice — the spec leaves the name an implementer detail.

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
  - [done] **[v2.3]** retry + capped exponential backoff, and the data-loss fix it uncovered. All three network calls (`fetch_metadata`, `fetch_transcript`, `enumerate_playlist`) wrapped in `_call_with_retries`, which retries **only** a `"transient"` verdict; `time.sleep` lives in the glue so the delay units stay pure. Adaptive pacing held in a `main()` local, escalated on each `rate_limited`. New `rate_limited` member status. `--sleep-requests` default `0.0` → `2.0`; new `--retries/--retry-base/--retry-cap/--max-pacing/--timeout` (the subprocess calls were **unbounded** — a hung yt-dlp hung the run with no escape). All three writes now go through `atomic_write_text`, `.md` before `.json` so the `.json` is the commit point.
    - **The invariant this turns on:** *a JSON on disk means a complete artifact.* A transiently-blocked transcript is not written at all. This is what makes `--skip-existing` correct **without touching `scan_existing`** — the half artifact that would defeat it never exists.
    - **What the live tier caught that 374 green tests could not**, because nothing in the unit tier calls `main()`: a blocked single-video collect exited **0 with no files and no stderr**. The member record was built and dropped, since `write_manifest` only runs for a collection. Arguably worse than the original bug — before you got wrong data, now you got silence, and CI swallows silence. Fixed: rate-limited videos always report on stderr; a run that wrote nothing while rate-limited exits 1. Partial failure deliberately unchanged (19 ok / 5 failed still exits 0 — verified live).
    - Re-verified live: two invalid ids → 4.9s total, **no backoff paid** (permanent → no retry; retrying would have cost ~2.5 min/video); real playlist → `total:24, ok:19, failed:5` matching I-02's year-old evidence exactly; `--metadata-only` unaffected; blocked single video → exit 1 + one-line stderr + zero files.
    - **The third rule this earns:** *green units do not mean a working program.* T-S1-13/14 taught that a pure function belongs in the unit tier; T-S1-15 taught that an integration gate must be executable. This one: the tier can be 374/374 while `main()` is silently broken, and only driving the real thing finds it.
  - [done] **[v2.4]** two known defects from `to-do.md` closed (items 1 and 3), both about a run saying what happened. `enumerate_playlist` gained an `isinstance(data, dict)` guard — rc-0 stdout that parses but isn't an object used to escape as `AttributeError` and kill the run, because the parse guard answers *"did it parse"* when the question is *"is it usable"* (spec `A6-T-S1-15` `[v2.4]`; 8 new cases, tier 380 → 388). `_warn_rate_limited` generalized to `_warn_failed`, and the exit rule from `if rate_limited and not collected` to `if failed and not collected`, so a permanently-failed single video now exits 1 with a reason instead of exiting 0 in silence. Partial success deliberately untouched and re-verified live: playlist still `exit 0`, 19 artifacts, and its 5 losses now print instead of being swallowed.
    - **The gate is the interesting part.** This defect lives in `main()`, which no unit test reaches, so it got an executable one (`test_skill1_single_permanent_failure_is_not_silent`) — and unlike the rest of I-01 it is **deterministic**: a bogus id fails on any network, needing no fixture and no caption luck. It skips rather than passes if the run is rate-limited instead, since that outcome satisfies every assertion without the permanent path ever executing.
    - **The gate then had to be hardened against the thing it was written to catch.** A crash also exits non-zero and also prints, so a crashing program passed it. Not hypothetical: a `NameError` in the new exit rule produced a textbook-looking `exit 1` + stderr **while all 388 unit tests were green**. A traceback check now guards both that gate and `_was_rate_limited` — the latter matters more, because it is the "that was environmental, skip" escape route, and an escape route a crash can trigger is the worst way to lose a regression.
    - **Sharpens the third rule rather than adding a fourth.** "Green units do not mean a working program" was recorded in v2.3; v2.4 adds that *a gate can be green on a program that crashed*. Both point at the same hole — `main()` has no coverage — and neither the warning nor the traceback check closes it. Tracked below the line in `to-do.md`.
- [done] SK2-ORCH — extract_requirements.py main/CLI + OpenAI engine (load_prompt_files/build_response_format/call_openai/process_artifact/write_outputs) (verified by I-03 ✓; claude-path ✓)
  - **[correction 2026-07-15]** "verified by I-03" **did not cover `write_outputs`**. I-03 stops at `process_artifact` — the function immediately before it — and writes nothing to disk, so every name in that parenthetical was exercised except this one (and `build_response_format`, reached only when `call_openai` requests json_schema). The row read as full coverage while the function that actually names the output files had none; v2.1 then changed its arity and its naming rule unguarded. Now covered by T-S2-08.
  - [done] **[v2.1]** `write_outputs` names outputs after the source artifact's basename instead of `video.id`, keeping Skill 1 the only owner of naming policy; `SKILL.md` step 6 re-authored to match so both engines agree. Re-verified: `01-tek-tek-ogrenci-yukleme.requirements.{json,md}`; `resolve_inputs` still resolves all 19 members via the manifest.

## Authoring (Phase C — non-blind; prose/assets; test-denylist still applies)

> Lifecycle: pending → drafted → accepted. Accepted at the mapped acceptance gate.

- [accepted] SK1-DOC — youtube-artifact-collector/SKILL.md (Phase C1; gate A-01)
- [accepted] SK2-ASSETS — Skill 2 prompts/{system_prompt,extraction_prompt}.md, templates/requirement_doc.md, .env.example (Phase C2; gates A-03, A-04)
- [accepted] SK2-DOC — feature-requirement-extractor/SKILL.md (Phase C3; gates A-02, A-03)

## Integration tier (`@pytest.mark.integration`, opt-in)

- [green] I-01 — **[v2.3] re-authored: split in three, and strengthened rather than adapted.** 2 passed, 1 skipped. The naming half now runs `--metadata-only` — it asserts a title-slug policy that has nothing to do with captions and rode on a full collect only by habit, which made it fail from a transcript-blocked network for a reason it does not test; it is now deterministic anywhere. The transcript half still skips where YouTube IP-blocks the fetch, but detects that from the run's exit + stderr rather than by reading an artifact, since under the v2.3 invariant no artifact is written. **A third case gates the invariant itself from *either* network** — blocked, it pins that nothing was written; unblocked, it pins that what was written is whole. An artifact carrying caption tracks on offer but no transcript is the exact shape of the original bug and can now never land unnoticed. Note what the old row below records: this gate was **green while documenting the bug** — it read `available_tracks=[en auto]` with `transcript.available:false` and passed anyway, because "an artifact exists" was all it asked.
  - **[superseded 2026-07-15]** Original two-way split: Skill 1 real fl1DSmwQKKY → metadata + title-derived artifact on disk. `writes_titled_artifact` **passes** (verified: `_singles/what-is-claude-code.json` + `.md`, `video.id` matches, basename is the title slug not the id); `fetches_transcript` **skips** from this network — YouTube `IpBlocked` on transcript fetch, so `available_tracks=[en auto]` is read but `transcript.available:false`. Skip ≠ pass: it runs for real on an unblocked network, and zero caption tracks would still fail.
  - **[correction 2026-07-15]** This row previously claimed `60 tr auto segments … available_tracks=[tr]`. That evidence does not describe `fl1DSmwQKKY` ("What is Claude Code?"), which exposes exactly one `en` auto track — measured directly. The claim predates `2bceaa9` swapping in this public video, and the gate was never re-run against it; the stale evidence rode along on the new id. Replaced with what is actually verifiable here.
- [green] I-02 — Skill 1 real playlist → **now an automated test** (`tests/integration/test_skill1_playlist.py`, 2 cases, ~29s). Live run 2026-07-15 against `PLk-DU0q6QMPP7RfYiyhiJY7qQOXoaFKHL`: summary `total:24, ok:19, failed:5`, members ordered 1..24, hidden_unavailable_count 5 — matching the original manual evidence exactly, a year on. Asserts structure + internal consistency (ordering, summary/member agreement, failed members listed w/ reason and `files:null`, ok members' manifest names present on disk, `<position>-<slug>` naming), **not** the upstream counts — pinning 24/5/19 would break when the channel adds a video, which is how I-01's assertion went stale. Guard proven: breaking the stderr anchor regex fails the count assertion; reverting `artifact_basename` to id-naming fails the naming assertion.
  - **[why this mattered]** Until 2026-07-15 this row was green on **manual** evidence — the gate was a prose prompt in `IMPLEMENTATION_GUIDE_v2.md:631-644`, not code. It was the one gate positioned to catch v2.1's `<position>-<slug>` rename, and it caught nothing because it did not exist. It also missed a real yt-dlp wording drift (see T-S1-10). A gate that only a human can run is not a gate.
- [green] I-03 — Skill 2 OpenAI real key → same JSON/MD shape parsed (json_schema; valid ids, composite-unique; model trace accuracy is model-side, not script)

## Acceptance-only (prompt-following & trigger behavior)

- [accepted] A-01 — Skill 1 SKILL.md fires on "collect artifacts for this playlist" (trigger + flag audit vs argparse: exact match)
- [accepted] A-02 — Skill 2 SKILL.md fires on "extract requirements from this artifact" (trigger + flag audit vs argparse: exact match)
- [accepted] A-03 — Claude-native engine yields filled doc: 18 reqs, valid ids, all traces resolve to real segments
- [accepted] A-04 — Swapping extraction_prompt.md changes model prompt with zero code edit (git status of script empty)
