# Spec — `validate_req_id` (T-S2-04)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 "Requirement ID scheme (locked) — `<MODULE>-<FEATURE>-<NNN>`"; catalog row T-S2-04
> "`^[A-Z0-9]{3,6}-[A-Z0-9-]{3,10}-\d{3}$`; video-local `NNN` from `001`; video_id **absent** from id").
> **No test code, no golden output tables here.**

## One-line purpose

Decide whether a requirement id is a well-formed `<MODULE>-<FEATURE>-<NNN>` code — matching the locked
pattern, with a real (non-zero) video-local sequence number — and, when a video id is supplied, that the
video id is **not** embedded inside the code.

## Signature

```python
def validate_req_id(req_id: str, video_id: str | None = None) -> bool
```

Pure and deterministic; no I/O. Returns `True` for a valid id and `False` otherwise (it does not raise on
malformed input — a non-matching string simply returns `False`).

## Inputs

- `req_id: str` — the candidate requirement id, e.g. `"REG-ADD-STU-001"`.
- `video_id: str | None` — optional source video id (e.g. `"EXAMPLE1234"`). When provided, the validator
  additionally enforces that the requirement id does **not** contain the video id as a substring (the
  scheme keeps `video_id` out of the code; it lives only in the `trace{}` / `source_video_id`).

## Expected behavior

Return `True` only if **all** of the following hold:

1. `req_id` fully matches the locked pattern `^[A-Z0-9]{3,6}-[A-Z0-9-]{3,10}-\d{3}$`, i.e.
   - **MODULE** — 3–6 characters of uppercase `A–Z` / digits `0–9`;
   - a single hyphen `-`;
   - **FEATURE** — 3–10 characters of uppercase `A–Z` / digits `0–9` / hyphen `-` (so `ACTION` or
     `ACTION-ENTITY` forms are allowed);
   - a single hyphen `-`;
   - **NNN** — exactly three digits.
2. The three-digit **NNN** is **not** `"000"` — sequence numbers are video-local and start at `001`, so
   `000` is rejected even though it satisfies `\d{3}`.
3. If `video_id` is provided (non-empty), `video_id` does **not** appear as a substring of `req_id`.

Otherwise return `False`.

## Edge cases

- **Lowercase letters anywhere** (`reg-add-001`) → invalid (pattern is uppercase-only).
- **MODULE too short / too long** (`RE-ADD-001`, `REGIST-ADD-001` where MODULE > 6) → invalid.
- **FEATURE too short / too long** (`REG-AD-001`, FEATURE > 10 chars) → invalid.
- **NNN not exactly three digits** (`REG-ADD-1`, `REG-ADD-0001`) → invalid.
- **NNN `000`** (`REG-ADD-000`) → invalid (video-local numbering starts at `001`).
- **FEATURE with internal hyphen** (`ATTND-BULK-DEL-007`) → valid (FEATURE = `BULK-DEL`).
- **Whitespace, leading/trailing spaces, surrounding text** → invalid (the match is full-string anchored).
- **Empty string** → invalid.
- **`video_id` embedded** (e.g. a code that happens to contain the supplied `video_id`) → invalid; absent
  `video_id` argument disables this check.
- **`video_id` provided but it cannot occur** (e.g. it contains lowercase, which the pattern already
  forbids) → the substring check simply never triggers; validity is decided by the pattern.

## Acceptance scenarios (Given / When / Then)

- **Given** `"REG-ADD-001"`, **when** validated, **then** `True`.
- **Given** `"EXAM-GRADE-012"` and `"ATTND-BULK-DEL-007"`, **when** validated, **then** `True` (FEATURE may
  contain an internal hyphen; MODULE up to 6 chars).
- **Given** `"reg-add-001"` (lowercase), **when** validated, **then** `False`.
- **Given** `"REG-ADD-1"` or `"REG-ADD-0001"`, **when** validated, **then** `False`.
- **Given** `"REG-ADD-000"`, **when** validated, **then** `False` (numbering starts at `001`).
- **Given** a too-short MODULE or FEATURE, **when** validated, **then** `False`.
- **Given** a valid-shaped code that contains the supplied `video_id` as a substring, **when** validated
  with that `video_id`, **then** `False`.
- **Given** the same code validated **without** a `video_id`, **when** validated, **then** the result is
  decided by the pattern alone (the embedding check is skipped).

## Assumptions

- [ASSUMPTION] Signature is `validate_req_id(req_id, video_id=None)`; the plan names the pattern and the
  "video_id absent from id" rule but not the function's exact arity — the optional `video_id` is how that
  rule is exercised.
- [ASSUMPTION] The validator **returns a bool** (does not raise) for malformed input; raising is reserved
  for genuinely exceptional inputs (e.g. a non-string), which are out of tested scope.
- [ASSUMPTION] `NNN == "000"` is treated as invalid to honor "video-local `NNN` from `001`", going one
  step stricter than the bare `\d{3}` pattern. (Catalog explicitly couples the pattern with "from `001`".)
- [ASSUMPTION] The match is full-string (anchored `^…$`), so any surrounding whitespace/text invalidates.
- [ASSUMPTION] The video-id embedding check is a plain case-sensitive substring test.

## Key entities (canonical schema excerpt)

```text
requirement.id          = <MODULE>-<FEATURE>-<NNN>     # e.g. REG-ADD-STU-001
  MODULE   : [A-Z0-9]{3,6}        (normalized from the collection/playlist title)
  FEATURE  : [A-Z0-9-]{3,10}      (ACTION or ACTION-ENTITY, from the video)
  NNN      : \d{3}, 001..999      (video-local; restarts per video)
requirement.source_video_id  ← carries the video id (NOT in the code)
requirement.trace            = { timestamp, segment_index }
```

Cross-video uniqueness is guaranteed by the composite key `(id, source_video_id)` (see T-S2-05), **not**
by embedding the video id in the code — which is exactly why the embedding check exists.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether `validate_req_id` should also enforce the video-local **sequence** (`001`,
  `002`, … contiguous, restarting per video). This spec validates a *single* id's well-formedness only;
  contiguity/ordering across a video's requirement set is a generation-time concern (related to T-S2-05's
  composite-key handling) and is not tested here.
- [NEEDS CLARIFICATION] Whether the substring embedding check should be case-insensitive or normalized
  (e.g. strip the video id's trailing `-c`). Plain case-sensitive containment is assumed.
