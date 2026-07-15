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

Given the *name* and *text* of a failure, say what we know about it — `"transient"` for failures a
later attempt might survive (rate limiting, bot checks, server errors, network faults),
`"permanent"` for failures that will never change (private, removed, age-restricted, no captions),
and **`"unknown"` when we recognize nothing at all**. Pure computation only; it performs no I/O,
sleeps nothing, and retries nothing.

## Signature

```python
def classify_failure(name: str, text: str) -> str
```

Returns exactly one of `"transient"`, `"permanent"`, or `"unknown"` — nothing else, ever.

## Why `"unknown"` is a separate answer **[v2.5]**

This unit used to return `"permanent"` for an unrecognized failure, folding *"I know this will never
succeed"* together with *"I have never seen this before"*. It **computed** the distinction — the
recognized-permanent branch and the fall-through were already separate code paths — and then threw it
away by returning the same string from both.

That is the same information-destroying collapse this project fixed one level down in v2.3, where
`fetch_metadata`'s bare `None` made "this video is private" and "YouTube rate-limited us" the same
value. The fix there was to stop destroying what the function already knew. This is that fix, applied
to the function that told it what to think.

It matters because **this unit is a wall of string literals matched against someone else's copy**.
When YouTube or yt-dlp rewords a message, the signal stops matching, the failure falls through, and
— under the old contract — it was silently relabelled `"permanent"`. Retry stops. A blocked
transcript gets written down as "this video has no captions". Nothing raises, nothing fails, no test
breaks. The whole retry apparatus quietly reverts to the bug it was built to remove.

This is not hypothetical. It has happened twice in this project already: yt-dlp's stderr wording
drifted and broke `parse_hidden_unavailable`'s anchor (recorded on the I-02 row), and YouTube ships
the bot check with a typographic apostrophe while this spec's signal was ASCII — caught by an
implementer's eye, not by any test.

Drift cannot be tested for in advance: a frozen fixture pins text we have already seen, and drift is
by definition text we have not. **The only detector is to make the unrecognized case visible the
moment it occurs in the wild** — which requires this unit to say "unknown" out loud instead of
guessing "permanent".

`"unknown"` does **not** change retry policy: callers test `!= "transient"`, so an unknown failure is
not retried, exactly as before. What changes is that the caller can now tell the difference, refuse
to write down a conclusion it has not earned, and print the text it did not recognize.

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
- **Unrecognized failures return `"unknown"`.** **[v2.5]** Neither a transient nor a permanent signal
  matched, so the unit reports that it recognized nothing rather than guessing. See "Why `"unknown"`
  is a separate answer" above — this is the whole point of the unit's v2.5 revision.
  - `"unknown"` is **not retried** by any caller (they test `!= "transient"`), so the retry policy is
    unchanged from when this case returned `"permanent"`. The rationale for not retrying still
    stands: an unrecognized failure retried is extra traffic aimed at a service that just failed us,
    working against the very goal retry serves.
  - What `"unknown"` buys is not a different retry decision but an **honest one**: a caller can now
    refuse to record a conclusion it has not earned (an unrecognized transcript failure is not
    evidence that a video has no captions), and can print the text it did not recognize.
- Matching on `text` is **case-insensitive** and **substring-based** (the signals below are fragments
  of longer real-world messages, never whole messages). Matching on `name` is an **exact** match
  against a class name. [ASSUMPTION]
- **Apostrophes are normalized before matching**: the typographic apostrophe `’` (U+2019) is folded to
  the ASCII `'` (U+0027). This is not a cosmetic nicety. YouTube's own copy ships the **typographic**
  form — the real message is `Sign in to confirm you’re not a bot` — while the signal written below,
  like any hand-typed string, is ASCII. Without the fold, the single most important transient signal
  in this unit would silently fail to match its own real-world text and fall through to `"unknown"`.
  The signals as documented below are ASCII and match verbatim; the fold is what makes them match
  reality too. **[v2.5]** Note this is exactly the drift the `"unknown"` verdict exists to surface —
  had the fold been missing today, the bot check would land in `"unknown"`, the caller would print the
  unrecognized text, and a reader would see the apostrophe. Under the old contract it would have been
  relabelled `"permanent"` and lost the transcript in silence.
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
- **`This playlist is private`** — the playlist-level counterpart. **[v2.5]** Do not assume the video
  signals cover it: they say *video*, and a private playlist says *playlist*, so nothing matched.
  This gap was found by the `"unknown"` verdict on the day it was introduced — the old
  unknown→permanent collapse had been answering `"permanent"` for private playlists by accident, via
  the fall-through, and the test that covered it was green for the wrong reason. Recorded here as the
  first thing the canary caught, and as the reason it exists: a signal list is a wall of someone
  else's copy, and the holes in it are invisible until something refuses to guess.
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
- `name` empty and `text` empty → `"unknown"`. Nothing was offered to recognize, so nothing was
  recognized. **[v2.5]**
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
- **Given** `name = ""` and `text` containing `Sign in to confirm you're not a bot` with an **ASCII**
  apostrophe, **when** it runs, **then** it returns `"transient"`.
- **Given** `name = ""` and `text` containing `Sign in to confirm you’re not a bot` with the
  **typographic** apostrophe (U+2019) — the form YouTube actually sends — **when** it runs, **then** it
  returns `"transient"`, identically to the ASCII form.
- **Given** `name = ""` and `text` containing `Sign in to confirm your age`, **when** it runs,
  **then** it returns `"permanent"` — the two "Sign in to confirm" messages resolve **oppositely**.
- **Given** `name = ""` and `text = "ERROR: something nobody has ever seen"`, **when** it runs,
  **then** it returns `"unknown"` — the unit says it recognized nothing rather than guessing. **[v2.5]**
- **Given** `name = ""` and `text = ""`, **when** it runs, **then** it returns `"unknown"`. **[v2.5]**
- **Given** `name = "SomeExceptionNobodyListed"` and `text = ""`, **when** it runs, **then** it
  returns `"unknown"` — an unlisted class name is as unrecognized as unlisted text. **[v2.5]**
- **Given** a text carrying a **known permanent** signal, **when** it runs, **then** it returns
  `"permanent"` and **not** `"unknown"` — the two are different answers, and this is the pair that
  pins the distinction the unit used to collapse. **[v2.5]**
- **Given** a transient signal in lowercase and the same signal in its documented casing, **when**
  each runs, **then** both return `"transient"`.

## Assumptions

- [ASSUMPTION] **[v2.5]** Unknown → `"unknown"`, and callers do not retry it (they test
  `!= "transient"`), so the *retry* behavior is identical to when this case returned `"permanent"`.
  The alternative — unknown → `"transient"` — was considered and rejected: it would retry failures
  nobody has characterized, adding traffic during an incident we do not understand. It is also
  unnecessary, because the data loss that argued for it is removed at the caller instead: an
  `"unknown"` transcript failure is no longer written down as "this video has no captions", so a
  drifted signal costs a re-run, not a transcript.
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
- [ASSUMPTION] The returned values are the bare strings `"transient"` / `"permanent"` / `"unknown"`
  rather than an enum or a bool. Strings keep the unit dependency-free and readable in the manifest
  `reason` text that ultimately quotes them; a bool (`should_retry`) would lose the vocabulary the
  manifest wants — and, with three answers rather than two, could not express them at all. **[v2.5]**
- [ASSUMPTION] **[v2.5]** This unit does not carry the *unrecognized text itself* out to its caller —
  it returns only the verdict, and the caller already holds the text it passed in. The reporting of
  that text (so a human can see what drifted) is the caller's job, not this unit's; keeping it out
  preserves the unit's purity and leaves its signature untouched.
- [ASSUMPTION] The signal lists above are **not exhaustive** and are expected to grow as real
  failures are observed. The unit's contract is the *classification behavior*, not a frozen list;
  adding a newly-observed signal to the right bucket later is a normal change, not a contract break.
- [ASSUMPTION] This unit does not decide **how many** times to retry, **how long** to wait, or
  **whether** to write an artifact — those are `backoff_delay` (T-S1-17) and the `main()`
  orchestration loop's concerns. This unit only answers "what do we know about this failure?"

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own — it touches no artifact field. Its answer is
consumed by the `main()` orchestration loop, which maps each verdict to a manifest member status:

```jsonc
// _manifest.json → members[]
{
  "status": "ok" | "metadata_failed" | "rate_limited" | "unrecognized",
  "reason": "transcript fetch rate-limited after 5 retries",
  "files": null
}
```

| verdict | meaning | member status | artifact |
|---|---|---|---|
| `"transient"` | blocked, may clear | `rate_limited` | not written |
| `"permanent"` | **established** — private, removed, genuinely no captions | `metadata_failed`, or written as a complete artifact when the transcript is genuinely absent | per case |
| `"unknown"` | **[v2.5]** nothing established | `unrecognized` | **not written** |

The `"permanent"` / `"unknown"` split is the one this unit exists to preserve. `"permanent"` licenses
the caller to record a conclusion — *this video has no captions* — as fact. `"unknown"` licenses
nothing: the caller must not write that conclusion down, because the unit did not reach it.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether `AgeRestricted` is truly permanent. It is permanent for an
  unauthenticated client, which is the only kind this collector has; were cookie/OAuth support ever
  added (not in the plan or the roadmap), the same video would become fetchable and the
  classification would want revisiting.
- [NEEDS CLARIFICATION] Whether a bare `HTTP Error 403` should be transient or permanent. Observed
  in the wild for both throttling and hard geo-blocks, so it is deliberately **absent** from both
  lists above and therefore falls through to `"unknown"`. Listed here so the omission reads as a
  decision rather than an oversight. **[v2.5]** Note the fall-through is now a better place to leave
  it than it was: an undecided signal lands in `"unknown"`, which reports itself and refuses to write
  a conclusion, rather than being silently relabelled `"permanent"`.
- [NEEDS CLARIFICATION] **[v2.5]** Whether a repeatedly-observed `"unknown"` should eventually
  escalate — e.g. a run that sees the same unrecognized text on every video is almost certainly
  looking at drift rather than a one-off, and might reasonably stop rather than grind through the
  whole playlist reporting the same thing. This spec adds no such rule: the unit is pure and stateless
  and cannot count, and whether the *loop* should is a policy question nobody has needed answered yet.
- [NEEDS CLARIFICATION] **[v2.5]** This design catches drift on **first occurrence in the wild**, not
  before it. Proactive detection was investigated and ruled out on measurement, not taste: a frozen
  fixture pins text already seen and so cannot detect text not yet seen, and scanning the installed
  yt-dlp's source finds `Private video` / `members-only` / `confirm your age` but **zero** occurrences
  of `not a bot`, `Too Many Requests`, or `HTTP Error 429` — the signals that actually matter arrive
  from YouTube's servers and the HTTP layer, not from yt-dlp's code. Deliberately triggering a real
  rate limit to sample the current wording is not acceptable. The accepted limit: drift cannot be
  prevented, only stopped from being silent.
