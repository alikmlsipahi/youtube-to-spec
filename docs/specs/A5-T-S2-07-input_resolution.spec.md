# Spec — `resolve_inputs` / `load_artifact` (input resolution) (T-S2-07)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 Input — "path to a `<video_id>.json` artifact, **or** a collection folder → iterate
> `_manifest.json` members with `status: ok`. Coupling is the JSON schema (`schema_version`) only;
> defensive reads."; §Skill 1 `_manifest.json` shape — `members[]` with `position`, `video_id`,
> `status = ok|metadata_failed|skipped_unavailable`, `files{json,md}|null`; catalog row T-S2-07
> "artifact path vs collection folder → iterates manifest members `status==ok`; defensive
> `schema_version` read"; §Risks — "Schema drift Skill 1 → Skill 2 → `schema_version` + defensive reads
> in Skill 2"). **No test code, no golden output tables here.**

## One-line purpose

Given a single path, decide whether it points at one Skill 1 artifact or at a collection folder, and
return the **ordered list of artifact JSON paths** to process — iterating a collection's `_manifest.json`
and keeping only members that succeeded (`status == "ok"`) and actually have a JSON file — plus a
defensive `load_artifact` that reads one artifact without crashing on schema drift.

## Signatures

```python
def resolve_inputs(path) -> list[pathlib.Path]
def load_artifact(path) -> dict
```

Both touch the filesystem (read-only) but never the network. `resolve_inputs` selects *which* artifacts
to process; `load_artifact` reads *one* artifact JSON defensively.

## Inputs

- `path` — a filesystem path (str or `Path`) that is **either**:
  - a **file** — a single `<video_id>.json` artifact, or
  - a **directory** — a collection folder containing a `_manifest.json` (and the member artifacts).
- For `load_artifact`, `path` is a single `<video_id>.json` artifact file.

## Expected behavior — `resolve_inputs`

1. **Single artifact file:** when `path` is an existing file, return a one-element list containing that
   path. (No manifest is consulted.)
2. **Collection folder:** when `path` is an existing directory, read `<dir>/_manifest.json`, walk its
   `members[]` **in listed order**, and for each member keep it **iff** `status == "ok"` **and** the
   member has a usable JSON file reference (`files.json` present and non-null). For each kept member,
   resolve its artifact path by joining the collection directory with `files.json` (a basename relative to
   the collection folder). Return those paths **in member order**.
3. Members with `status != "ok"` (`metadata_failed`, `skipped_unavailable`, anything else) are
   **excluded**. Members whose `files` is `null` or lacks a `json` entry are **defensively skipped** even
   if `status == "ok"` (no crash).
4. **No usable `_manifest.json` in a directory** (absent or unreadable/invalid) → raise a **clear** error
   naming the missing manifest.
5. **Non-existent `path`** → raise a clear error.
6. Read-only; never writes, never mutates inputs, never hits the network.

## Expected behavior — `load_artifact`

1. Read the JSON file at `path` (UTF-8) and return it as a `dict`.
2. **Defensive `schema_version` read:** a missing `schema_version`, or an unexpected/unknown value, does
   **not** raise — the artifact still loads (the field may be ignored or surfaced as a warning). Coupling
   to Skill 1 is tolerant, per the schema-drift mitigation.
3. A genuinely unreadable/non-JSON file raises a clear error (this is distinct from a merely
   missing/unknown `schema_version`).
4. Read-only; never mutates; never hits the network.

## Edge cases

- **Directory whose manifest lists `ok`, `metadata_failed`, `ok` (with one ok member's `files == null`),
  and `skipped_unavailable`** → only the ok members **with** a json file are returned, in order; failed,
  skipped, and files-less members are dropped.
- **Single artifact file path** → exactly that one path returned (no manifest needed).
- **Directory without `_manifest.json`** → clear error.
- **Path that does not exist** → clear error.
- **Manifest with an empty `members[]`** → empty list returned (no error).
- **`load_artifact` on an artifact missing `schema_version`** → returns the dict, no raise.
- **`load_artifact` on an artifact with an unknown `schema_version` (e.g. `"9.9"`)** → returns the dict,
  no raise.
- **`load_artifact` on a non-JSON / corrupt file** → clear error.

## Acceptance scenarios (Given / When / Then)

- **Given** a collection directory whose manifest has ok and non-ok members, **when** `resolve_inputs`
  runs, **then** it returns only the ok members' artifact paths, in listed order, and excludes
  `metadata_failed` and `skipped_unavailable` members.
- **Given** an ok member whose `files` is `null`, **when** `resolve_inputs` runs, **then** that member is
  skipped without error.
- **Given** a path to a single artifact `.json` file, **when** `resolve_inputs` runs, **then** it returns
  a one-element list with that path.
- **Given** a directory with no `_manifest.json`, **when** `resolve_inputs` runs, **then** it raises a
  clear error.
- **Given** a non-existent path, **when** `resolve_inputs` runs, **then** it raises a clear error.
- **Given** a valid artifact file, **when** `load_artifact` runs, **then** it returns a dict carrying the
  artifact's fields.
- **Given** an artifact file missing `schema_version`, **when** `load_artifact` runs, **then** it returns
  the dict without raising.
- **Given** an artifact file with an unknown `schema_version`, **when** `load_artifact` runs, **then** it
  returns the dict without raising.

## Assumptions

- [ASSUMPTION] The collection manifest filename is exactly **`_manifest.json`** and lives at the root of
  the collection directory (matches Skill 1's layout).
- [ASSUMPTION] `member.files.json` is a **basename relative to the collection directory** (Skill 1 writes
  `<video_id>.json` into the same folder), so the artifact path is `dir / files.json`. If an absolute path
  were stored, joining still resolves it.
- [ASSUMPTION] "Iterate members with `status: ok`" additionally requires a usable `files.json`; an ok
  member without one is defensively skipped rather than producing a missing-file crash.
- [ASSUMPTION] `resolve_inputs` returns **paths** (not loaded dicts); the engine loads each via
  `load_artifact`. This keeps selection and reading separable and the per-file defensive read in one
  place.
- [ASSUMPTION] Order is **manifest member order** (which Skill 1 keeps aligned with playlist position) —
  relational integrity requires the ordering be preserved.
- [ASSUMPTION] "Defensive `schema_version` read" means tolerating missing/unknown versions (load anyway);
  it does **not** mean silently accepting structurally corrupt JSON, which still raises.

## Key entities (canonical schema excerpts)

`_manifest.json` (Skill 1):

```jsonc
{
  "collection": { "type","id","title","uploader","source_url","hidden_unavailable_count" },
  "members": [
    { "position": 1, "video_id": "…", "title": "…",
      "status": "ok",                       // ok | metadata_failed | skipped_unavailable
      "files": { "json": "<video_id>.json", "md": "<video_id>.md" }, // null when failed/skipped
      "transcript": { "available": true, "language": "tr", "type": "auto" } }
  ],
  "summary": { "total","ok","failed","no_transcript" }
}
```

Per-video artifact (the thing `load_artifact` reads):

```jsonc
{ "schema_version": "1.0", "kind": "video_artifact", "video": { … }, "collection": { … } | null, "transcript": { … } }
```

`schema_version` is the **only** coupling between Skill 1 and Skill 2, and it is read defensively.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether an unknown `schema_version` should emit a visible warning (to stderr) or
  load silently. This spec requires "does not crash"; the warning channel is the implementer's choice and
  not asserted at the unit tier.
- [NEEDS CLARIFICATION] Whether a directory that *is* a collection but whose manifest references missing
  files on disk should drop those members or error. This spec treats `resolve_inputs` as returning paths
  (existence of the target file is checked when `load_artifact` reads it); confirm at the B-gate.
- [NEEDS CLARIFICATION] Whether `_singles/` (Skill 1's standalone folder, which has **no** manifest)
  should be accepted as a "collection" directory. Out of scope here — callers point at a specific artifact
  file for singles.
