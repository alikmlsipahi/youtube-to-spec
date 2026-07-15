# Spec — `enumerate_playlist` (T-S1-15)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #2 `enumerate_playlist(url)` — "`yt-dlp --flat-playlist --dump-single-json`; capture
> playlist id/title/uploader, ordered member ids, and `hidden_unavailable_count` parsed from stderr
> WARNING"; §Functions #3 for the subprocess-isolation convention this function follows; §`_manifest.json`
> shape; §Grounding "two-stage yt-dlp extraction"; §Risks "subprocess isolation + per-video try/except"),
> `skills/youtube-artifact-collector/SKILL.md` (§Graceful degradation, §Tooling),
> `docs/specs/A3-T-S1-10-parse_hidden_unavailable.spec.md` (the reuse contract),
> `docs/specs/A3-T-S1-11-graceful_degradation.spec.md` (the governing "subprocess fails → `None`, never
> raise" precedent), `docs/IMPLEMENTATION_PLAN-progress.md` (SK1-ORCH, I-02 gate), and the function's own
> signature + docstring. Retrofitted coverage: the code predates this spec, which is authored from
> documented policy + signature/docstring only — no function body was read.
> **No test code, no golden output tables here.**

## One-line purpose

Enumerate a playlist's identity and its **ordered** members by shelling out to yt-dlp's flat listing,
returning a dict carrying the playlist's `id`/`title`/`uploader`, the members in playlist order, and the
count of unavailable members yt-dlp hid from the listing — or **`None`** on any failure, so an
unreachable playlist degrades gracefully instead of aborting the run.

## Signature

```python
def enumerate_playlist(url: str) -> dict | None
```

This is the **first** of the two yt-dlp stages (plan §Grounding): `--flat-playlist` yields playlist
metadata plus thin per-entry fields, while the rich per-video fields (description, tags, chapters,
upload_date) require the separate per-video `--dump-json` that `fetch_metadata` (T-S1-11) performs.

Performs a subprocess call (`subprocess.run`) to yt-dlp; it does **not** use the Python yt-dlp API —
subprocess is chosen for stable JSON output and per-run isolation, consistent with `fetch_metadata`. It
is **not** pure, but it is deterministic given a mocked subprocess, and **the unit tier mocks the
subprocess so no network is touched**. It reuses `parse_hidden_unavailable` (T-S1-10) unchanged.

## Inputs

- `url: str` — a playlist URL, already classified as a playlist by `classify_input` (T-S1-03). A
  `watch?v=…&list=…` URL only reaches this function when the run was invoked with `--playlist`; without
  that flag it is collected as a single video and this function is never called.

The function invokes, conceptually, `yt-dlp --flat-playlist --dump-single-json <url>` via
`subprocess.run`, capturing **stdout** (the single playlist JSON document), capturing **stderr** (which
carries the hidden-unavailable WARNING), and inspecting the process return code.

## Expected behavior

- **Success path:** when the subprocess exits with **return code `0`**, parse its captured **stdout** as
  a single JSON document and return a dict of the shape:
  - `id` — the playlist's id,
  - `title` — the playlist's title,
  - `uploader` — the playlist's uploader/channel,
  - `entries` — the members as `{id, title}` records, **in playlist order**,
  - `hidden_unavailable_count` — an `int`, obtained by passing the captured **stderr** to
    `parse_hidden_unavailable` (T-S1-10), which returns `0` when no such warning appears.
- **Member order is the contract.** The order yt-dlp emits entries in *is* the playlist order, and it must
  be preserved as-is. Downstream, a member's index in `entries` becomes its 1-based `position` — the
  manifest's `members[].position`, the artifact's `collection{position}`, and the numeric prefix
  `artifact_basename` (T-S1-13) puts on the filename. Reordering, sorting, or deduplicating entries here
  would silently corrupt all three.
- **Unavailable members are enumerated, not omitted.** A private/deleted/otherwise unavailable member
  **still appears** in the flat listing, carrying a **null title**. yt-dlp *additionally* reports how many
  such members exist via the stderr WARNING. Both facts are recorded: the member stays in `entries` (with
  its null title intact), **and** the count lands in `hidden_unavailable_count`. Such members enumerate
  fine and fail later, at the per-video metadata fetch — which is precisely what makes them
  `metadata_failed` manifest members rather than missing ones. This function must **not** filter them out;
  dropping them would shift every subsequent member's position and erase them from the manifest.
- **Null titles are preserved, not repaired.** An entry's `title` is passed through exactly as yt-dlp
  reported it, including `None`. The video-id fallback for an untitled member is `artifact_basename`'s job
  (T-S1-13), not this function's; a coerced empty string here would defeat that fallback's own contract.
- **Failure path (graceful):** when the subprocess exits with a **non-zero** return code, return **`None`**
  — do **not** raise, and do **not** call `sys.exit`. This follows the convention T-S1-11 establishes for
  `fetch_metadata`: the script-wide `except → stderr → sys.exit(1)` convention applies to fatal top-level
  errors, not to a yt-dlp call that came back unhappy. Failure is always signalled by the `None` return.

## Edge cases

- **Return code 0 with a valid playlist JSON on stdout:** returns the dict described above.
- **Non-zero exit** (playlist private, deleted, region-blocked, URL malformed, network down): returns
  `None`.
- **Return code 0 but unparseable or empty stdout:** treated as a failure → returns `None`. A successful
  exit with garbage output must not propagate a parse exception to the caller. [ASSUMPTION] — this
  mirrors T-S1-11's identical defensive rule.
- **yt-dlp executable missing (`FileNotFoundError`) or other subprocess error:** treated as a failure →
  returns `None`, not an exception. [ASSUMPTION] — again mirroring T-S1-11.
- **stderr carries no hidden-unavailable WARNING:** `hidden_unavailable_count` is `0` — that is
  `parse_hidden_unavailable`'s contract for the absent/empty case, and this function does not second-guess
  it.
- **stderr carries the WARNING while the listing is complete:** both are recorded — the entries are all
  returned *and* the count is non-zero. The count is **not** a count of missing entries and must not be
  used to infer that any are missing.
- **Members with a null title:** kept in `entries`, in position, with `title` still `None`.
- **The function must never raise** on the failure paths above.

## Acceptance scenarios (Given / When / Then)

All scenarios are described at the **mocked-subprocess boundary**: `subprocess.run` is mocked to return a
process result with a chosen return code, stdout, and stderr, so no network is touched.

- **Given** `subprocess.run` is mocked to return a **non-zero** return code, **when** `enumerate_playlist`
  runs on any URL, **then** it returns `None` and does not raise.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout being a valid flat-playlist
  JSON document, **when** `enumerate_playlist` runs, **then** it returns a dict carrying the playlist's
  `id`, `title`, and `uploader` drawn from that document.
- **Given** the same mocked success, **when** `enumerate_playlist` runs, **then** `entries` contains one
  `{id, title}` record per member of the mocked document, in the **same order** the document listed them.
- **Given** a mocked stdout whose entries include members with a **null title**, **when**
  `enumerate_playlist` runs, **then** those members are **present** in `entries` — not filtered out — at
  their original positions, and their `title` is still `None`.
- **Given** a mocked stderr containing yt-dlp's hidden-unavailable WARNING alongside a **complete** entry
  listing on stdout, **when** `enumerate_playlist` runs, **then** `hidden_unavailable_count` reflects the
  count the warning reported **and** every entry from stdout is still returned — the count does not cause
  any member to be dropped.
- **Given** a mocked stderr with **no** hidden-unavailable WARNING, **when** `enumerate_playlist` runs,
  **then** `hidden_unavailable_count` is `0`.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout that is **not** parseable
  JSON, **when** `enumerate_playlist` runs, **then** it returns `None` rather than raising.

## Assumptions

- [ASSUMPTION] The function calls `subprocess.run(...)` (so it is patchable at `subprocess.run`), captures
  output as text, and reads `.returncode`, `.stdout`, and `.stderr`. The plan specifies the flags
  (`--flat-playlist --dump-single-json`) but not the exact call form; T-S1-11 and the reuse source
  (`get_transcript.py`) establish the subprocess + JSON convention.
- [ASSUMPTION] Success is defined as `returncode == 0` **and** stdout parses as JSON; any other outcome
  yields `None`. This is T-S1-11's rule applied to the sibling subprocess call.
- [ASSUMPTION] `stderr` is captured on the **same** `subprocess.run` call as stdout (not discarded, not
  merged into stdout), since `hidden_unavailable_count` depends on reading it. The plan says the count is
  "parsed from stderr WARNING", which requires stderr to be captured separately.
- [ASSUMPTION] `hidden_unavailable_count` is produced by delegating to `parse_hidden_unavailable`
  (T-S1-10) rather than by re-implementing the parse; the docstring names that function explicitly. Its
  own rules (first-occurrence, `0` when absent) are **not** re-pinned by this unit.
- [ASSUMPTION] The returned dict's keys are exactly `{id, title, uploader, entries, hidden_unavailable_count}`
  per the docstring, and each `entries` record is exactly `{id, title}` — the thin fields the flat listing
  supplies. Richer per-entry fields, if present in the yt-dlp document, are not part of this contract; the
  second stage (`fetch_metadata`) is what supplies rich fields.
- [ASSUMPTION] `type` and `source_url` — the other two `_manifest.json` `collection{}` fields — are **not**
  this function's output. `type` is a constant the manifest builder (T-S1-09) sets, and `source_url` is the
  `url` the caller already holds. This function reports only what yt-dlp told it.
- [ASSUMPTION] No `sys.exit` is called on failure; the `None` return is the sole failure signal.
- [ASSUMPTION] The precise yt-dlp argument vector (flag order, extra flags such as `--no-warnings` or
  `--sleep-requests`) is an implementer detail and is **not** asserted by this unit — except that
  `--no-warnings`, or anything else suppressing stderr warnings, would be incompatible with parsing
  `hidden_unavailable_count` from stderr. The tests pin behavior on the mocked return code, stdout, and
  stderr, not on the exact command line.

## Key entities (canonical schema excerpt)

```jsonc
// _manifest.json → collection{}
"collection": { "type","id","title","uploader","source_url","hidden_unavailable_count" }
// _manifest.json → members[] — one per entry this function returns, in the same order
{ "position": 1, "video_id":"…", "title":"…",
  "status":"ok|metadata_failed|skipped_unavailable", "files": {…}|null,
  "transcript": { "available","language","type" } }
// per-video artifact → collection{} (null for true singles)
"collection": { "type","id","title","uploader","position","total_members" }
```

This function populates the manifest's `collection{id,title,uploader,hidden_unavailable_count}` and
supplies the ordered `entries` that become `members[]`. An entry's index drives `members[].position`, the
artifact's `collection{position, total_members}`, and the zero-padded numeric prefix in the on-disk
basename (T-S1-13) — which is why order and completeness are the load-bearing parts of the contract.
Members that enumerate here but fail the later per-video fetch are **listed with status + reason, never
silently dropped** (plan §`_manifest.json`; SKILL.md §Graceful degradation), and
`hidden_unavailable_count` tells a downstream consumer how many of them YouTube itself flagged as hidden.

`parse_hidden_unavailable` (T-S1-10) is reused here **unchanged**; none of this unit's rules constrain it.

## NEEDS CLARIFICATION

Two items raised in drafting are **resolved**; the rest remain genuinely undecided and are deliberately
left out of this unit's tested contract (testing them would freeze incidental behavior into a contract).
The undecided ones are logged in `to-do.md`.

- [RESOLVED 2026-07-15] **The "omits" claim was wrong and is now corrected.** The spec author flagged that
  `docs/IMPLEMENTATION_PLAN_v2.md:76-77` (§Grounding) and this file's sibling
  `docs/specs/A3-T-S1-10-parse_hidden_unavailable.spec.md` provenance header both claimed yt-dlp "omits the
  5 hidden unavailable videos from the flat list" — contradicted by the corrected docstring, by a live
  measurement (a real 24-member playlist returned **all 24 entries**, the 5 unavailable ones with
  `title: None`), and by the I-02 row's own "24 members, 19 ok / 5 metadata_failed", a total only reachable
  if nothing was omitted. Both sites have been reworded. T-S1-10's behavior was never affected — it only
  parses stderr — so only the rationale was wrong.
- [RESOLVED 2026-07-15] **Catalog row added.** `T-S1-15 | enumerate_playlist` now exists in the plan's unit
  catalog and the progress checklist; the function was previously covered only by `[done] SK1-ORCH`.
- [NEEDS CLARIFICATION] **Empty playlist (return code 0, zero entries).** Whether this should yield a dict
  with an empty `entries` list or `None` is unspecified. The former seems right (it is a successful
  enumeration of a real, empty playlist), but nothing documented decides it, so it is left out of this
  unit's tested contract.
- [NEEDS CLARIFICATION] **Missing playlist-level keys** (`id`, `title`, or `uploader` absent from an
  otherwise valid yt-dlp document). Whether these become `None` in the returned dict or make the whole call
  a failure is unspecified. T-S1-05 (`build_video_block`) tolerates missing optional fields, which suggests
  `None`, but the analogy is not documented policy.
- [NEEDS CLARIFICATION] **An entry lacking an `id`.** Whether such an entry is kept (with a null id),
  dropped, or fails the call is unspecified. Dropping it would shift subsequent positions, so keeping it
  seems safer, but this is not decided.
- [NEEDS CLARIFICATION] **A non-playlist URL reaching this function** (e.g. yt-dlp returns a single-video
  document with no `entries`). `classify_input` (T-S1-03) is specified to prevent this, so no real caller
  reaches it; the behavior is undefined and deliberately untested.
- [NEEDS CLARIFICATION] Whether `--sleep-requests` / `request_delay` (T-S1-12) applies to this
  enumeration call. The risk section frames the delay as covering "~24 sequential **per-video** calls" and
  T-S1-12 as applying "before every network-hitting iteration", which reads as the per-video loop; the
  single up-front enumeration call is not addressed either way.
