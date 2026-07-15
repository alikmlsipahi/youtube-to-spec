# Spec — `scan_existing` (T-S1-14)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #7, **[v2.1]** — "`scan_existing(out_dir)` indexes `{video_id: basename}` off disk so
> `--skip-existing` stays network-free"; §File layout; §CLI `--skip-existing`,
> `docs/IMPLEMENTATION_PLAN_v2.md:178`; the canonical per-video JSON shape; §Skill 2 Output **[v2.1]**),
> `skills/youtube-artifact-collector/SKILL.md` (§Output layout, flag table), and
> `docs/IMPLEMENTATION_PLAN-progress.md` (SK1-ORCH **[v2.1]** note). Signature + docstring only.
> **No test code, no golden output tables here.**

## One-line purpose

Index the artifacts already written under a directory as `{video_id: basename}`, reading the ids back off
disk so `--skip-existing` can decide what to skip **without making a single network request**.

## Signature

```python
def scan_existing(out_dir: Path) -> dict
```

## Inputs

- `out_dir: Path` — the directory holding previously written artifacts: either a collection folder
  (`data/<slug(title)>-<playlist_id>/`) or `data/_singles/` (plan §File layout). It may not exist yet.

## Expected behavior

Since **[v2.1]**, a basename is derived from the video's **title** (T-S1-13) and is therefore no longer
derivable from a video id alone. `--skip-existing` consequently resolves the other way round: rather than
predicting a filename from an id, this unit reads each artifact on disk and recovers the id **from its
contents**.

- **Return a mapping of `{video_id: basename}`** — one entry per already-written artifact, where the
  basename is the artifact's on-disk name **without its extension** (the `<basename>` that T-S1-13
  produced and that pairs `<basename>.json` with `<basename>.md`).
- The video id is read out of the artifact's canonical JSON, whose `video.id` field is authoritative. The
  filename is **not** parsed for the id — that is precisely what the **[v2.1]** naming change made
  impossible.
- **Local I/O only.** This is the unit that preserves `--skip-existing`'s guarantee of making **no**
  network request; a skipped video costs disk reads only. The progress record's re-verification frames
  this as the flag's defining property (a second pass skipping 19 members in ~0.09s, no network).
- **Exclusions.** Not every file under `out_dir` is a video artifact. Skip:
  - `_manifest.json` — the per-collection membership record, not a video artifact.
  - Skill 2's requirement documents (`<basename>.requirements.json` / `.requirements.md`), which are
    written alongside the source artifact in the same folder (plan §Skill 2 Output, **[v2.1]**).
- **Unreadable files are ignored**, never fatal: a truncated, malformed, or unparseable file — or one
  carrying no usable video id — is silently omitted from the index and does not raise. This matches the
  skill's graceful-degradation posture: a damaged leftover file degrades to "not yet collected" (so the
  video is re-fetched), which is the safe direction.
- The function is **read-only**: it creates, moves, and modifies nothing.

## Edge cases

- **`out_dir` does not exist** (a first-ever run, before anything is written) → an empty mapping, not an
  error. [ASSUMPTION]
- **`out_dir` exists but is empty** → an empty mapping.
- **A folder holding only `_manifest.json`** → an empty mapping (the manifest is excluded).
- **A folder holding artifacts plus Skill 2 requirement docs** → only the video artifacts are indexed;
  the requirement docs contribute no entries and must not be mistaken for artifacts of their own.
- **A malformed / unparseable artifact** → ignored, no exception, no entry.
- **An artifact with no recoverable video id** → ignored, no entry.
- **The `.md` companion of an indexed artifact** → contributes no separate entry; a video appears **once**
  in the mapping, keyed by its id. [ASSUMPTION]
- **Two artifacts carrying the same video id** → key collision; see NEEDS CLARIFICATION.

## Acceptance scenarios (Given / When / Then)

- **Given** a temporary directory that does not exist, **when** `scan_existing` runs on it, **then** it
  returns an empty mapping without raising.
- **Given** an empty temporary directory, **when** `scan_existing` runs, **then** it returns an empty
  mapping.
- **Given** a directory containing canonical artifacts for several videos, **when** `scan_existing` runs,
  **then** the mapping has one entry per video, keyed by each artifact's own `video.id`, valued by that
  artifact's extension-less filename.
- **Given** a directory whose artifacts were written with position-prefixed, title-derived names,
  **when** `scan_existing` runs, **then** the recovered basenames are exactly those on-disk names —
  demonstrating that the mapping is read from disk rather than reconstructed from the id.
- **Given** a directory containing a `_manifest.json` alongside video artifacts, **when** `scan_existing`
  runs, **then** the manifest contributes no entry.
- **Given** a directory containing `<basename>.requirements.json` and `<basename>.requirements.md`
  alongside their source artifact, **when** `scan_existing` runs, **then** only the source artifact is
  indexed.
- **Given** a directory containing a file that is not valid readable artifact content, **when**
  `scan_existing` runs, **then** that file is skipped, no exception escapes, and the other artifacts in
  the directory are still indexed.
- **Given** any directory whatsoever, **when** `scan_existing` runs, **then** no network call is made and
  the directory's contents are left unmodified.

This unit does disk I/O but no network I/O, so it is **fully testable against a temporary directory**:
write artifact files into a tmp dir, call the function, assert on the returned mapping. No HTTP stubbing,
no yt-dlp, and no `youtube-transcript-api` are involved.

## Assumptions

- [ASSUMPTION] A missing `out_dir` returns an empty mapping rather than raising. The plan does not name
  this case, but `--skip-existing` must be safe to pass on a first run, where the output directory cannot
  exist yet; raising would make the flag order-dependent.
- [ASSUMPTION] Only the `.json` artifacts are read for ids — the canonical JSON is the lossless artifact
  and is where `video.id` lives, whereas the `.md` is a rendered view. Each video therefore yields exactly
  one entry.
- [ASSUMPTION] "Basename" here means the same `<basename>` token that `artifact_basename` (T-S1-13)
  produces — the filename stem, carrying its position prefix for a collection member, and bearing neither
  directory nor extension.
- [ASSUMPTION] The scan covers `out_dir` itself and is not recursive: `out_dir` is a single collection
  folder or `_singles/`, and the plan's layout puts artifacts directly inside it with no nesting.
- [ASSUMPTION] "Unreadable" covers both I/O-level failure and content-level failure (invalid JSON, valid
  JSON of an unexpected shape, missing `video.id`); all degrade identically to "no entry", since the
  docstring's "unreadable files are ignored" is stated without qualification.
- [ASSUMPTION] This unit only **builds the index**; deciding what to do with a hit (skip the video, and
  reuse the existing basename in the manifest) belongs to the `main()` orchestration loop (SK1-ORCH glue),
  not to this function's contract.

## Key entities (canonical schema excerpt)

Keys come from the canonical per-video JSON's `video.id` (plan §Canonical per-video JSON). Values are the
`<basename>` of the `<basename>.json` / `<basename>.md` pair under `data/<slug(title)>-<playlist_id>/` or
`data/_singles/` (plan §File layout, **[v2.1]**), as produced by `artifact_basename` (T-S1-13). The
excluded `_manifest.json` is the per-collection record
(`collection{…}`, `members[]`, `summary{…}`); the excluded `<basename>.requirements.{json,md}` are Skill
2's consumption-layer outputs, which live in the same folder but are not video artifacts. This unit is
consumed by the `main()` loop behind the `--skip-existing` CLI flag
(`docs/IMPLEMENTATION_PLAN_v2.md:178`).

## NEEDS CLARIFICATION

The items below are genuinely unspecified by the documented policy. **They are deliberately left out
of this unit's tested contract**: writing a test for them would freeze whatever the code happens to do
today into a contract nobody has decided on. They are logged in `to-do.md` as documentation gaps to
settle on their own merits.

- [NEEDS CLARIFICATION] **Duplicate video ids in one directory** (e.g. a leftover artifact from a run
  before a title change, so the same id exists under two basenames). Whether last-wins, first-wins, or
  the stale file should be reported is unspecified; the mapping's shape (`dict`) can only hold one.
- [NEEDS CLARIFICATION] **Whether an entry requires both `.json` and `.md` to be present.** SKILL.md's
  flag table says `--skip-existing` skips videos "whose artifact files already exist" (plural), but
  `--format json|md|both` means a run may legitimately have produced only one of them. Whether a
  json-only artifact counts as "existing" — and whether a `--format md` run can be skip-resolved at all,
  given ids live in the JSON — is not described.
- [NEEDS CLARIFICATION] **How other unexpected files in `out_dir` are treated** — e.g. `.DS_Store`,
  editor swap files, or a nested subdirectory. Presumably they fall under "unreadable → ignored", but the
  exclusion list names only the manifest and requirement docs.
- [NEEDS CLARIFICATION] Whether `scan_existing` is expected to consult `_manifest.json` — which already
  records `members[].video_id` **and** `files{json,md}` — as a faster or authoritative index instead of
  reading each artifact. The docstring explicitly skips the manifest, but the plan does not say why the
  manifest is not the source, nor what should happen when the manifest and the on-disk artifacts disagree.
