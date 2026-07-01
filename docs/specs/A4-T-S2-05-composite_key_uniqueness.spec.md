# Spec — `dedupe_requirements` (composite-key uniqueness) (T-S2-05)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 — "Cross-video uniqueness is guaranteed by the **composite key `requirement_id` +
> `source_video_id`**, not by embedding the video id in the code"; §Risks "Module/feature code collisions
> across videos → mitigated by the composite key"; catalog row T-S2-05 "dedup on
> `(requirement_id, source_video_id)`; same req-id across two videos is **allowed**"). **No test code, no
> golden output tables here.**

## One-line purpose

De-duplicate a list of extracted requirements on the **composite key** `(id, source_video_id)` — removing
only true duplicates (same code *and* same source video) while **preserving** distinct entries, including
the legitimate case of the same requirement code appearing under two different videos.

## Signature

```python
def dedupe_requirements(requirements: list[dict]) -> list[dict]
```

Pure and deterministic; no I/O. Does not mutate the input list or its dicts.

## Inputs

- `requirements: list[dict]` — extracted requirement records, each carrying at least:
  - `id: str` — the `<MODULE>-<FEATURE>-<NNN>` requirement code (validated by T-S2-04).
  - `source_video_id: str` — the id of the video the requirement was extracted from.
  - (other fields such as `text`, `trace{}` may be present and are carried through untouched.)

## Expected behavior

Return a new list containing each requirement **the first time** its composite key
`(req["id"], req["source_video_id"])` is seen, **in original order**. Subsequent records whose composite
key was already seen are dropped.

- **First occurrence wins**: when two records share a composite key, the earlier one is kept verbatim and
  the later one(s) discarded; the kept record's other fields are not merged or altered.
- **Order preserved**: surviving records appear in the same relative order as in the input.
- **Distinctness rule**: two records are duplicates **only if both** `id` **and** `source_video_id` match.
  Differing on either field makes them distinct and both are kept.

Consequences that must hold:

- The **same `id` under two different `source_video_id`s** → both kept (this is explicitly allowed; module
  /feature codes are video-local and collisions across videos are expected).
- **Different `id`s under the same `source_video_id`** → both kept.
- **Identical `(id, source_video_id)` appearing twice** → collapsed to one.

## Edge cases

- **Empty input** → empty list.
- **No duplicates** → list returned with the same elements in the same order (logically unchanged).
- **All identical composite keys** → collapses to a single record (the first).
- **Same code, two videos** → both retained (the headline allowed case).
- **Interleaved duplicates** (`A,B,A`) → second `A` (same composite key) dropped, result `A,B`.
- **Records differing only in non-key fields but sharing the composite key** (e.g. different `text`) →
  treated as duplicates; the **first** is kept and the second dropped (no merging).
- **Missing key fields** → out of tested scope; inputs are assumed to carry both `id` and
  `source_video_id` (see NEEDS CLARIFICATION).

## Acceptance scenarios (Given / When / Then)

- **Given** two records with the same `id` and the same `source_video_id`, **when** deduped, **then** only
  the first remains.
- **Given** two records with the same `id` but different `source_video_id`, **when** deduped, **then**
  both remain.
- **Given** two records with different `id`s but the same `source_video_id`, **when** deduped, **then**
  both remain.
- **Given** a list with no duplicate composite keys, **when** deduped, **then** the output equals the
  input in content and order.
- **Given** an empty list, **when** deduped, **then** the output is empty.
- **Given** duplicates interleaved with distinct records, **when** deduped, **then** order is preserved
  and only later duplicates are removed (first occurrence kept).

## Assumptions

- [ASSUMPTION] The requirement-id field is named `id` (matching the plan's output description "each
  requirement: `id`=`<MODULE>-<FEATURE>-<NNN>`"). The §ID-scheme prose calls the concept `requirement_id`;
  these refer to the same value. See NEEDS CLARIFICATION if the JSON key is actually `requirement_id`.
- [ASSUMPTION] De-duplication keeps the **first** occurrence and never merges fields from later
  duplicates.
- [ASSUMPTION] The function returns a new list and does not mutate inputs.
- [ASSUMPTION] Both key fields are present on every record; absence is out of scope.
- [ASSUMPTION] Composite-key comparison is exact/case-sensitive on both fields.

## Key entities (canonical schema excerpt)

```jsonc
// one requirement record
{
  "id": "REG-ADD-001",            // <MODULE>-<FEATURE>-<NNN>; video-local NNN
  "text": "…",
  "source_video_id": "EXAMPLE1234",
  "trace": { "timestamp": "01:15", "segment_index": 12 }
}
```

Composite key = `(id, source_video_id)`. This is the mechanism that lets video-local codes coexist across
videos without a global renumbering pass (which the plan defers to a later consolidation stage).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] The exact JSON key for the requirement code — `id` (per the output description,
  assumed here) vs. `requirement_id` (per the ID-scheme prose). If the engine emits `requirement_id`, the
  composite key and one fixture change accordingly.
- [NEEDS CLARIFICATION] Whether dedup should additionally **warn/report** on collapsed duplicates (for
  observability) or silently drop them. This spec specifies silent first-wins removal; reporting is a
  possible enhancement to confirm at the acceptance gate.
