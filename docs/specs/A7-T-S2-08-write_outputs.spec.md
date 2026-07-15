# Spec — `write_outputs` (T-S2-08)

> Behavioral contract for the blind implementer. **Retrofitted coverage:** the code predates this
> spec and has never been executed by any test tier, so this contract is authored from the
> **documented policy plus the signature and docstring only** — the function body was not read, and
> it is the code that must answer to this spec, not the reverse. Source of truth:
> `skills/spec-distiller/SKILL.md` (§Claude-native engine step 6 — "write `<basename>.requirements.md`
> plus a mirrored `<basename>.requirements.json` alongside the source artifact… `<basename>` is the
> **source artifact's filename without its extension**… **Never rebuild the name from the video id**";
> §Output; flag table `--out-dir NAME` / `--no-save` / `--print`),
> `docs/IMPLEMENTATION_PLAN_v2.md` (§Skill 2 Output **[v2.1]** — "written alongside the source artifact
> — same collection folder or `_singles/`; override with `--out-dir`… `<basename>` mirrors the source
> artifact's filename (Skill 1 owns naming; Skill 2 stays policy-agnostic)"; §Skill 2 CLI; §Save
> behavior — "Default save; also `--print` / no-save terminal mode"; §Skill 2 catalog table), and
> `docs/IMPLEMENTATION_PLAN-progress.md` (SK2-ORCH **[v2.1]** row; the §Orchestration preamble's
> `[2026-07-15]` note that "glue needs no unit test" is what let a naming-policy change land unguarded).
> **No test code, no golden output tables here.**

## One-line purpose

Persist one artifact's finished requirement document as the pair
`<basename>.requirements.json` + `<basename>.requirements.md` — where `<basename>` is **mirrored from
the source artifact's own filename and never reconstructed from the video id** — placing them
alongside the source artifact unless `out_dir` redirects them, or printing them instead of writing
when `no_save` is set.

## Signature

```python
def write_outputs(artifact_path, doc, markdown, out_dir, no_save)
```

Touches the filesystem (write) and stdout. Never the network. This is the last step of a per-artifact
run: the document is already produced and already rendered by the time it is called.

## Inputs

- `artifact_path` — the path of the **source** Skill 1 artifact `.json` this document was distilled
  from (the same path `resolve_inputs` (T-S2-07) returned). It is the **sole** source of the output
  basename and, by default, of the output directory.
- `doc` — the structured document: `summary`, `modules[] → features[] → requirements[]` (each with
  `id`, `text`, `source_video_id`, `trace{timestamp, segment_index}`), plus `assumptions` and
  `open_questions`. This is what the `.json` output carries.
- `markdown` — the already-rendered document text (rendered from `templates/requirement_doc.md`).
  This is what the `.md` output carries. This function **renders nothing**; it does not re-derive the
  markdown from `doc`, and the two outputs mirror each other because the caller made them mirror.
- `out_dir` — an **override** for the output directory. Absent/empty (the documented default,
  "alongside source") means: write into the directory that holds `artifact_path`.
- `no_save` — when set, **print instead of writing files** (`--no-save` / `--print`); no output file
  is created anywhere.

## Expected behavior

### 1. The naming rule (the load-bearing one)

`<basename>` is the **source artifact's filename with its extension removed** — nothing else. The two
outputs are `<basename>.requirements.json` and `<basename>.requirements.md`, and they always agree
with each other because they are built from the same `<basename>`.

The prohibition is explicit in both SKILL.md and the plan and is the point of this unit:

- The basename is **never** rebuilt from `video.id`, and **never** from `video.title`, the collection
  title, the requirement ids, or anything else inside `doc`. Skill 1 owns artifact-naming policy
  entirely; Skill 2 is policy-agnostic and only mirrors what it was handed.
- Consequently the outputs must carry a source artifact's position prefix, its title-derived slug, and
  any other Skill 1 naming decision **verbatim**, because they were copied rather than recomputed.
- Because `doc` is not consulted for the name, a `doc` whose `video`/`source_video_id` data bears no
  resemblance to the source filename must not perturb the output names at all. This is the sharp
  observable difference between mirroring and reconstructing, and it is what a
  `video.id`-based implementation fails.
- Mirroring is also what keeps the **claude** and **openai** engines emitting identical filenames from
  identical inputs — the engines only agree if neither invents a name.

### 2. Where the files land

- **Default (no `out_dir`)** — both files are written into the directory containing `artifact_path`:
  the member's collection folder, or `_singles/`, exactly as Skill 1 laid it out. Sitting the document
  next to its source is the documented behavior; the artifact is not moved, copied, or touched.
- **`out_dir` given** — both files are written into that directory instead, keeping the same
  `<basename>` (the override redirects the *location*, never the *name*).
- Both files are written for a save-mode call — the `.json` mirror is not optional, and Skill 2 has no
  format selector.

### 3. Print mode (`no_save`)

- **Nothing is written to disk** — not into the source's folder, not into `out_dir`, not anywhere. A
  print-mode call must leave the filesystem exactly as it found it; this is the whole point of a
  "terminal mode" and it is the guarantee a user relies on when pointing the tool at a folder they do
  not want mutated.
- The document is emitted to **stdout** instead, so the user sees the result they would otherwise have
  had to open a file to read.

### 4. Invariants

- **The source artifact is read-only.** It is never modified, renamed, or deleted; it is used for its
  path (and specifically its filename), not its contents.
- **No network I/O.** The OpenAI call happened earlier, upstream of this function.
- **Deterministic.** The same `artifact_path` yields the same two output paths on every run,
  independent of clock, cwd, or `doc` contents.

## Edge cases

- **A source artifact whose filename stem is unrelated to its `video.id`** (the normal case since
  **[v2.1]**: a position-prefixed, title-derived slug) → outputs named from the stem; the video id
  appears in **no** output filename.
- **A `doc` whose `source_video_id` contradicts the source filename** → output names are unchanged;
  `doc` has no vote in naming.
- **Two artifacts in one collection folder** → each yields its own `<basename>.requirements.*` pair; no
  collision, because each mirrors its own distinct source name.
- **A source filename containing dots beyond the extension** → only the final extension is dropped;
  the rest of the name survives into `<basename>` [ASSUMPTION].
- **A source filename carrying non-ASCII characters** → mirrored as-is; this function does not slugify,
  normalize, or otherwise sanitize a name that Skill 1 already decided.
- **`out_dir` pointing at a directory that does not exist yet** → see NEEDS CLARIFICATION.
- **Outputs that already exist from a previous run** → see NEEDS CLARIFICATION.
- **`no_save` set together with an `out_dir`** → nothing is written; `no_save` wins, since it is
  defined as "print instead of writing files" and there is no file to place [ASSUMPTION].

## Acceptance scenarios (Given / When / Then)

This unit does disk I/O and stdout I/O but **no network I/O**, so it is fully testable against a
**temporary directory**: place a source artifact in a tmp dir, call the function with a document and a
rendered markdown string, then assert on what appeared on disk (or on captured stdout). No OpenAI
client, no HTTP stubbing, and no Skill 1 machinery are involved.

- **Given** a source artifact at `<tmp>/<basename>.json`, **when** `write_outputs` runs in save mode
  with no `out_dir`, **then** exactly `<tmp>/<basename>.requirements.json` and
  `<tmp>/<basename>.requirements.md` exist beside it, and the source artifact is unchanged.
- **Given** a source artifact whose filename stem is a position-prefixed title slug bearing no
  relation to the video id inside the accompanying document, **when** `write_outputs` runs, **then**
  the output filenames are derived from that stem and the video id appears nowhere in either output
  filename.
- **Given** two source artifacts with different filenames in one temp collection folder, **when**
  `write_outputs` runs for each, **then** two distinct document pairs exist, each mirroring its own
  source's basename.
- **Given** a source artifact and an `out_dir` pointing elsewhere, **when** `write_outputs` runs in
  save mode, **then** both files appear under `out_dir` under the same `<basename>`, and nothing is
  written beside the source artifact.
- **Given** a source artifact, **when** `write_outputs` runs with `no_save` set, **then** the temp
  directory holds nothing but the original source artifact — no `.requirements.json`, no
  `.requirements.md` — and the document is emitted on stdout.
- **Given** the rendered markdown handed in, **when** `write_outputs` writes the `.md`, **then** the
  file carries that rendered text rather than anything this function composed itself.
- **Given** the structured document handed in, **when** `write_outputs` writes the `.json`, **then**
  the file carries that document's structure (`summary`, `modules[] → features[] → requirements[]`,
  `assumptions`, `open_questions`), mirroring the `.md`.
- **Given** any of the above, **when** `write_outputs` runs, **then** no network request is made.

## Assumptions

- [ASSUMPTION] "Filename without its extension" means the **final** extension only (the path stem), so
  `01-tek-tek-ogrenci-yukleme.json` → `01-tek-tek-ogrenci-yukleme`. SKILL.md's worked example shows
  exactly one extension, and Skill 1's own `<basename>.json` / `<basename>.md` pairing is defined the
  same way (T-S1-13/14).
- [ASSUMPTION] `out_dir` absent/empty (`None`) selects the documented default ("alongside source"); the
  flag table lists the default as *alongside source* rather than as a directory value, so the default
  must be expressible as "no override given".
- [ASSUMPTION] `out_dir` is interpreted as a directory **path** to write into. SKILL.md spells the flag
  `--out-dir NAME`, and Skill 1's identically spelled flag names a folder under `--root data`; Skill 2
  has no `--root`, so the base a bare NAME would be relative to is undefined — see NEEDS
  CLARIFICATION.
- [ASSUMPTION] Print mode prints the **rendered markdown** — the document is defined as the rendered
  doc throughout SKILL.md, and "print instead" reads as showing the user the same artifact they would
  have opened. Whether the JSON mirror is also printed is not documented — see NEEDS CLARIFICATION.
- [ASSUMPTION] Files are written UTF-8. Artifact titles are routinely Turkish, and Skill 1's artifacts
  are UTF-8; a document mirroring them cannot be narrower.
- [ASSUMPTION] The `.json` mirror is written from `doc` as handed in — this function serializes, it
  does not validate, renumber, dedup, or re-order. Requirement-id validity (T-S2-04) and composite-key
  uniqueness (T-S2-05) are upstream units and are not re-litigated here.
- [ASSUMPTION] This function handles **one** artifact per call; iterating a collection's members (and
  any concurrency across them) is the caller's job (`resolve_inputs`, T-S2-07, plus the `main()` glue).

## Key entities (canonical schema excerpt)

The input side — a Skill 1 artifact, whose **filename** is the only part this unit reads:

```jsonc
// data/<slug(title)>-<playlist_id>/01-<slug>.json   or   data/_singles/<slug>.json
{ "schema_version": "1.0", "kind": "video_artifact",
  "video": { "id": "…", "title": "…", … },     // `id` is deliberately NOT a naming input
  "collection": { … } | null, "transcript": { … } }
```

The output side — Skill 2's document pair, written into the same folder by default (plan §Skill 2
Output, **[v2.1]**; these are the same files `scan_existing` (T-S1-14) must exclude when indexing a
folder, since they are consumption-layer outputs and not video artifacts):

```jsonc
// <basename>.requirements.json — mirrors <basename>.requirements.md
{ "summary": "…",
  "modules": [ { "features": [ { "requirements": [
      { "id": "<MODULE>-<FEATURE>-<NNN>", "text": "…", "source_video_id": "…",
        "trace": { "timestamp": "…", "segment_index": 0 } } ] } ] } ],
  "assumptions": [ … ], "open_questions": [ … ] }
```

`<basename>` is the source artifact's stem — the sole coupling between the two shapes above, and the
one Skill 1 owns.

## NEEDS CLARIFICATION

The items below are genuinely unspecified by the documented policy. **They are deliberately left out
of this unit's tested contract**: writing a test for them would freeze whatever the code happens to do
today into a contract nobody has decided on — which is precisely the failure mode the SK2-ORCH
`[2026-07-15]` note records. They belong in `to-do.md` as documentation gaps to settle on their own
merits.

- [NEEDS CLARIFICATION] **What a bare `--out-dir NAME` is relative to.** Skill 1 pairs `--out-dir NAME`
  with `--root data`, so a NAME resolves under the root; Skill 2 has no `--root` and its flag table
  says only "Override the output directory". Whether Skill 2's value is a full path, a name relative to
  cwd, or a name relative to the source artifact's parent is undecided.
- [NEEDS CLARIFICATION] **Whether a non-existent `out_dir` is created** (with parents) or is an error.
  Neither doc says. Skill 1's write path creates its collection folders, which suggests creation, but
  that is an inference from a different skill, not a stated Skill 2 policy.
- [NEEDS CLARIFICATION] **Overwrite policy for pre-existing outputs.** Skill 2 has no `--skip-existing`
  analog, and re-running the distiller over a folder is the normal way to pick up an edited prompt —
  which argues for overwrite — but "documents are overwritten in place" is nowhere written down, and
  neither is any backup/refuse/suffix alternative.
- [NEEDS CLARIFICATION] **Exactly what print mode emits.** Whether stdout carries the markdown only,
  the JSON only, or both (and in what order, with what separator) is unspecified; the plan says only
  "`--print` / no-save terminal mode". Whether print mode is per-artifact or accumulates across a
  collection is likewise undescribed.
- [NEEDS CLARIFICATION] **The return value.** The signature and docstring name none, and no caller
  contract is documented — whether the written paths are returned (useful for a manifest or a summary
  line) or `None` is undecided.
- [NEEDS CLARIFICATION] **JSON serialization details** — indentation and whether non-ASCII is escaped.
  Skill 1's artifacts are the natural precedent, but the plan states nothing for Skill 2's mirror; only
  "the JSON mirrors the doc".
- [NEEDS CLARIFICATION] **A source artifact whose stem already ends in `.requirements`** (i.e. running
  the distiller over its own output). Mirroring would produce `x.requirements.requirements.json`.
  Whether such an input should be rejected upstream (`resolve_inputs`) or is simply out of contemplation
  is not stated.
