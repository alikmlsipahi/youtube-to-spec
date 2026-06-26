# Spec — `fetch_metadata` graceful degradation (T-S1-11)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #3 `fetch_metadata(video_id)` — "`yt-dlp --skip-download --dump-json` via subprocess; on
> failure return `None` + record (graceful degradation). Subprocess (not Python API) for stable JSON +
> per-video isolation"; catalog row T-S1-11; capability "Graceful degradation"; §Reuse "`except Exception
> → stderr → sys.exit(1)` convention" — but per-video failures here must **not** exit). **No test code,
> no golden output tables here.**

## One-line purpose

Fetch one video's metadata by shelling out to yt-dlp, returning the parsed metadata dict on success and
**`None` on any failure** (non-zero exit, missing tool, unparseable output) — so a single bad video
degrades gracefully and the surrounding batch run continues instead of aborting.

## Signature

```python
def fetch_metadata(video_id: str) -> dict | None
```

Performs a subprocess call (`subprocess.run`) to yt-dlp; it does **not** use the Python yt-dlp API
(subprocess is chosen for stable JSON output and per-video isolation). It is **not** pure — but it is
deterministic given a mocked subprocess, and the unit tier mocks the subprocess so no network is touched.

## Inputs

- `video_id: str` — an 11-char YouTube video id (already extracted upstream via `extract_video_id`).

The function invokes, conceptually, `yt-dlp --skip-download --dump-json <video_id>` via `subprocess.run`,
capturing stdout (the per-video JSON) and stderr, and inspecting the process return code.

## Expected behavior

- **Success path:** when the subprocess exits with **return code `0`**, parse its captured **stdout** as
  JSON and return the resulting `dict`.
- **Failure path (graceful):** when the subprocess exits with a **non-zero** return code, return
  **`None`** — do **not** raise, and do **not** call `sys.exit`. (The caller records the video as
  `metadata_failed` with a reason and continues the batch — that recording is the orchestration loop's
  job; this unit's contract is "non-zero exit → `None`".)
- The function never lets a single video's failure crash the run; the per-video try/except isolation that
  the plan's risk section calls for resolves, at this unit's boundary, to "return `None` on failure".

## Edge cases

- **Non-zero exit (e.g. private/deleted/unavailable video):** returns `None`.
- **Return code 0 with valid JSON stdout:** returns the parsed dict (the metadata yt-dlp emitted).
- **Return code 0 but unparseable/empty stdout:** treated as a failure → returns `None` (defensive; a
  successful exit with garbage output should not propagate a parse exception). [ASSUMPTION]
- **yt-dlp executable missing (`FileNotFoundError`) or other subprocess error:** treated as a failure →
  returns `None`, not an exception. [ASSUMPTION]
- The function must **never** raise on the failure paths above; failure is always signalled by the `None`
  return value.

## Acceptance scenarios (Given / When / Then)

- **Given** `subprocess.run` is mocked to return a process result with a **non-zero** return code, **when**
  `fetch_metadata("someVideoId")` runs, **then** it returns `None` and does not raise.
- **Given** `subprocess.run` is mocked to return return code `0` with stdout being a valid JSON object,
  **when** `fetch_metadata` runs, **then** it returns that object as a `dict`.
- **Given** two videos processed in sequence where the first's subprocess fails (returns `None`), **when**
  the batch continues, **then** the failure is isolated to that video — the second still proceeds (the
  unit guarantees the `None` signal that makes this continuation possible).

## Assumptions

- [ASSUMPTION] The function calls `subprocess.run(...)` (so it is patchable at `subprocess.run`), captures
  output as text, and reads `.returncode` and `.stdout`. The plan specifies "subprocess … `--dump-json`"
  but not the exact call form; the reuse source (`get_transcript.py`) establishes the subprocess + JSON
  convention.
- [ASSUMPTION] Success is defined as `returncode == 0` **and** stdout parses as JSON; any other outcome
  yields `None`.
- [ASSUMPTION] The "+ record" part of "on failure return `None` + record" is performed by the **caller**
  (the batch loop builds the `metadata_failed` member record); `fetch_metadata` itself only returns
  `None`. The unit test therefore pins the `None`/`dict` return contract, which is what makes the
  caller's graceful recording possible.
- [ASSUMPTION] No `sys.exit` is called on a per-video failure — the script-wide `except → sys.exit(1)`
  convention applies to fatal top-level errors, not to a single video's metadata miss.

## Key entities (canonical schema excerpt)

```jsonc
// per-video artifact → extraction{}
"extraction": { "metadata_ok","transcript_ok","warnings","tool_versions" }
// _manifest.json member when this returns None:
{ "status":"metadata_failed", "reason":"…", "files": null }
```

A `None` from `fetch_metadata` is what drives `metadata_ok: false` / a `metadata_failed` manifest member,
keeping the failed video listed (with reason) rather than silently dropped.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether a return-code-0-but-empty-stdout case should be a failure (`None`) or a
  surfaced error is unspecified; this spec treats it as `None` for safety. The two pinned unit cases are
  the unambiguous ones (non-zero → `None`; zero + valid JSON → dict).
- [NEEDS CLARIFICATION] The precise yt-dlp argument vector (flag order, extra flags like
  `--no-warnings`/`--sleep-requests`) is an implementer detail and is **not** asserted by this unit; the
  test pins behavior on the mocked return code and stdout, not on the exact command line.
