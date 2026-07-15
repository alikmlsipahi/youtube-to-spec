# Spec — `classify_failure` (T-S1-16)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Risks & mitigations, `docs/IMPLEMENTATION_PLAN_v2.md:447-454` — "yt-dlp / YouTube fragility &
> rate-limiting over ~24 sequential per-video calls"). This unit is the **precondition** for retry:
> the collector currently collapses every network failure into a single value (`fetch_metadata` →
> `None`, `fetch_transcript` → an empty block), so "YouTube blocked us" and "this video has no
> captions" are today indistinguishable at every call site. Retrying without this distinction is
> actively harmful — retrying a private video is wasted traffic that *raises* the rate-limit risk the
> retry exists to manage. **No test code, no golden output tables here.**

## One-line purpose

Given the *name* and *text* of a failure, decide whether it is worth retrying — return `"transient"`
for failures that a later attempt might survive (rate limiting, bot checks, server errors, network
faults) and `"permanent"` for failures that will never change (private, removed, age-restricted, no
captions). Pure computation only; it performs no I/O, sleeps nothing, and retries nothing.

## Signature

```python
def classify_failure(name: str, text: str) -> str
```

Returns the string `"transient"` or the string `"permanent"` — nothing else, ever.

## Inputs

Two plain strings, so that a single unit serves **both** of the collector's unrelated failure
sources without either one leaking its types into this function:

- `name: str` — a failure's class name when one exists, otherwise `""`.
  - yt-dlp path (a subprocess, so there is no exception object): `""`.
  - transcript path (a real exception object): `type(exc).__name__`.
- `text: str` — the failure's human-readable text.
  - yt-dlp path: the subprocess's captured **stderr**.
  - transcript path: `str(exc)`.

Either argument may be empty. Neither may be `None` — callers pass `""` instead. [ASSUMPTION]

> **Why strings and not exception classes.** This is a deliberate design constraint, not a stylistic
> preference. The offline unit tier stubs the script's network dependencies in `sys.modules` with
> mock objects *before* importing the module under test, so the real exception classes are not
> importable in that tier. A module-level `except SomeLibraryError:` naming a stubbed attribute would
> raise `TypeError: catching classes that do not inherit from BaseException` and take the whole tier
> down. Classifying on `(name, text)` keeps this unit pure, keeps it testable with plain fakes, and
> keeps the script importable offline.

## Expected behavior

- Return `"transient"` when **either** `name` matches a known transient failure class **or** `text`
  contains a known transient signal.
- Return `"permanent"` when **either** `name` matches a known permanent failure class **or** `text`
  contains a known permanent signal.
- **Unknown failures return `"permanent"`.** [ASSUMPTION] Rationale: an unrecognized failure retried
  is extra traffic aimed at a service that just failed us, which works against the very goal
  (rate-limit avoidance) that retry serves. It is also the behavior-preserving choice — the collector
  does not retry anything today, so "unknown → permanent" changes nothing for failures this unit does
  not yet understand.
- Matching on `text` is **case-insensitive** and **substring-based** (the signals below are fragments
  of longer real-world messages, never whole messages). Matching on `name` is an **exact** match
  against a class name. [ASSUMPTION]
- The function is **pure**: no I/O, no sleeping, no logging, no side effects, no hidden state. The
  same `(name, text)` always yields the same answer.

### Transient signals

Failure class names (transcript path):

- `RequestBlocked` — the library's "YouTube is refusing this request" signal.
- `IpBlocked` — a **subclass** of `RequestBlocked`; both must classify transient. This unit matches on
  the exact leaf name it is handed, so **both names must be listed independently** — there is no class
  hierarchy available to a string comparison.
- `YouTubeRequestFailed` — an upstream request failure.

Message fragments (either path):

- `HTTP Error 429` / `Too Many Requests` — explicit rate limiting.
- `Sign in to confirm you're not a bot` — YouTube's bot check. **This is the single most important
  transient signal**: it is what an over-paced run actually receives, and misreading it as permanent
  is what turns a recoverable throttle into silent data loss.
- `HTTP Error 500`, `HTTP Error 502`, `HTTP Error 503` — server-side faults.
- `timed out` / `timeout` — a stalled request.
- `Connection reset` / `Connection refused` / `Temporary failure in name resolution` — transport and
  DNS faults.

### Permanent signals

Failure class names (transcript path):

- `NoTranscriptFound`, `TranscriptsDisabled` — this video will never yield captions.
- `VideoUnavailable`, `VideoUnplayable`, `AgeRestricted` — this video will never yield metadata.

Message fragments (either path):

- `Private video` / `This video is private`
- `Video unavailable` / `This video is not available`
- `removed by the uploader`
- `members-only` / `join this channel`
- `Sign in to confirm your age`

## Edge cases

- **The two "Sign in to confirm…" messages are opposites and share a prefix.** `Sign in to confirm
  you're not a bot` is **transient** (a throttle — retry may clear it). `Sign in to confirm your age`
  is **permanent** (an age gate — retrying forever will never open it). Matching on the shared prefix
  `Sign in to confirm` alone is wrong for one of the two whichever way it resolves; the distinguishing
  tail is required. This is the sharpest trap in the unit.
- `name` empty and `text` empty → `"permanent"` (unknown).
- `name` empty and `text` carrying a transient signal → `"transient"` (the yt-dlp path always looks
  like this — it has no class name to offer).
- `name` recognized and `text` empty → classified on `name` alone.
- A transient `name` with permanent-looking `text`, or vice versa → see the precedence rule in
  Assumptions.
- Real stderr is multi-line and prefixed (`ERROR: [youtube] abc123: …`); a signal appears **inside** a
  longer line, never as the whole string. Substring matching is what makes this work.
- Mixed case (`too many requests` vs `Too Many Requests`) → same answer.
- `text` containing a transient signal **twice** → still one answer, `"transient"`.

## Acceptance scenarios (Given / When / Then)

- **Given** `name = ""` and `text` a multi-line yt-dlp stderr containing `HTTP Error 429`, **when**
  `classify_failure(name, text)` runs, **then** it returns `"transient"`.
- **Given** `name = ""` and `text` a yt-dlp stderr containing `Private video`, **when** it runs,
  **then** it returns `"permanent"`.
- **Given** `name = "IpBlocked"` and `text = ""`, **when** it runs, **then** it returns `"transient"`.
- **Given** `name = "RequestBlocked"` and `text = ""`, **when** it runs, **then** it returns
  `"transient"` — the subclass and its parent classify alike.
- **Given** `name = "TranscriptsDisabled"` and `text = ""`, **when** it runs, **then** it returns
  `"permanent"`.
- **Given** `name = ""` and `text` containing `Sign in to confirm you're not a bot`, **when** it runs,
  **then** it returns `"transient"`.
- **Given** `name = ""` and `text` containing `Sign in to confirm your age`, **when** it runs,
  **then** it returns `"permanent"` — the two "Sign in to confirm" messages resolve **oppositely**.
- **Given** `name = ""` and `text = "ERROR: something nobody has ever seen"`, **when** it runs,
  **then** it returns `"permanent"` — unknown failures are not retried.
- **Given** `name = ""` and `text = ""`, **when** it runs, **then** it returns `"permanent"`.
- **Given** a transient signal in lowercase and the same signal in its documented casing, **when**
  each runs, **then** both return `"transient"`.

## Assumptions

- [ASSUMPTION] Unknown → `"permanent"`. See Expected behavior for the rationale. The alternative
  (unknown → `"transient"`) would retry failures nobody has characterized, adding traffic during an
  incident we do not understand.
- [ASSUMPTION] **Whenever any transient signal is present at all, `"transient"` wins** — regardless of
  what else is present. This covers two distinct kinds of conflict, and it resolves both the same way:
  - **`name` vs `text`** — a transient class name carrying permanent-looking text, or the reverse.
  - **Within `text`** — a single real stderr block carrying *both* a transient and a permanent signal
    (yt-dlp stderr is multi-line, so a rate-limit line and a `Video unavailable` line can genuinely
    co-occur in one failure).

  Rationale for resolving toward transient in every case: the cost of a wrong `"transient"` is a
  bounded, backed-off, capped retry that eventually gives up and records the video anyway; the cost of
  a wrong `"permanent"` is exactly the silent data loss this whole change exists to remove (a
  recoverable throttle recorded forever as "this video has no captions"). The asymmetry favors
  retrying, and it favors it identically no matter where the conflict lives. In practice a "transient
  present" check that runs **before** any permanent check satisfies this rule for both kinds at once.
- [ASSUMPTION] The returned values are the bare strings `"transient"` / `"permanent"` rather than an
  enum or a bool. Strings keep the unit dependency-free and readable in the manifest `reason` text
  that ultimately quotes them; a bool (`should_retry`) would lose the vocabulary the manifest wants.
- [ASSUMPTION] The signal lists above are **not exhaustive** and are expected to grow as real
  failures are observed. The unit's contract is the *classification behavior*, not a frozen list;
  adding a newly-observed signal to the right bucket later is a normal change, not a contract break.
- [ASSUMPTION] This unit does not decide **how many** times to retry, **how long** to wait, or
  **whether** to write an artifact — those are `backoff_delay` (T-S1-17) and the `main()`
  orchestration loop's concerns. This unit only answers "is another attempt worth making?"

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own — it touches no artifact field. Its answer is
consumed by the `main()` orchestration loop, which turns a `"transient"` verdict that survives all
retries into the manifest member status `rate_limited`, and a `"permanent"` verdict into the existing
`metadata_failed`:

```jsonc
// _manifest.json → members[]
{
  "status": "ok" | "metadata_failed" | "rate_limited",  // rate_limited is new with this change
  "reason": "transcript fetch rate-limited after 5 retries",
  "files": null
}
```

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether `AgeRestricted` is truly permanent. It is permanent for an
  unauthenticated client, which is the only kind this collector has; were cookie/OAuth support ever
  added (not in the plan or the roadmap), the same video would become fetchable and the
  classification would want revisiting.
- [NEEDS CLARIFICATION] Whether a bare `HTTP Error 403` should be transient or permanent. Observed
  in the wild for both throttling and hard geo-blocks, so it is deliberately **absent** from both
  lists above and therefore falls through to `"permanent"` by the unknown rule. Listed here so the
  omission reads as a decision rather than an oversight.
