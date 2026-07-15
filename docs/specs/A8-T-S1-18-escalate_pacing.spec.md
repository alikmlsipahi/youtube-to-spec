# Spec — `escalate_pacing` (T-S1-18)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Risks & mitigations, `docs/IMPLEMENTATION_PLAN_v2.md:447-454`) and the settled decision that a
> run which exhausts its retries on a rate-limited video **marks that video and continues** rather
> than aborting. This unit exists to make that decision safe. **No test code, no golden output tables
> here.**

## One-line purpose

Given the run's current inter-video pacing, compute the new, slower pacing to use for the rest of the
run after a rate-limit event — so that a run which keeps going in the face of throttling gets
progressively politer instead of continuing to knock at the same rate. Pure computation only.

## Why this unit exists

"Mark the video and continue" and "never get IP banned" are in tension. If YouTube has just refused a
video hard enough to burn through every retry, the service is actively throttling this client;
continuing to request the *next* video at the same 2–4 second pace is how a soft, recoverable
throttle becomes a hard IP block. The run was not aborted (a settled decision), so the only remaining
lever is the pace itself: each rate-limit event permanently backs the whole run off. The run still
finishes; it just stops insisting.

Where `backoff_delay` (T-S1-17) backs off **within** one video's retries and then forgets, this unit
backs off **across** videos and remembers — the escalated pacing persists for the remainder of the
run and never decays back down. [ASSUMPTION]

## Signature

```python
def escalate_pacing(current: float, ceiling: float, factor: float = 2.0) -> float
```

## Inputs

- `current: float` — the pacing in seconds currently in force between videos. On the first call this
  is the CLI `--sleep-requests` value (default `2.0`); on later calls it is this function's own
  previous return value, fed back in.
- `ceiling: float` — the maximum pacing this run will ever escalate to, in seconds. CLI
  `--max-pacing`, default `60.0`. Without it, a long run hitting many rate limits would escalate
  without bound and effectively hang.
- `factor: float` — the multiplier per event. Defaults to `2.0` (doubling).

## Expected behavior

- **Opt-out is absolute:** when `current <= 0`, return `0.0`. A user who passed `--sleep-requests 0`
  has explicitly asked for no pacing, and escalation must **never** override that — `0 * 2` is `0`
  anyway, but this is stated as a contract rather than left to arithmetic so it cannot be lost to a
  later refactor. `ceiling` and `factor` are irrelevant in this case.
- **Otherwise:** return `min(current * factor, ceiling)` — multiply, then clamp — with the whole
  result floored at `0.0`, so the function **never returns a negative number**. The floor matters
  because this unit's return value is fed straight back in as the next call's `current`, and a
  negative `current` would then hit the opt-out branch above and silently disable pacing for the rest
  of the run. A non-negative return keeps the two rules from contradicting each other.
- The escalation is **monotonic**: for any positive `current` and `factor >= 1`, the result is never
  smaller than `current`. This unit has no way to speed a run back up; there is no de-escalation path
  and that is deliberate.
- The function is **pure**: no I/O, no sleeping, no side effects, no hidden state. It does not know
  how many rate-limit events have occurred — the caller holds that state by feeding the result back
  in as the next `current`.

### The resulting progression

With the defaults (`--sleep-requests 2.0`, `--max-pacing 60.0`, `factor 2.0`), successive rate-limit
events move the run's pacing:

`2 → 4 → 8 → 16 → 32 → 60 → 60 → 60 …`

(The sixth event clamps: `32 * 2 = 64`, above the `60.0` ceiling.) Note the pacing is itself passed
through `request_delay` (T-S1-12) by the caller, so the actual waits are jittered — a pacing of `32`
means a 32–64 second gap.

## Edge cases

- `current = 0` → `0.0` (explicit opt-out; see above).
- `current` negative → `0.0`. Treated identically to zero, consistent with `request_delay`'s
  "any non-positive base means no delay" rule. [ASSUMPTION]
- `current` already at `ceiling` → returns `ceiling` unchanged; further events are idempotent. A run
  that has bottomed out stays bottomed out rather than creeping past the ceiling.
- `current * factor` slightly below `ceiling` → returned unclamped; the ceiling binds only when
  actually exceeded.
- `current > ceiling` (e.g. the user passed `--sleep-requests 90 --max-pacing 60`) → returns
  `ceiling`, i.e. the pacing is **lowered**. This is the one case where the monotonic guarantee does
  not hold, and it is the correct reading of an explicit ceiling. [ASSUMPTION]
- `ceiling <= 0` with positive `current` → returns `0.0`. A caller who sets a non-positive ceiling has
  asked for no pacing, and this unit does not second-guess that — but it reports it as `0.0` rather
  than passing a negative ceiling straight through, because the return is fed back in as the next
  call's `current` and a negative `current` would trip the opt-out branch. `0.0` and a negative number
  mean the same thing to every consumer here; only `0.0` is safe to round-trip. [ASSUMPTION]
- `factor = 1.0` → pacing never grows; escalation is effectively disabled. Not an error.
- `factor < 1.0` → pacing *shrinks*. Degenerate and not an expected caller; defined here only so it
  is not a surprise. [ASSUMPTION]

## Acceptance scenarios (Given / When / Then)

- **Given** `current = 2.0` and `ceiling = 60.0`, **when** `escalate_pacing(current, ceiling)` runs
  with the default factor, **then** it returns `4.0`.
- **Given** a `current` fed back in repeatedly from `2.0` with `ceiling = 60.0`, **when**
  `escalate_pacing` runs six times in succession, **then** the values are `4, 8, 16, 32, 60, 60` —
  doubling until the ceiling binds, then holding.
- **Given** `current = 32.0` and `ceiling = 60.0`, **when** it runs, **then** it returns `60.0` —
  `64.0` is clamped.
- **Given** `current = 60.0` and `ceiling = 60.0`, **when** it runs, **then** it returns `60.0` —
  already at the ceiling, idempotent.
- **Given** `current = 0` and `ceiling = 60.0`, **when** it runs, **then** it returns `0.0` — the
  `--sleep-requests 0` opt-out survives escalation.
- **Given** `current` a negative number, **when** it runs, **then** it returns `0.0`.
- **Given** `current = 90.0` and `ceiling = 60.0`, **when** it runs, **then** it returns `60.0`.
- **Given** `current = 2.0`, `ceiling = 60.0` and `factor = 3.0`, **when** it runs, **then** it
  returns `6.0` — the factor is honored.
- **Given** the same `current` and `ceiling`, **when** `escalate_pacing` is called twice, **then**
  both calls return the same value — the unit holds no internal state.

## Assumptions

- [ASSUMPTION] Escalation is **permanent for the run** — there is no decay, no cooldown, and no path
  back to the original pacing after a stretch of successful videos. A run that has been throttled
  once is treated as being on a throttled network until it ends. The conservative reading is chosen
  because the cost of staying slow is a longer run, while the cost of speeding back up too early is
  the IP block this whole change exists to avoid.
- [ASSUMPTION] `current <= 0` short-circuits to `0.0` as an explicit contract rather than relying on
  `min(0 * factor, ceiling)` happening to be `0` — which it would only be while `ceiling >= 0`.
- [ASSUMPTION] The caller, not this unit, owns the pacing state and decides **what counts as** a
  rate-limit event worth escalating on. This unit is a pure arithmetic step in that decision, not the
  policy.
- [ASSUMPTION] `factor` is a defaulted parameter rather than a CLI flag. It is here so the unit is
  testable at a non-default value and so a future policy change has a seam; no CLI surface exposes it
  and none is planned.

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own (it touches no artifact or manifest field). It is
consumed by the `main()` orchestration loop, which holds the run's current pacing in a local variable,
passes it through `request_delay` (T-S1-12) before each network-hitting iteration, and replaces it
with this unit's return value each time a video ends in the `rate_limited` status. CLI surface:
`--sleep-requests` (the starting `current`) and `--max-pacing` (the `ceiling`).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether escalation should trigger on **every observed transient failure**
  (including ones a retry then survives) rather than only on a video that exhausts all its retries.
  The narrower trigger is specified because a single 429 that the first retry clears is weak evidence
  of a throttle, whereas burning five backed-off retries is strong evidence. Not asserted against any
  external requirement.
- [NEEDS CLARIFICATION] Whether the ceiling default of `60.0` is right. A 60-second pace over a
  24-video playlist adds ~24 minutes to a run that was already failing — tolerable for an unattended
  collect, possibly not for an interactive one. Tunable via `--max-pacing`; the default is a
  judgement call, not a measurement.
