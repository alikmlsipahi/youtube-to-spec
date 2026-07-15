# Spec — `fetch_metadata` graceful degradation (T-S1-11)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #3 `fetch_metadata(video_id)` — "`yt-dlp --skip-download --dump-json` via subprocess; on
> failure return `None` + record (graceful degradation). Subprocess (not Python API) for stable JSON +
> per-video isolation"; catalog row T-S1-11; capability "Graceful degradation"; §Reuse "`except Exception
> → stderr → sys.exit(1)` convention" — but per-video failures here must **not** exit). **No test code,
> no golden output tables here.**
>
> **[v2.3 — RE-SIGNED]** This unit's return type changed from `dict | None` to
> `tuple[dict | None, str | None]`, and it gained a `timeout` parameter. The old contract is not being
> *fixed around*; it is the thing being fixed. See "Why this unit was re-signed" below. Precedent for
> re-signing a green unit rather than working around it: `artifact_basename` in v2.1
> (`docs/IMPLEMENTATION_PLAN-progress.md:67`).

## Why this unit was re-signed

The previous contract was *"any failure → `None`"*. That single sentinel is information-destroying:
it renders "this video is private" and "YouTube just rate-limited us" **the same value**, at the only
boundary where the difference is still knowable (the subprocess's stderr, which the old
implementation captured and then discarded).

Everything downstream inherits that loss. A caller holding `None` cannot decide whether to retry,
because it cannot tell a permanent failure from a transient one — so it either retries everything
(burning minutes of backoff on videos that will never exist, adding traffic during the exact incident
retry exists to survive) or retries nothing (today's behavior). Retry is not implementable on top of
this contract. Hence the re-sign: the failure's *kind* must survive the return.

## One-line purpose

Fetch one video's metadata by shelling out to yt-dlp, returning the parsed metadata dict on success
and, on any failure, **`None` plus a classification of that failure** (`"transient"` or
`"permanent"`) — so a single bad video degrades gracefully and the surrounding batch continues, and
so the caller can tell a failure worth retrying from one that never will be.

## Signature

```python
def fetch_metadata(video_id: str, *, timeout: float | None = None) -> tuple[dict | None, str | None]
```

Performs a subprocess call (`subprocess.run`) to yt-dlp; it does **not** use the Python yt-dlp API
(subprocess is chosen for stable JSON output and per-video isolation). It is **not** pure — but it is
deterministic given a mocked subprocess, and the unit tier mocks the subprocess so no network is
touched.

## Inputs

- `video_id: str` — an 11-char YouTube video id (already extracted upstream via `extract_video_id`).
- `timeout: float | None` — keyword-only. Seconds to allow the subprocess before killing it; `None`
  means no limit. CLI `--timeout`, default `120.0`. The call was previously **unbounded**: a yt-dlp
  process that hangs would hang the entire run forever, with no flag to escape it.

The function invokes, conceptually, `yt-dlp --skip-download --dump-json <video_id>` via
`subprocess.run`, capturing stdout (the per-video JSON) and stderr, and inspecting the return code.

## Expected behavior

Returns a 2-tuple `(meta, failure)`. Exactly one of the two is ever non-`None`:

- **Success:** return code `0` **and** stdout parses as JSON → `(parsed_dict, None)`.
- **Failure:** → `(None, kind)` where `kind` is `"transient"`, `"permanent"` or **`"unknown"`
  [v2.5]**, obtained by handing the failure to `classify_failure` (T-S1-16). **This unit does not
  classify anything itself** — it captures the evidence and delegates the judgement, so the signal
  lists live in exactly one place. It follows that this unit gained the third verdict for free: it
  passes through whatever the classifier says, and a test of this unit should not need to know which
  strings produce which answer.

How the evidence is gathered per failure mode:

- **Non-zero return code** → `classify_failure("", stderr)`. There is no exception object, so the
  name is empty and stderr carries the whole story (this is why stderr must be captured and must not
  be suppressed).
- **Subprocess raised** (tool missing, timeout expired, OS error) → `classify_failure(type(exc).__name__, str(exc))`.
  Note this needs no special-casing per exception type, and that is the point of routing it through
  the classifier: an expired timeout produces text containing a timeout signal and is called
  `"transient"` (correct — the next attempt may well succeed), while a yt-dlp that is not installed
  produces text nothing recognizes and is called **`"unknown"` [v2.5]** — also correct, and usefully
  so: it is not retried (installing it is not something a retry achieves), and the caller prints the
  text it did not recognize, which is exactly the `No such file or directory: 'yt-dlp'` a user needs
  to see. Before v2.5 this was flattened to `"permanent"` and the message was thrown away.
- **Return code `0` but unparseable/empty stdout** → `(None, "permanent")`. A clean exit that emits
  garbage is not a throttle, and re-running it is not expected to produce different bytes. [ASSUMPTION]

Unchanged from the original contract, and still load-bearing:

- The function **never raises** on any failure path and **never** calls `sys.exit`. Failure is always
  signalled by the return value. A single video's failure must not crash the run.
- The per-video try/except isolation the plan's risk section calls for resolves, at this unit's
  boundary, to "failure → `(None, kind)`".

## Edge cases

- **Non-zero exit, stderr says the video is private/deleted/unavailable** → `(None, "permanent")`.
- **Non-zero exit, stderr carries a rate-limit or bot-check signal** → `(None, "transient")`. This is
  the case the whole re-sign exists to make expressible; under the old contract it was indistinguishable
  from the line above.
- **Non-zero exit, stderr empty** → `(None, "unknown")` — nothing was offered to recognize. **[v2.5]**
- **Non-zero exit, stderr carries text the classifier does not recognize** → `(None, "unknown")`.
  **[v2.5]** This is the drift case: a reworded YouTube message lands here rather than being
  relabelled `"permanent"`.
- **Return code 0 with valid JSON stdout** → `(parsed_dict, None)`.
- **Return code 0 but unparseable/empty stdout** → `(None, "permanent")`. [ASSUMPTION]
- **yt-dlp executable missing (`FileNotFoundError`)** → `(None, "unknown")`, not an exception.
  **[v2.5]** Not retried either way; the difference is that the message now reaches the user.
- **Timeout expires** → `(None, "transient")`, not an exception.
- **`timeout=None`** → no time limit is imposed (the pre-v2.3 behavior remains reachable).
- The function must **never** raise on any of the above.

## Acceptance scenarios (Given / When / Then)

- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr describing a
  private video, **when** `fetch_metadata("someVideoId")` runs, **then** it returns `(None, "permanent")`
  and does not raise.
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr carrying a
  rate-limit signal, **when** it runs, **then** it returns `(None, "transient")` — the same return
  code as the previous scenario, classified oppositely, on stderr alone.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout being a valid JSON object,
  **when** it runs, **then** it returns that object as a `dict` paired with `None`.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout that is not valid JSON,
  **when** it runs, **then** it returns `(None, "permanent")` and does not raise.
- **Given** `subprocess.run` is mocked to raise as though the yt-dlp executable were missing, **when**
  it runs, **then** it returns `(None, "unknown")` and does not raise. **[v2.5]**
- **Given** `subprocess.run` is mocked to raise as though the call had timed out, **when** it runs,
  **then** it returns `(None, "transient")` and does not raise.
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with **empty** stderr,
  **when** it runs, **then** it returns `(None, "unknown")` — nothing was offered to recognize.
  **[v2.5]**
- **Given** `subprocess.run` is mocked to return a **non-zero** return code with stderr carrying text
  that matches no known signal, **when** it runs, **then** it returns `(None, "unknown")` — **not**
  `"permanent"`. This is the drift case, and it is the scenario the v2.5 revision exists for. **[v2.5]**
- **Given** two videos processed in sequence where the first's subprocess fails, **when** the batch
  continues, **then** the failure is isolated to that video — the second still proceeds.

## Assumptions

- [ASSUMPTION] The function calls `subprocess.run(...)` (so it is patchable at `subprocess.run`),
  captures output as text, and reads `.returncode`, `.stdout` and `.stderr`. The plan specifies
  "subprocess … `--dump-json`" but not the exact call form.
- [ASSUMPTION] Success is defined as `returncode == 0` **and** stdout parses as JSON; any other
  outcome yields `(None, kind)`.
- [ASSUMPTION] Classification is **delegated** to `classify_failure` (T-S1-16), never reimplemented
  here. This unit's own contract is therefore "capture the right evidence and pass it on" — which
  strings map to which verdict is T-S1-16's contract, not this one's. A test of this unit should not
  need to know the signal lists.
- [ASSUMPTION] The "+ record" part of "on failure return `None` + record" is still performed by the
  **caller** (the batch loop builds the `metadata_failed` / `rate_limited` member record). This unit
  only returns the tuple.
- [ASSUMPTION] No `sys.exit` on a per-video failure — the script-wide `except → sys.exit(1)`
  convention applies to fatal top-level errors, not a single video's metadata miss.
- [ASSUMPTION] `timeout` is keyword-only and defaults to `None`, so the parameter is additive: an
  existing positional call site keeps compiling and keeps its old (unbounded) behavior. Only the
  return type is a breaking change.

## Key entities (canonical schema excerpt)

```jsonc
// per-video artifact → extraction{}
"extraction": { "metadata_ok","transcript_ok","warnings","tool_versions" }

// _manifest.json member, by this unit's return:
{ "status":"metadata_failed", "reason":"…",                    "files": null }  // (None, "permanent")
{ "status":"rate_limited",    "reason":"… rate-limited after N retries", "files": null }  // (None, "transient"), retries exhausted
```

The `failure` half of the tuple is what lets the loop tell those two rows apart. `metadata_ok: false`
follows from `meta is None` exactly as before; the failed video stays listed with a reason rather than
being silently dropped.

## NEEDS CLARIFICATION

- [RESOLVED 2026-07-15] **Return code 0 with empty stdout is `"permanent"`, exactly like return code 0
  with unparseable stdout** — the two are one case, not two, and the Edge cases section above decides
  it. This item previously both decided the case and reopened it, which is a contradiction rather than
  an open question; a spec cannot ask the implementer to treat a case as `"permanent"` and
  simultaneously tell them it is undecided. Resolved toward `"permanent"` on the stated reasoning: a
  clean exit is not a throttle, and re-running a process that exited `0` is not expected to produce
  different bytes. The counter-case (a truncated response from an overloaded upstream presenting this
  way) is real but unobserved; if it ever shows up, it will show up as a `metadata_failed` row for a
  video that plainly exists, which is a legible symptom to reopen this on.
- [NEEDS CLARIFICATION] The precise yt-dlp argument vector (flag order, extra flags) remains an
  implementer detail and is **not** asserted by this unit — with one constraint that *is* contractual
  as of v2.3: stderr must be captured and must not be suppressed, since it is now the sole evidence
  the classification is drawn from.
