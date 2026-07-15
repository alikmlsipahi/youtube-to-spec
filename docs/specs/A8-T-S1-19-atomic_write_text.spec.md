# Spec — `atomic_write_text` (T-S1-19)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§File layout / artifact + manifest writing) and the requirement that the collector must not be
> able to leave a half-written or corrupt file on disk. The collector currently writes all three of
> its outputs — the artifact `.json`, the artifact `.md`, and `_manifest.json` — with a bare
> `write_text`, which truncates the target and then streams into it; a crash, a `SIGKILL`, or a full
> disk anywhere in that window leaves a truncated file where a valid one used to be. This unit
> replaces that with a write that either fully lands or does not land at all. **No test code, no
> golden output tables here.**

## One-line purpose

Write text to a path such that an observer of that path only ever sees the complete old content or
the complete new content — never a partial write, and never a zero-length file — and such that a
failure mid-write leaves no debris behind.

## Signature

```python
def atomic_write_text(path: Path, text: str) -> None
```

Returns nothing. Raises on I/O failure (see Expected behavior).

## Inputs

- `path: Path` — the final destination path. Its parent directory is assumed to exist; this unit does
  not create it (the callers already call `mkdir(parents=True, exist_ok=True)` before writing).
  [ASSUMPTION]
- `text: str` — the full content to write. Always written as **UTF-8**, matching every existing write
  in this codebase and the plan's "write UTF-8 everywhere" rule.

## Expected behavior

The write proceeds in this order, and the order is the contract:

1. Write `text` to a **temporary file in the same directory as `path`**.
2. Flush it, then `fsync` its file descriptor.
3. `os.replace(tmp, path)` — the atomic step.
4. On any failure, remove the temporary file before propagating the error.

Each step earns its place:

- **Same directory, not a system temp dir.** `os.replace` is only atomic within a single filesystem.
  A temp file under `/tmp` may live on a different filesystem than the output directory, which
  silently degrades the "atomic" rename into a copy — reintroducing exactly the partial-write window
  this unit removes. The temp file **must** be created alongside its destination.
- **`fsync` before the replace.** `os.replace` guarantees that no reader sees a *partial* file. It
  does **not** guarantee the data reached the disk: on several filesystems a power loss shortly after
  an un-synced rename can leave a correctly-named, **zero-length** file. Renaming un-synced data is
  the classic way to produce an empty file where a valid one used to be, which is a worse outcome
  than the truncation this unit is replacing. The `fsync` is not optional.
- **`os.replace`, not `os.rename`.** `os.replace` overwrites an existing destination atomically on
  every supported platform; `os.rename`'s overwrite behavior is platform-dependent.
- **Cleanup on failure.** A failed write must not strand a temp file next to the artifacts. The
  cleanup itself must not mask the original error.

Further contract points:

- On success, `path` contains exactly `text`, encoded UTF-8, and **no temporary file remains** in the
  directory.
- On failure (disk full, permission denied, encoding error), the original error **propagates** — this
  unit does **not** swallow it and does not return a status. It differs deliberately from the
  codebase's network-facing helpers (`fetch_metadata`, `enumerate_playlist`), which degrade to `None`
  because a single unreachable video must not kill a batch. A local write failure is not that: it
  means the output directory is unusable, and continuing would produce a run whose manifest claims
  files that are not there. Loud is correct here. [ASSUMPTION]
- On failure, `path` is left **untouched** — if it existed, it still holds its previous complete
  content. The temp file absorbs every partial state.
- The temporary file's name must not collide with the collector's own outputs, and must not be picked
  up by anything that scans the directory. The directory scan that matters globs `*.json` and then
  filters by name, so a temp name ending in `.json` would be read as an artifact mid-write. [ASSUMPTION]

## Edge cases

- `path` does not exist → created. No pre-existing file is required.
- `path` exists with different content → replaced wholesale.
- `path` exists and the new `text` is **shorter** than the old content → the result is exactly the new
  text with no trailing remnant of the old. (This is a real failure mode of truncate-then-write that
  the temp-file approach cannot exhibit.)
- `text` is empty (`""`) → `path` becomes a zero-length file. This is a *legitimate* result of an
  explicit empty write and must not be conflated with the crash-induced zero-length file the `fsync`
  guards against.
- `text` contains non-ASCII (Turkish characters, emoji, CJK) → round-trips exactly under UTF-8. The
  artifacts this writes are Turkish-language transcripts; a mangled encoding here is silent corruption.
- `text` contains newlines → written verbatim, with **no** newline translation.
- Called twice on the same `path` → the second write wins completely; no interleaving.
- Two different `path`s in the same directory → independent, no interference between their temp files.
- The parent directory does not exist → the underlying error propagates (this unit does not `mkdir`).

## Acceptance scenarios (Given / When / Then)

- **Given** a path in an existing empty directory, **when** `atomic_write_text(path, text)` runs,
  **then** the path exists and reads back exactly `text`.
- **Given** a path already holding long content, **when** it is called with much shorter text,
  **then** the path reads back exactly the short text with no remnant of the old content.
- **Given** any successful call, **when** the containing directory is listed afterwards, **then** it
  contains **only** the destination file — no temporary file survives.
- **Given** `text` containing Turkish characters and emoji, **when** it runs, **then** the path reads
  back the identical string.
- **Given** `text = ""`, **when** it runs, **then** the path exists and is empty.
- **Given** a path whose parent directory does not exist, **when** it runs, **then** the error
  propagates rather than being swallowed.
- **Given** a write that fails partway (e.g. the underlying write raises), **when** it runs, **then**
  the error propagates, **and** the destination retains its previous content, **and** no temporary
  file is left in the directory.
- **Given** the same path written twice with different content, **when** both calls complete, **then**
  the path holds the second content exactly.

## Assumptions

- [ASSUMPTION] Callers create the parent directory. Both existing call sites already do
  (`out_dir.mkdir(parents=True, exist_ok=True)`), so folding `mkdir` in here would duplicate a
  responsibility rather than centralize one.
- [ASSUMPTION] Errors propagate rather than degrade to a return value. See Expected behavior.
- [ASSUMPTION] The temp file's exact naming scheme is an **implementer detail** and is not asserted by
  this unit's contract, with two constraints that *are* contractual: it lives in the same directory as
  `path`, and it is not visible to a `*.json` glob of that directory.
- [ASSUMPTION] Directory-level `fsync` (syncing the parent directory entry after the rename, which is
  what makes the *rename itself* durable across a power loss, as opposed to the file's *contents*) is
  **out of scope**. The failure this unit is specified against is a process crash or kill, against
  which `os.replace` alone is sufficient; full power-loss durability of the directory entry is a
  materially larger contract for an artifact that can simply be re-fetched.
- [ASSUMPTION] This unit does not decide **what** to write, **when**, or **in what order** — those are
  the orchestration loop's concerns. Notably, the ordering rule that the artifact `.md` is written
  *before* its `.json` (so that the `.json` landing is the run's commit point for `--skip-existing`)
  lives in the caller, not here.

## Key entities (canonical schema excerpt)

This unit has no canonical-schema surface of its own — it is content-agnostic and writes whatever
string it is handed. It replaces the three bare `write_text` calls in the collector:

```jsonc
// data/<collection>/
//   <NN>-<slug>.json        // the per-video artifact — what --skip-existing reads back
//   <NN>-<slug>.md          // the readable view
//   _manifest.json          // the collection record — Skill 2's input resolution reads this
```

`_manifest.json` is the highest-stakes of the three: a corrupt artifact `.json` is self-healing
(the existing directory scan cannot parse it, so it is not indexed, so the next `--skip-existing` run
re-fetches it), whereas nothing validates the manifest before Skill 2 consumes it.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether a leftover temp file from a `SIGKILL` (which no `finally` can clean
  up, by definition) should be swept at the start of the next run. This unit's cleanup covers ordinary
  exceptions only; a hard kill can strand a temp file forever. It is inert — nothing reads it, and the
  next successful write of that destination does not collide with it — so the cost is a stray file,
  not a correctness problem. Not addressed here.
- [NEEDS CLARIFICATION] Whether the two artifact files (`.json` and `.md`) should be atomic **as a
  pair**. This unit makes each individually atomic; a crash between them can still leave a `.json`
  with no matching `.md`. The caller mitigates this by ordering (`.md` first, `.json` last, so the
  `.json` is the commit marker), which closes the window that matters for `--skip-existing` but does
  not make the pair truly transactional. Cross-file transactions are out of scope.
