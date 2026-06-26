# Spec — `format_timestamp` (T-S1-02)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Reuse, §Functions; catalog row T-S1-02). **No test code, no golden output tables here.**

## One-line purpose

Render a number of seconds as a human-readable clock string, using `MM:SS` for durations under one hour
and `HH:MM:SS` once the duration reaches one hour.

## Signature

```python
def format_timestamp(seconds: float) -> str
```

Reuse mandate (plan §Reuse, line 83): **copy verbatim** from
`.claude/skills/youtube-transcript/scripts/get_transcript.py` lines 32–39 (it already does MM:SS /
HH:MM:SS). The behavior below is exactly that verbatim copy.

## Inputs

- `seconds: float` — a non-negative elapsed time in seconds. In practice this is a transcript segment
  `start` (a float like `3.2`) or a chapter offset.

## Expected behavior

1. Split `seconds` into whole hours, whole minutes (0–59), and whole seconds (0–59) using integer/floor
   arithmetic:
   - hours = `floor(seconds / 3600)`
   - minutes = `floor((seconds mod 3600) / 60)`
   - secs = `floor(seconds mod 60)`
2. If hours > 0, return `HH:MM:SS` with each field zero-padded to two digits.
3. Otherwise return `MM:SS` with each field zero-padded to two digits.
4. The fractional part of `seconds` is **discarded** (floored), never rounded.

The function is pure and deterministic; no I/O.

## Edge cases

- `0` → minutes/seconds both zero, hours zero → two-field `MM:SS` output (`00:00`).
- A fractional value just under a whole second floors **down** (e.g. `5.9` s → `00:05`, not `00:06`).
- Exactly one hour (`3600`) is the boundary that switches the format from two fields to three.
- Just under one hour (`3599`) stays in the two-field `MM:SS` form.
- Large values (e.g. tens of thousands of seconds) keep producing a valid three-field string with a
  two-or-more-digit hour field; hours are **not** capped or wrapped at 24.
- Each of minutes and seconds is always in the range 0–59 in the output.

## Acceptance scenarios (Given / When / Then)

- **Given** zero seconds, **when** called, **then** it returns a two-field string with all zeros.
- **Given** a sub-hour duration, **when** called, **then** it returns a two-field `MM:SS` string.
- **Given** a duration with a fractional remainder, **when** called, **then** the seconds field is the
  floored whole second.
- **Given** a duration of exactly one hour or more, **when** called, **then** it returns a three-field
  `HH:MM:SS` string.
- **Given** a duration just below one hour, **when** called, **then** the output is still two-field.

## Assumptions

- [ASSUMPTION] Inputs are non-negative; negative durations are out of scope (the reuse source does not
  guard against them and transcript starts are always ≥ 0).
- [ASSUMPTION] Two-digit zero-padding of each field matches the reuse source's `:02d` formatting; the hour
  field may exceed two digits for very long videos.

## Key entities (canonical schema excerpt)

This formatter produces the `[MM:SS]` / `[HH:MM:SS]` prefixes in the Markdown transcript view
(`render_markdown`, T-S1-08) derived from `transcript.segments[].start`
(`IMPLEMENTATION_PLAN_v2.md` §Canonical per-video JSON).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] None — behavior is fully pinned by the verbatim-copy mandate.
