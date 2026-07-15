# Spec — `backoff_delay` (T-S1-17)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Risks & mitigations, `docs/IMPLEMENTATION_PLAN_v2.md:447-454` — yt-dlp / YouTube rate-limiting
> over long sequential runs) and the existing jitter unit `request_delay` (T-S1-12,
> `docs/specs/A6-T-S1-12-request_delay.spec.md`), which this unit **builds on rather than
> duplicates**. Where `request_delay` paces *successful* traffic at a flat rate, this unit computes
> the *escalating* wait between retries of a failed request, so repeated failures back away from the
> service instead of hammering it. **No test code, no golden output tables here.**

## One-line purpose

Given a zero-based retry attempt number, compute how long to wait before that attempt: an
exponentially growing delay, capped at a ceiling, and jittered — so that N clients (or N retries)
never fall into a synchronized, obviously-automated retry rhythm. Pure computation only; it does not
sleep.

## Signature

```python
def backoff_delay(attempt: int, base: float, cap: float,
                  rng: Callable[[], float] = random.random) -> float
```

`rng` is an injected zero-argument callable returning a float in `[0.0, 1.0)`, defaulting to
`random.random` — the same injection contract as `request_delay` (T-S1-12), and for the same reason:
it is what keeps the unit deterministic under test without patching `random` or `time` module state.

## Inputs

- `attempt: int` — **zero-based** retry index. `0` is the wait before the *first* retry (i.e. after
  the initial attempt already failed), `1` before the second, and so on. It is not a count of
  attempts made, and it is not one-based; getting this wrong doubles or halves every wait in the
  sequence.
- `base: float` — the first retry's pre-jitter delay in seconds. CLI `--retry-base`, default `5.0`.
- `cap: float` — the ceiling for the pre-jitter delay in seconds. CLI `--retry-cap`, default `300.0`.
- `rng: Callable[[], float]` — optional; defaults to `random.random`.

## Expected behavior

- Compute the pre-jitter delay `d = min(base * (2 ** attempt), cap)` — doubling per attempt, clamped
  to `cap`.
- Return that value **jittered by delegating to `request_delay(d, rng)`** (T-S1-12), yielding a
  result drawn uniformly from `[d, 2*d)`.
- **Reuse, do not reimplement.** The jitter shape is already specified, already green, and already
  has a documented rationale; this unit is `min`/`**` plus a call into it. Re-deriving `d + d*rng()`
  inline would fork the jitter policy into two places that must then be kept in agreement.
- Consequently the disabled/degenerate cases inherit `request_delay`'s contract for free: whenever
  `d <= 0`, the result is `0.0` and `rng` is never called — this unit does not need its own
  zero-check.
- The function is **pure**: no I/O, no sleeping, no side effects. Sleeping on the returned value is
  the **caller's** job (the orchestration loop's), not this unit's.

### Why `[d, 2*d)` and not `[0, d)`

The widely-cited "full jitter" formulation (`random_between(0, d)`) is deliberately **rejected**
here. It can return a near-zero wait for a request that just got rate-limited — precisely the
behavior that escalates a soft throttle into a hard block. This unit keeps `request_delay`'s shape
for the reason that spec already records: it *"guarantees the delay never drops below what the caller
requested, which matters more for rate-limit avoidance than symmetry."* The delay's growth comes from
the exponent; the jitter's job is only to break the rhythm, never to shorten the wait.

### The resulting sequence

With the defaults (`base = 5.0`, `cap = 300.0`, `--retries 5`, so `attempt` runs `0..4`):

| `attempt` | `d` | actual wait |
|---|---|---|
| 0 | 5 | 5–10s |
| 1 | 10 | 10–20s |
| 2 | 20 | 20–40s |
| 3 | 40 | 40–80s |
| 4 | 80 | 80–160s |

Total per rate-limited video: roughly 155–310 seconds. `cap` does not bind at these defaults (the
largest `d` is 80) — it exists as a safety rail for a caller who raises `--retries`, and it binds
from `attempt = 6` onward.

## Edge cases

- `attempt = 0` → `d = base` exactly (no growth yet). The `2 ** 0 == 1` identity is what makes the
  zero-based indexing work; a one-based caller would silently skip this rung.
- Large `attempt` (e.g. `20`) → `base * 2**20` is enormous but `min` clamps `d` to `cap`, so the
  result stays within `[cap, 2*cap)`. **No overflow, no unbounded wait** — this is the cap's whole
  purpose.
- `cap < base` → `d = cap` from `attempt = 0` onward; the sequence never grows. Degenerate but not an
  error, and not something this unit rejects. [ASSUMPTION]
- `base <= 0` → `d <= 0` → `0.0`, `rng` never called (inherited from `request_delay`).
- `cap <= 0` → `d <= 0` → `0.0`, `rng` never called (inherited).
- `attempt` negative → `2 ** -1 == 0.5`, so `d = base/2`, i.e. a *shorter* delay rather than an error.
  Not a caller this unit expects; behavior is defined here only so it is not a surprise. [ASSUMPTION]
- Successive calls with the **same** `attempt` and a **stateful** `rng` return **different** values —
  jitter, not a fixed offset per rung.
- Successive calls with the same `attempt` and a **fixed-return** `rng` return the **same** value —
  the unit holds no internal state.

## Acceptance scenarios (Given / When / Then)

- **Given** `attempt = 0`, `base = 5.0`, `cap = 300.0` and `rng` fixed to return `0.0`, **when**
  `backoff_delay(...)` runs, **then** it returns exactly `5.0` — the lower bound of the first rung.
- **Given** `attempt = 3`, `base = 5.0`, `cap = 300.0` and `rng` fixed to `0.0`, **when** it runs,
  **then** it returns exactly `40.0` (`5 * 2**3`) — the exponent, verified without waiting.
- **Given** `attempt` stepping `0, 1, 2, 3, 4` with `base = 5.0`, `cap = 300.0` and `rng` fixed to
  `0.0`, **when** each runs, **then** the results are exactly `5, 10, 20, 40, 80` — each rung doubles
  its predecessor.
- **Given** `attempt = 2`, `base = 5.0`, `cap = 300.0` and `rng` fixed to some `v` in `[0.0, 1.0)`,
  **when** it runs, **then** the result satisfies `20.0 <= result < 40.0`.
- **Given** `attempt = 20`, `base = 5.0` and `cap = 300.0`, **when** it runs with any `rng`, **then**
  the result satisfies `300.0 <= result < 600.0` — the cap binds and the wait stays bounded.
- **Given** `attempt = 6`, `base = 5.0` and `cap = 300.0` with `rng` fixed to `0.0`, **when** it runs,
  **then** it returns exactly `300.0` — `5 * 2**6 = 320` is clamped, the first rung at which the cap
  binds.
- **Given** `base = 0` and any `attempt`, **when** it runs with a call-counting fake `rng`, **then**
  it returns `0.0` and the fake `rng` was never invoked.
- **Given** `attempt = 1`, `base = 5.0`, `cap = 300.0` and no `rng` argument supplied, **when** it
  runs using the default `random.random`, **then** the result satisfies `10.0 <= result < 20.0`
  (checked as a range, not a fixed value, since the default rng is non-deterministic).
- **Given** `attempt = 2`, **when** `backoff_delay` is called twice with an `rng` returning two
  different values on successive calls, **then** the two returned delays differ.

## Assumptions

- [ASSUMPTION] `attempt` is zero-based. The alternative (one-based) would make the first retry wait
  `2*base` and silently drop the `base` rung from the sequence.
- [ASSUMPTION] The multiplier is fixed at `2` (doubling) rather than being a parameter. No caller
  needs to tune it, and a `--retry-factor` flag would be a knob with no use case; `base` and `cap`
  already span the useful range of policies.
- [ASSUMPTION] `cap` clamps the **pre-jitter** value `d`, so the maximum possible returned wait is
  just under `2 * cap`, not `cap`. Documented rather than "fixed" because clamping post-jitter would
  re-introduce the flat, un-jittered ceiling that the jitter exists to avoid — every request at the
  ceiling would wait exactly `cap` and re-synchronize.
- [ASSUMPTION] Degenerate inputs (`cap < base`, negative `attempt`) compute rather than raise,
  consistent with this codebase's other non-raising helpers (`request_delay` T-S1-12, `fetch_metadata`
  T-S1-11).
- [ASSUMPTION] This unit does not decide **how many** retries happen, **which** failures are worth
  retrying (that is `classify_failure`, T-S1-16), or **when** to stop — only how long rung `attempt`
  waits.

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own (it touches no artifact or manifest field). It is
consumed by the `main()` orchestration loop and the retry wrappers around the network calls, driven by
the CLI flags `--retries` (how many rungs), `--retry-base` (`base`) and `--retry-cap` (`cap`).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether the defaults (`base = 5.0`, `cap = 300.0`, 5 retries → ~2.5–5 minutes
  per rate-limited video) are actually sufficient to avoid a YouTube IP block. They are a judgement
  call informed by the stated goal ("long enough to never get banned") and by the fact that YouTube's
  IP-level throttles are observed to last minutes-to-hours; no external requirement or measurement
  pins these numbers. They are CLI-tunable precisely because the right values are not knowable up
  front.
- [NEEDS CLARIFICATION] Whether "decorrelated jitter" (seeding each rung from the *previous actual*
  wait rather than from `attempt`) would pace better under contention. It would make the unit
  stateful — it needs the prior delay — which conflicts with the pure/injected-`rng` shape the rest
  of this tier follows. Not adopted; recorded so the omission reads as a decision.
