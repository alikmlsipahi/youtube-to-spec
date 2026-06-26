# Spec — `build_manifest` (T-S1-09)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #6 `write_manifest`; §`_manifest.json` shape; catalog row T-S1-09; capabilities "Graceful
> degradation" and "Relational integrity" — failed videos listed with status+reason, never silently
> dropped; manifest preserves playlist→ordered-member relations). **No test code, no golden output tables
> here.**

## One-line purpose

Assemble the in-memory `_manifest.json` object for one collection — pairing the collection descriptor
with an **order-preserving** member list (each member carrying its status and, on failure, a reason) and
a computed `summary{}` of counts — so that every processed video, succeeded or failed, is recorded with
its relationship to the collection.

## Signature

```python
def build_manifest(collection: dict, members: list[dict]) -> dict
```

Pure and deterministic; no I/O, no network. `write_manifest` (the I/O sibling in §Functions #6) is the
caller that serializes this dict to `_manifest.json`; only the pure assembly is this unit.

## Inputs

- `collection: dict` — the collection descriptor, already shaped with the keys
  `type, id, title, uploader, source_url, hidden_unavailable_count`. Placed under the manifest's
  `collection` key. (For a `_singles/` run with no real playlist, the caller supplies an equivalent
  singles descriptor; that shaping is the caller's concern, not this unit's.)
- `members: list[dict]` — the **ordered** per-video outcome records, one per attempted video, in the
  order they should appear in the manifest (playlist position order). Each record carries:
  - `position: int` — 1-based position within the collection.
  - `video_id: str`.
  - `title: str` — best-known title (may be a thin/flat-playlist title for failures).
  - `status: str` — one of `"ok" | "metadata_failed" | "skipped_unavailable"`.
  - `reason: str | None` — failure reason; `None`/absent for `ok`.
  - `files: dict | None` — `{ "json": ..., "md": ... }` when artifacts were written; otherwise `None`.
  - `transcript: dict | None` — `{ "available", "language", "type" }` describing the selected track, or
    `None`/`{available: false, ...}` when there is no transcript.

## Expected behavior

Return a dict with exactly three top-level keys: `collection`, `members`, `summary`.

- **`collection`** — the passed-in `collection` descriptor, carried through under the `collection` key.
- **`members`** — one entry per input record, **in the same order** (order is the preserved
  playlist→member relationship). Each emitted member entry carries these keys:
  `position, video_id, title, status, reason, files, transcript`, where:
  - `position, video_id, title, status, transcript` pass through from the input record;
  - `reason` passes through (`None` for `ok`);
  - **`files` is forced to `null` whenever `status != "ok"`** — a failed or skipped video must not claim
    artifact files even if a stale value was provided; for `status == "ok"`, `files` passes through.
- **`summary`** — counts derived from the member list:
  - `total` = number of members.
  - `ok` = members with `status == "ok"`.
  - `failed` = members with `status != "ok"` (i.e. `metadata_failed` + `skipped_unavailable`).
  - `no_transcript` = members that **succeeded** (`status == "ok"`) but whose transcript is unavailable
    (`transcript` is `None` or `transcript["available"]` is not `True`).

Failed/skipped members are **always listed** (with their `status` and `reason`); they are never dropped.
Member order is never re-sorted.

## Edge cases

- **All members ok:** `failed == 0`, `no_transcript` counts only ok-without-transcript members.
- **All members failed:** `ok == 0`, `failed == total`, `no_transcript == 0` (no ok members to count).
- **Empty member list:** `members == []`, `summary == {total:0, ok:0, failed:0, no_transcript:0}`.
- **Failed member with a non-null `files` provided:** output `files` is forced to `null`.
- **Ok member with an unavailable transcript:** counted in `no_transcript`; its `files` is preserved.
- **`reason` present on an ok member:** passed through as-is (not cleared); only `files` is normalized.
- **Order:** the manifest's `members` order exactly equals the input order regardless of status mix.

## Acceptance scenarios (Given / When / Then)

- **Given** a collection and four members in positions 1..4 — two `ok` (one with an available transcript,
  one without), one `metadata_failed`, one `skipped_unavailable` — **when** `build_manifest` runs,
  **then** `members` lists all four in positions 1..4, the two non-ok members have `files == null` and a
  non-null `reason`, and `summary == {total:4, ok:2, failed:2, no_transcript:1}`.
- **Given** a failed member whose input record carries a non-null `files` value, **when** built, **then**
  that member's `files` in the manifest is `null`.
- **Given** an empty member list, **when** built, **then** `members` is `[]` and every summary count is
  `0`.
- **Given** the `collection` descriptor, **when** built, **then** it appears verbatim under the
  manifest's `collection` key (including `hidden_unavailable_count`).

## Assumptions

- [ASSUMPTION] The function takes `(collection, members)`; the plan names the manifest shape but not the
  builder's exact signature.
- [ASSUMPTION] Emitted member key set is `position, video_id, title, status, reason, files, transcript`.
  The plan lists `position, video_id, title, status, files, transcript`; `reason` is added because the
  catalog row requires failed members to "carry status+reason".
- [ASSUMPTION] `no_transcript` counts only `ok` members lacking a transcript (failed videos are already
  counted under `failed`, so they are excluded to avoid double-counting). See NEEDS CLARIFICATION.
- [ASSUMPTION] `failed` aggregates both `metadata_failed` and `skipped_unavailable` (any non-`ok` status).
- [ASSUMPTION] The `collection` descriptor arrives pre-shaped; this unit does not re-derive or re-key it.

## Key entities (canonical schema excerpt)

```jsonc
// _manifest.json
{
  "collection": { "type","id","title","uploader","source_url","hidden_unavailable_count" },
  "members": [
    { "position":1, "video_id":"…", "title":"…",
      "status":"ok|metadata_failed|skipped_unavailable",
      "reason": null,                  // reason string when failed
      "files": { "json":"…", "md":"…" } | null,   // null when status != "ok"
      "transcript": { "available":true, "language":"tr", "type":"auto" } | null }
  ],
  "summary": { "total":0, "ok":0, "failed":0, "no_transcript":0 }
}
```

This is the relational backbone: it preserves the playlist→ordered-member relationship and records every
video's fate, satisfying the brief's relational-integrity and graceful-degradation requirements.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] `no_transcript` semantics: this spec scopes it to **ok-but-no-transcript** members
  so the four summary buckets stay disjoint (`ok` minus `no_transcript` = ok-with-transcript; `failed`
  separate). If the intended meaning is "every member lacking a transcript" (including failures), the
  count and one fixture would change — flagged for human confirmation at the acceptance gate.
- [NEEDS CLARIFICATION] Whether `write_manifest` (the I/O wrapper) also re-derives `position` from list
  order or trusts the supplied `position` is out of scope here; `build_manifest` preserves the supplied
  `position` and the supplied order.
