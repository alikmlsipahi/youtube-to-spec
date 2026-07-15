# Spec — `normalize_trace_indexes` (T-S2-09)

> **Descriptive spec — read this caveat before trusting the document.** Unlike every other spec in this
> directory, this one is **not** a blind contract written ahead of an implementation. The function, and
> its unit tests (`skills/spec-distiller/tests/test_trace_index_validation.py`), both already existed;
> what was missing was the *record* — no catalog id, no spec, so the unit was invisible to
> `docs/IMPLEMENTATION_PLAN_v2.md`'s catalog and to `docs/IMPLEMENTATION_PLAN-progress.md`. This file
> closes that gap by writing down the contract the function's docstring already states. It therefore
> **cannot** serve the usual purpose of letting a test disagree with the code — the tests came first.
> Treat it as documentation of an existing agreement, not as an independent check on it. Recorded
> 2026-07-15. Source: the function's own signature + docstring, and
> `docs/IMPLEMENTATION_PLAN_v2.md` (§Skill 2 — the `trace{timestamp, segment_index}` requirement;
> §Grounding "segment addressability is load-bearing", `03_ROADMAP.md:53`).
> **No test code, no golden output tables here.**

## One-line purpose

Guarantee that every requirement's `trace.segment_index` addresses a **real** transcript segment —
repairing the common LLM error of writing a segment's *start second* where its *index* belongs, but
only when the repair is unambiguous, and failing loudly rather than silently mis-addressing.

## Signature

```python
def normalize_trace_indexes(doc: dict, artifact: dict | None) -> dict
```

Mutates `doc` **in place** and returns it. Pure computation over two dicts — no I/O, no network.

## Inputs

- `doc: dict` — the parsed requirement document: `modules[] → features[] → requirements[]`, each
  requirement carrying `trace{timestamp, segment_index}`.
- `artifact: dict | None` — the source Skill 1 artifact, whose `transcript.segments[]` supply the real
  `index` and `start` values to validate against.

## Expected behavior

Applied per requirement trace:

| Case | Outcome |
|---|---|
| `segment_index` already equals a real segment index | kept as-is |
| `segment_index` is `None`/absent | left as-is — traces are optional |
| `segment_index` matches no real index | treated as a **start-second** and remapped to the segment starting within that whole second — **only when exactly one** segment does |
| the start-second is unresolvable, or **ambiguous** (several segments start in that second) | raises `ValueError` |
| `segment_index` is not an integer | raises `ValueError` |

- **A missing or empty transcript disables validation entirely** — there is nothing to resolve
  against, so `doc` is returned untouched rather than every trace being rejected.
- **Failing loudly is the point.** A trace is the promise that a requirement can be walked back to the
  moment it came from (`03_ROADMAP.md:53` makes `segments[].index` the stable address that future
  artifact types will reference). A silently wrong index breaks that promise invisibly, which is worse
  than an error — hence `ValueError` over a best guess.

## Edge cases

- Ambiguity is resolved **only** by uniqueness — two segments starting in the same whole second make
  the value unresolvable, not a coin flip.
- The repair is one-directional: a real index is never reinterpreted as a start-second.
- `doc` is mutated in place *and* returned, so callers may use either style.

## Acceptance scenarios (Given / When / Then)

- **Given** a trace whose `segment_index` is already a real segment index, **when**
  `normalize_trace_indexes` runs, **then** it is unchanged.
- **Given** a trace whose `segment_index` matches no index but equals the whole-second start of exactly
  one segment, **when** it runs, **then** the value is replaced by that segment's index.
- **Given** a trace whose start-second matches several segments, **when** it runs, **then** it raises
  `ValueError` rather than picking one.
- **Given** a trace with no `segment_index`, **when** it runs, **then** it is left alone.
- **Given** an artifact with no transcript or no segments, **when** it runs, **then** `doc` is returned
  unchanged and nothing raises.
- **Given** a non-integer `segment_index`, **when** it runs, **then** it raises `ValueError`.

## Assumptions

- [ASSUMPTION] The rules above are transcribed from the docstring, which is the only written statement
  of this contract; no separate plan section specifies the start-second repair. If the docstring and
  the code ever disagreed, this spec would inherit the docstring's version — a weakness inherent to a
  descriptive spec, and the reason blind specs are written first everywhere else.

## Key entities (canonical schema excerpt)

```jsonc
// requirement → trace{}
"trace": { "timestamp": "MM:SS", "segment_index": 42 }
// Skill 1 artifact → transcript.segments[]
{ "index": 42, "start": 104.84, "duration": 3.2, "end": 108.04, "text": "…" }
```

`segment_index` addresses `transcript.segments[].index` — the stable address the roadmap requires for
future artifact types (screenshots, OCR) to reference a moment. `start` is what an LLM tends to emit
by mistake, and what the unambiguous-remap rule exists to recover from.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether the start-second remap should widen its tolerance (e.g. nearest
  segment within ±1s) when no segment starts in the exact second. Currently unresolvable → `ValueError`.
  Untested and undecided; a widening would trade loudness for recall and should be a deliberate call.
- [NEEDS CLARIFICATION] Whether `timestamp` and `segment_index` are cross-checked against each other.
  This unit validates the index against the transcript; nothing verifies the human-readable
  `timestamp` agrees with it.
