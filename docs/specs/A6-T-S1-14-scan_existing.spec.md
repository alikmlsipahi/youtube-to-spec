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
- **Two artifacts carrying the same video id** → one entry, chosen **deterministically**: the scan is
  ordered by filename, so the last basename in sorted order wins. The same directory always yields the
  same index. [RESOLVED 2026-07-15 — see NEEDS CLARIFICATION for the accepted wart]
- **A folder holding only `.md` files** (a `--format md` run) → an **empty mapping**. Ids live in the
  canonical JSON; a rendered view carries none. `--skip-existing` therefore cannot resolve a md-only
  collection and will re-fetch it — a documented limitation, recorded in SKILL.md's flag table.
  [RESOLVED 2026-07-15]
- **Stray files** — `.DS_Store`, editor swap files, a nested subdirectory → cannot interfere: only
  `*.json` is globbed, so they never match. A *directory* named `*.json` matches the glob but fails to
  read, falling under "unreadable → ignored". [RESOLVED 2026-07-15]

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

**All four items below were settled on 2026-07-15** and folded into the behavior above. They are kept
here with their resolutions because the reasoning is the useful part — each was a place the docs had
never decided anything, and the decision is now the contract rather than an accident of the code.

- [RESOLVED 2026-07-15] **Duplicate video ids in one directory** (a leftover artifact from a run before
  a title change, so the same id exists under two basenames). **Decision: the scan is ordered, so the
  outcome is deterministic — the last basename in sorted order wins.** A `dict` can hold one entry per
  id, and determinism is what matters: the same directory always yields the same index. Either basename
  addresses the same video, and `--skip-existing` skips it either way.
  **Known wart, accepted deliberately:** sorted order is alphabetical, not chronological, so the *stale*
  file can win and the manifest can then name it. This is rare (it needs a title change plus a leftover)
  and self-inflicted (deleting the stale file fixes it). Resolving by modification time would fix it
  properly and is logged in `to-do.md` as possible future work — not done here, because it is a code
  change dressed up as a clarification.
- [RESOLVED 2026-07-15] **Whether an entry requires both `.json` and `.md`.** **Decision: only the
  `.json` matters, and a `--format md` run cannot be skip-resolved at all.** Ids live in the canonical
  JSON; the `.md` is a rendered view carrying no id. So a json-only artifact counts as existing, and a
  md-only collection indexes as empty — meaning `--skip-existing` will re-fetch everything. That is a
  **documented limitation**, not a bug to paper over: recovering an id from a rendered Markdown view
  would mean parsing the view, which is exactly the coupling `[v2.1]` removed. SKILL.md's flag table
  now says so.
- [RESOLVED 2026-07-15] **Unexpected files in `out_dir`** (`.DS_Store`, editor swap files, a nested
  subdirectory). **Decision: they cannot interfere.** The scan globs `*.json` only, so anything else —
  including `.md` companions and `.DS_Store` — never even matches. A directory that happens to be named
  `*.json` fails to read and falls under the existing "unreadable → ignored" rule. No new exclusion is
  needed; the glob is the filter.
- [RESOLVED 2026-07-15] Whether `scan_existing` is expected to consult `_manifest.json` — which already
  records `members[].video_id` **and** `files{json,md}` — as a faster or authoritative index instead of
  reading each artifact. **Decision: the manifest is not, and cannot be, the index.** Two reasons, now
  recorded: (1) `_singles/` has **no manifest at all**, so a manifest-based index would only work for
  collections — this unit must serve both; (2) the manifest records what a *previous run intended*,
  while `--skip-existing` must answer what is *actually on disk now*. A file deleted by hand after the
  run still appears in the manifest, and trusting it would skip a video whose artifact no longer
  exists. Disk is the ground truth, so a disagreement between manifest and disk is resolved in disk's
  favor by construction — this unit never reads the manifest, so it can never be misled by one.
