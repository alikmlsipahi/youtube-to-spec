# Plan — Finish the pipeline agentically to "ready to use"

## Context

Every unit is `[green]` and both skill scripts + Phase C assets are written (`[drafted]`).
What's left is **not new code** — it's the Phase B verification gates that the build was
deliberately deferred to: real-network integration, prompt-following/trigger acceptance, the
OpenAI engine, and promoting the drafted Phase C docs to `[accepted]`. The user wants me to
**run and verify all of it myself**, end to end, until the two skills are demonstrably usable —
not to hand back commands for them to run.

Current truth (`docs/IMPLEMENTATION_PLAN-progress.md`): all `T-S1-*`/`T-S2-*` green; `SK1-ORCH`/
`SK2-ORCH` done; `SK1-DOC`/`SK2-ASSETS`/`SK2-DOC` drafted; `I-01` green; **`I-02`, `I-03`,
`A-01..A-04` pending**. A full playlist extraction already sits in
`data/example-kayit-modulu-rehberi-PLk-.../` (24 members: 19 `ok`, 5 `metadata_failed`) but the
manifest uses a nested `collection`/`members`/`summary` shape, so I-02 must be validated against
the *actual* schema, not the guide's flat-field shorthand.

### Decisions locked with the user
- **I-03 (OpenAI):** in scope — user has an `OPENAI_API_KEY` and will provide it when needed, via
  project-local `.claude/skills/feature-requirement-extractor/.env`. **Precondition:** I first
  verify that `.env` path is git-ignored. If the key is absent or cannot be used safely →
  `I-03 → [blocked: no key]`, **never** `[accepted]`.
- **B7 (deprecate `youtube-transcript`):** **out of scope.** Do not deprecate, delete, move,
  rename, or archive the skill; do not edit `skills-lock.json`.
- **Fix protocol:** **strict blind-TDD.** If any gate exposes a bug needing a code fix, it is fixed
  **only** from the relevant `docs/specs/*.spec.md` + a plain-language behavioral gap — never from
  reading tests. I keep the `tests/**` / `conftest` / `fixtures/**` denylist at all times.

### Hard rules (manual approval, strict scope)
- **No git mutations:** no `git add`, `git commit`, `git push`; no commits of any kind.
- **Secrets:** never print, cat, echo, grep, log, or otherwise expose `OPENAI_API_KEY` or `.env`
  contents. Do not modify `.env` except an exact change I explicitly approve first.
- **Tests untouched:** never edit tests, fixtures, or conftest files.
- **Temp files:** prompt-swap variants live only in the scratchpad (outside tracked repo files) and
  are deleted after verification.
- **Runtime artifacts:** may be written under `data/**` (git-ignored) freely.
- **Only tracked file editable:** `docs/IMPLEMENTATION_PLAN-progress.md`, and only *after* real
  evidence from an executed check. **Before editing any tracked file I show the exact target file
  and intended diff for approval.**

## Definition of "ready to use"
Both skills exercised on real inputs with outputs validated; the default (no-key) Claude-native
path proven; OpenAI path proven once the key lands; all Phase B/acceptance rows and the three
Phase C authoring rows at `[accepted]` (I-03 may end `[accepted]` or `[blocked: no key]`).

---

## Step 0 — Baseline sanity (offline, no risk)
Reconfirm the whole unit tier is still green before touching anything.

```bash
uv run --with pytest pytest .claude/skills/youtube-artifact-collector/tests/ -q
uv run --with pytest pytest .claude/skills/feature-requirement-extractor/tests/ -q
```
**Pass:** both suites all-pass. Any failure → strict blind-fix loop (≤3), then continue.

---

## Step 1 — Skill 1 single-video, file-writing path (guide B2; solidifies I-01)
`I-01` proved `--print`; now prove the on-disk artifacts.

```bash
uv run .claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py fl1DSmwQKKY --root data
```
**Verify (my checks, via python -m json.tool / jq):**
- `data/_singles/fl1DSmwQKKY.json` **and** `.md` exist.
- JSON `transcript.selected.type == "auto"`, `available_tracks == ["tr"]`, `segment_count == 60`.
- Every `segments[]` entry carries an `index` field (0..59, contiguous).
- `.md` is human-readable with timestamped lines.

**Pass:** all true → note evidence. (No progress row of its own; feeds I-01 confidence.)

---

## Step 2 — Skill 1 playlist + graceful degradation (I-02) ⟵ first pending row
Re-run the playlist fresh (don't trust stale data) into a scratch root, then validate the
manifest against its **real nested schema**.

```bash
uv run .claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py \
  "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" --playlist --root data
```
**Verify** the produced `_manifest.json`:
- `collection` block preserves the playlist id / ordered relation; `schema_version` present
  (locate wherever it actually lives — likely under `collection`).
- `members[]` ordered by `position`; ≥19 `status:"ok"`, exactly 5 non-ok
  (`metadata_failed`/unavailable) each with a `reason` — this **is** the graceful-degradation proof.
- Hidden/unavailable count surfaced (in `summary`) and consistent with the 5 failures.
- Each `ok` member has real `files` (json+md) on disk; failed members recorded but not fatal.

**Pass:** ordered members + 5 recorded failures + run exited 0 → `I-02 → [green]`, and
`SK1-ORCH` note updated (I-02 ✓).

---

## Step 3 — Skill 2 Claude-native engine, real artifact (A-03) — the default, no-key path
This is the engine that matters for "usable without OpenAI." I run it **in-chat** (the skill has
no script for the claude engine): read the artifact + external prompt/template, produce the doc.

Inputs: `data/_singles/fl1DSmwQKKY.json` (from Step 1),
`.claude/skills/feature-requirement-extractor/prompts/extraction_prompt.md`,
`.../templates/requirement_doc.md`, `.../prompts/system_prompt.md`.

**Produce** a filled Module→Feature→Requirement doc and **verify:**
- Requirement IDs match the `<MODULE>-<FEATURE>-<NNN>` scheme (reuse `validate_req_id` in
  `extract_requirements.py:132` as the pattern oracle; composite keys unique).
- Each requirement carries a **trace** to a real transcript segment whose timestamp exists in the
  artifact's `segments[]`.

**Pass:** codes valid + traces resolve → `A-03 → [accepted]`.

---

## Step 4 — Prompt-swap independence (A-04)
Prove analyses swap at the prompt level, not the code level (core project principle).

- Copy `prompts/extraction_prompt.md` to a temp variant with a visibly different instruction
  (e.g. different grouping/emphasis) **in the scratchpad** — do not commit a throwaway.
- Re-run the Step-3 Claude-native flow pointed at the variant prompt.
- **Verify:** output structure/content changes, and `extract_requirements.py` / no `.py` was
  edited to achieve it.

**Pass:** output differs with zero code edits → `A-04 → [accepted]`.

---

## Step 5 — SKILL.md trigger review (A-01, A-02)
These gate on Claude routing to the right skill. I verify by auditing the shipped `SKILL.md`
frontmatter for correct, de-conflicted triggers (not by guessing model behavior):
- `youtube-artifact-collector/SKILL.md`: fires on "collect artifacts for this playlist"; its
  description explicitly steers *away* from single-video dumps toward `youtube-transcript`.
- `feature-requirement-extractor/SKILL.md`: fires on "extract requirements from this artifact";
  consumption trigger ("from already-extracted artifacts"), not URL ingestion.
- CLI usage documented in each SKILL.md matches the **actual argparse** (Skill 1 flags at
  `extract_artifacts.py:524`; Skill 2 flags at `extract_requirements.py:545`).

**Pass:** descriptions unambiguous + usage matches shipped flags → `A-01 → [accepted]`,
`A-02 → [accepted]`. Promote Phase C rows now proven: `SK1-DOC`, `SK2-ASSETS`, `SK2-DOC → [accepted]`.

---

## Step 6 — OpenAI engine (I-03) — gated on the key, safety-first
Only step that waits on the user. Sequence:
1. **Confirm `.env` is git-ignored** before anything: `git check-ignore -v
   .claude/skills/feature-requirement-extractor/.env`. If it is **not** ignored → stop, tell the
   user, do not write the key there → `I-03 → [blocked: no key]`.
2. User places the key in `.claude/skills/feature-requirement-extractor/.env` themselves (I do not
   edit `.env` without an explicit, exact approved change). I never echo/cat/grep/log the key or
   `.env` contents.
3. Run — the key is loaded by the script's own `.env` loader, never passed on a visible cmdline:

```bash
uv run .claude/skills/feature-requirement-extractor/scripts/extract_requirements.py \
  data/_singles/fl1DSmwQKKY.json --engine openai --print
```
**Verify:** returns the **same shape** (module/feature/requirement + traces, valid IDs) as the
Step-3 Claude-native output; `json_schema` structured output parses.

**Pass:** `.env` ignored + shapes match → `I-03 → [accepted]`. Key absent / `.env` not ignored /
unsafe → `I-03 → [blocked: no key]`; everything else still completes (skill is usable without it).

---

## Step 7 — Close-out
- Update `docs/IMPLEMENTATION_PLAN-progress.md` rows to their proven states (evidence-based only;
  no assertion text — blind barrier stays intact).
- Summarize to the user: what ran, what each gate proved, any residual (`I-03` if key absent),
  and confirm both skills are ready to use. `B7` deprecation intentionally left undone.

---

## Verification tooling & guardrails
- **Truth source:** advance a progress row only on a real run's evidence; `data/` is gitignored so
  writing there is safe.
- **Blind-TDD:** I never open `**/tests/**`, `**/conftest.py`, `**/fixtures/**` when writing/fixing
  script code. Fix loop = blind implementer (spec + behavioral gap) → verifier (reads tests) → ≤3
  iters → escalate.
- **Reuse, don't rewrite:** validation leans on existing helpers already in the scripts
  (`validate_req_id`, `require_api_key`, `resolve_inputs`, manifest/segment builders) rather than
  new checking code.
- **No commits** unless you ask; changes here are runs + the two progress-file edits.

## Files touched
- `docs/IMPLEMENTATION_PLAN-progress.md` — row state transitions only (the sole tracked repo file
  edited), **after showing the exact diff for approval** and only on real evidence.
- `data/**` (git-ignored) — regenerated artifacts from real runs.
- Scratchpad only — the temp prompt variant for A-04 (deleted after).
- Script `.py` files — **only if** a gate exposes a bug, strictly via the blind loop, and the diff
  is shown before applying.

## Explicitly NOT touched
- No `git add/commit/push`, no commits. No `.env` edits (unless an exact change I pre-approve).
- No deprecate/delete/move/rename/archive of `youtube-transcript`; no `skills-lock.json` edit.
- No edits to tests / fixtures / conftest. No exposing of `OPENAI_API_KEY` or `.env` contents.
