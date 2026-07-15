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
>
> **[v2.3 — RE-SIGNED]** This unit's return type changed from `dict | None` to
> `tuple[dict | None, str | None]`, and it gained a `timeout` parameter — mirroring the identical
> re-sign of its sibling `fetch_metadata` (T-S1-11), and for the identical reason: a bare `None`
> cannot say *why*, so a caller cannot decide whether to retry. This call is now retried on transient
> failures. It is also the **highest-stakes** call in the script to get this right: it is a single
> up-front request that gates the entire run, so one 429 here kills a playlist collect before it
> fetches anything, where the same 429 on a per-video call costs one video. The order-preservation,
> null-title and hidden-unavailable rules below are **unchanged** by this re-sign.

## One-line purpose

Enumerate a playlist's identity and its **ordered** members by shelling out to yt-dlp's flat listing,
returning a dict carrying the playlist's `id`/`title`/`uploader`, the members in playlist order, and the
count of unavailable members yt-dlp hid from the listing — or, on any failure, **`None` plus a
classification of that failure** (`"transient"`, `"permanent"` or `"unknown"`), so an unreachable
playlist degrades
gracefully instead of aborting the run, and so a throttled one can be retried rather than written off.

## Signature

```python
def enumerate_playlist(url: str, *, timeout: float | None = None) -> tuple[dict | None, str | None]
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
- `timeout: float | None` — keyword-only. Seconds to allow the subprocess before killing it; `None`
  means no limit. CLI `--timeout`, default `120.0`. The call was previously **unbounded**: a hung
  yt-dlp would hang the whole run with no escape. **[v2.3]**

The function invokes, conceptually, `yt-dlp --flat-playlist --dump-single-json <url>` via
`subprocess.run`, capturing **stdout** (the single playlist JSON document), capturing **stderr** (which
carries the hidden-unavailable WARNING), and inspecting the process return code.

## Expected behavior

Returns a 2-tuple `(playlist, failure)`. Exactly one half is ever non-`None`. **[v2.3]**

- **Success path:** when the subprocess exits with **return code `0`**, parse its captured **stdout** as
  a single JSON document and return `(playlist, None)`, where `playlist` is a dict of the shape:
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
- **Failure path (graceful):** on any failure, return `(None, kind)` where `kind` is `"transient"`,
  `"permanent"` or **`"unknown"` [v2.5]** — do **not** raise, and do **not** call `sys.exit`. This follows the convention T-S1-11
  establishes for `fetch_metadata`: the script-wide `except → stderr → sys.exit(1)` convention applies
  to fatal top-level errors, not to a yt-dlp call that came back unhappy. Failure is always signalled
  by the return value, never by an exception. **[v2.3]**
- **Classification is delegated**, never reimplemented here — exactly as in T-S1-11: **[v2.3]**
  - **Non-zero return code** → `classify_failure("", stderr)` (T-S1-16). No exception object exists, so
    the name is empty and stderr carries the evidence.
  - **Subprocess raised** (tool missing, timeout expired, OS error) →
    `classify_failure(type(exc).__name__, str(exc))`. No per-exception special-casing: a missing yt-dlp
    yields text nothing recognizes → **`"unknown"` [v2.5]** (still not retried — no retry installs it —
    but the message now reaches the user);
    an expired timeout yields text carrying a timeout signal → `"transient"` (also correct).
  - **Return code `0` but unparseable/empty stdout** → `(None, "permanent")`. A clean exit emitting
    garbage is not a throttle. [ASSUMPTION]
  - **Return code `0`, stdout parses, but the result is not a JSON object** (a list, `null`, a bare
    string or number) → `(None, "permanent")`. **[v2.4]** Parsing succeeding is not the same as the
    document being usable: a playlist document is a mapping, and anything else cannot be read as one.
    This case is called out separately from "unparseable" because it is the one that used to escape —
    `json.loads` succeeds, so the parse guard lets it through, and the *next* read is what fails. The
    guard has to be "is this a dict", not "did it parse".
- **stderr is doing two jobs now.** It was already the sole source of `hidden_unavailable_count`; as of
  v2.3 it is *also* the sole evidence for classification. Anything that suppresses it (`--no-warnings`)
  breaks both. **[v2.3]**

## Edge cases

- **Return code 0 with a valid playlist JSON on stdout:** returns `(dict, None)` as described above.
- **Non-zero exit, stderr says the playlist is private/deleted/region-blocked:** returns
  `(None, "permanent")`.
- **Non-zero exit, stderr carries a rate-limit or bot-check signal:** returns `(None, "transient")` —
  the same return code as the line above, classified oppositely on stderr alone. **[v2.3]**
- **Non-zero exit, stderr empty:** returns `(None, "unknown")` — nothing was offered to recognize. **[v2.5]**
- **Non-zero exit, stderr carries text matching no known signal:** returns `(None, "unknown")`, **not**
  `"permanent"`. The drift case. **[v2.5]**
- **Return code 0 but unparseable or empty stdout:** treated as a failure → returns
  `(None, "permanent")`. A successful exit with garbage output must not propagate a parse exception to
  the caller. [ASSUMPTION] — this mirrors T-S1-11's identical defensive rule.
- **Return code 0, stdout parses, but is not a JSON object** (`[1,2,3]`, `null`, `"text"`, `42`):
  treated as a failure → returns `(None, "permanent")`. **The function must not raise here** — this is
  the same "never raises" guarantee as every other failure path, and it is the path that historically
  broke it. **[v2.4]**
- **yt-dlp executable missing (`FileNotFoundError`) or other subprocess error:** treated as a failure →
  returns `(None, "unknown")`, not an exception. **[v2.5]** [ASSUMPTION] — again mirroring T-S1-11.
- **Timeout expires:** returns `(None, "transient")`, not an exception. **[v2.3]**
- **`timeout=None`:** no time limit is imposed (the pre-v2.3 behavior remains reachable). **[v2.3]**
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

- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr describing a
  private playlist, **when** `enumerate_playlist` runs on any URL, **then** it returns
  `(None, "permanent")` and does not raise.
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr carrying a
  rate-limit signal, **when** it runs, **then** it returns `(None, "transient")` — same return code as
  above, opposite classification.
- **Given** `subprocess.run` is mocked to raise as though the call had timed out, **when** it runs,
  **then** it returns `(None, "transient")` and does not raise.
- **Given** `subprocess.run` is mocked to raise as though the yt-dlp executable were missing, **when**
  it runs, **then** it returns `(None, "unknown")` and does not raise. **[v2.5]**
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with **empty** stderr,
  **when** it runs, **then** it returns `(None, "unknown")` — nothing was offered to recognize. **[v2.5]**
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr matching no
  known signal, **when** it runs, **then** it returns `(None, "unknown")` — **not** `"permanent"`.
  The drift case: the same return code as the private-playlist and rate-limit scenarios, resolved a
  third way on stderr alone. **[v2.5]**
- **Given** `subprocess.run` is mocked to return return code `0` with stdout being a valid flat-playlist
  JSON document, **when** `enumerate_playlist` runs, **then** it returns a dict carrying the playlist's
  `id`, `title`, and `uploader` drawn from that document, paired with `None`.
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
  JSON, **when** `enumerate_playlist` runs, **then** it returns `(None, "permanent")` rather than
  raising.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout that **parses cleanly but
  is not an object** — a JSON array, `null`, a bare string, a bare number — **when**
  `enumerate_playlist` runs, **then** it returns `(None, "permanent")` rather than raising, for each
  of those shapes. **[v2.4]**

## Assumptions

- [ASSUMPTION] The function calls `subprocess.run(...)` (so it is patchable at `subprocess.run`), captures
  output as text, and reads `.returncode`, `.stdout`, and `.stderr`. The plan specifies the flags
  (`--flat-playlist --dump-single-json`) but not the exact call form; T-S1-11 and the reuse source
  (`get_transcript.py`) establish the subprocess + JSON convention.
- [ASSUMPTION] Success is defined as `returncode == 0` **and** stdout parses as JSON; any other outcome
  yields `(None, kind)`. This is T-S1-11's rule applied to the sibling subprocess call.
- [ASSUMPTION] **[v2.3]** Classification is **delegated** to `classify_failure` (T-S1-16), never
  reimplemented here. This unit's contract is "capture the right evidence and pass it on"; which
  strings map to which verdict is T-S1-16's contract, not this one's. A test of this unit should not
  need to know the signal lists.
- [ASSUMPTION] **[v2.3]** `timeout` is keyword-only and defaults to `None`, so the parameter is
  additive: an existing positional call site keeps compiling and keeps its old unbounded behavior.
  Only the return type is a breaking change.
- [ASSUMPTION] **[v2.3]** This unit does not retry. It reports the failure's kind; **how many** times
  to retry and **how long** to wait between attempts belong to the orchestration loop and to
  `backoff_delay` (T-S1-17). This unit stays a single subprocess call.
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
  "status":"ok|metadata_failed|rate_limited", "files": {…}|null,   // rate_limited is new in v2.3
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
- [RESOLVED 2026-07-15] **Return code 0 with valid JSON that is not an object used to raise**,
  violating this unit's own "never raises" contract and killing the run. `json.loads` succeeds on
  `[1,2,3]` or `null`, so the parse guard let it through, and the *next* read — outside the try — threw
  `AttributeError`. Measured before the fix, not inferred: mocked `stdout='[1,2,3]'` raised
  `AttributeError: 'list' object has no attribute 'get'`; `'null'` the same. The sibling
  `fetch_metadata` was never affected — it assumes nothing about the parsed shape. Now specified above
  as an edge case and an acceptance scenario, fixed in v2.4, and pinned by tests. The lesson worth
  keeping: **"it parsed" is not "it is usable"**, and a guard written as `try: json.loads` answers only
  the first question.
- [RESOLVED 2026-07-15] **Whether the rate-limit machinery applies to this enumeration call — it
  does.** The question was previously open because the risk section frames the delay as covering
  "~24 sequential **per-video** calls", which reads as the per-video loop, leaving the single up-front
  enumeration call unaddressed either way. Resolved in v2.3 with the retry work, on the reasoning that
  this call carries the **whole run**: a 429 here kills a playlist collect before it fetches anything,
  where the same 429 on a per-video call costs one video. Concretely: this call **is** retried on a
  `"transient"` classification, with the same `--retries` / `--retry-base` / `--retry-cap` budget as
  the per-video calls. It is **not** preceded by a `--sleep-requests` pace — there is nothing before it
  to be paced against, and `hit_network` gating already exempts the run's first network call by design.
