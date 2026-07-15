# Spec — `request_delay` (T-S1-12)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Risks & mitigations, `docs/IMPLEMENTATION_PLAN_v2.md:431-432` — "yt-dlp / YouTube fragility &
> rate-limiting over ~24 sequential per-video calls → subprocess isolation + per-video try/except +
> `--sleep-requests`"; §CLI, `docs/IMPLEMENTATION_PLAN_v2.md:178` — the existing `--sleep-requests N`
> flag). This unit adds **jitter** to that existing flag's delay so fixed-interval requests do not read
> as an obviously automated traffic pattern, while keeping the delay computation deterministic and
> testable. **No test code, no golden output tables here.**

## One-line purpose

Given a base delay in seconds, compute a **jittered** delay — a value randomized within
`[base, 2*base)` rather than the fixed `base` — so repeated calls do not sleep for an identical,
bot-like interval. Pure computation only; it does not sleep.

## Signature

```python
def request_delay(base: float, rng: Callable[[], float] = random.random) -> float
```

`rng` is an injected zero-argument callable returning a float in `[0.0, 1.0)`, defaulting to
`random.random`. Injecting it is what keeps this unit **pure and deterministic under test** — the
unit tier passes a fake `rng`, so no `time`/`random` module state needs patching and no test asserts
on real randomness.

## Inputs

- `base: float` — the caller's requested base delay in seconds. This is the existing
  `--sleep-requests N` CLI value (`args.sleep_requests`, default `0.0`, meaning "no delay"). May be
  `0`, negative (defensively — an unusual but not excluded caller value), or positive.
- `rng: Callable[[], float]` — zero-argument callable returning a float in `[0.0, 1.0)`. Optional;
  defaults to `random.random`.

## Expected behavior

- **Disabled case:** when `base <= 0`, return `0.0`. This is the single owner of "delay is off" —
  callers do not need their own separate zero-check before calling this function.
- **Enabled case:** when `base > 0`, return `base + base * rng()`, i.e. a value drawn uniformly from
  `[base, 2*base)` (inclusive lower bound, exclusive upper bound, matching `rng()`'s own
  `[0.0, 1.0)` range).
- `rng` is invoked **at most once** per call, and **only** when `base > 0`. When `base <= 0`, `rng` is
  never called.
- The function is **pure**: no I/O, no sleeping, no side effects. It only computes and returns a
  number; calling `time.sleep` (or any other wait) on the returned value is the **caller's**
  responsibility, not this unit's.

## Edge cases

- `base == 0` → `0.0`, `rng` not called.
- `base < 0` (negative) → `0.0`, `rng` not called. Treated the same as `base == 0`: any non-positive
  base means "no delay." [ASSUMPTION]
- `rng()` returns `0.0` (its lower bound) → result is exactly `base`.
- `rng()` returns a value close to (but, per its own contract, always below) `1.0` → result approaches
  but never reaches `2 * base`.
- Repeated calls with the **same** `base` and a **stateful** `rng` that returns different values on
  each call produce **different** results — jitter, not a fixed offset.
- Repeated calls with the same `base` and rng and a **fixed-return** `rng` (e.g. a stub always
  returning the same float) produce the **same** result — the function itself has no hidden internal
  state or side effects.

## Acceptance scenarios (Given / When / Then)

- **Given** `base = 0`, **when** `request_delay(base)` runs with a call-counting fake `rng`, **then**
  it returns `0.0` and the fake `rng` was never invoked.
- **Given** `base` a negative number, **when** `request_delay(base)` runs, **then** it returns `0.0`.
- **Given** `base = 2.0` and `rng` fixed to return `0.0`, **when** `request_delay(base, rng)` runs,
  **then** it returns exactly `2.0`.
- **Given** `base = 2.0` and `rng` fixed to return some value `v` in `[0.0, 1.0)`, **when**
  `request_delay(base, rng)` runs, **then** it returns `2.0 + 2.0 * v`, and for any such `v` the
  result satisfies `2.0 <= result < 4.0`.
- **Given** `base = 1.5` and no `rng` argument supplied, **when** `request_delay(base)` runs using the
  default `random.random`, **then** the result satisfies `1.5 <= result < 3.0` (checked as a range,
  not a fixed value, since the default rng is non-deterministic).
- **Given** `base = 3.0`, **when** `request_delay` is called twice with an `rng` that returns two
  different values on successive calls, **then** the two returned delays differ.

## Assumptions

- [ASSUMPTION] Negative `base` is treated identically to zero (`0.0`, no `rng` call) rather than
  raising. The plan does not describe negative delays as a caller possibility; this spec chooses the
  defensive, non-raising behavior consistent with this codebase's other graceful-degradation units
  (e.g. `fetch_metadata`, T-S1-11) rather than adding a new failure mode.
- [ASSUMPTION] The jitter formula is `base + base * rng()`, giving the range `[base, 2*base)`. The
  plan's risk section names `--sleep-requests` but does not specify a jitter formula; this spec adopts
  the "up to double the base, never less than the base" shape so a caller's requested minimum delay is
  always honored and the randomized ceiling is proportional to what they asked for.
- [ASSUMPTION] `rng`'s contract (`[0.0, 1.0)`) mirrors `random.random`'s documented range exactly, so
  the default argument and any test double are interchangeable at the boundary.
- [ASSUMPTION] This unit does not decide **when** in the orchestration loop it is called (e.g. before
  vs. after a request, whether skipped iterations pay it) — that wiring is the `main()` loop's
  responsibility (SK1-ORCH glue), not this pure helper's contract.

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own (it does not touch `video{}`, `manifest{}`, or
any artifact field). It is consumed by the `main()` orchestration loop as the delay computation behind
the existing `--sleep-requests N` CLI flag (`docs/IMPLEMENTATION_PLAN_v2.md:178`).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether the jitter range should be symmetric around `base` (e.g.
  `base ± base/2`) instead of `[base, 2*base)`. This spec picks `[base, 2*base)` because it guarantees
  the delay never drops below what the caller requested, which matters more for rate-limit avoidance
  than symmetry; not asserted against any external requirement.
