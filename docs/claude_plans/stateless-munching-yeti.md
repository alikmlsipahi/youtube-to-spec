# Plan — Clean reset of all implementation work (start from scratch)

## Context

The user is restarting Phase-1 implementation from zero. All implementation-produced artifacts (the A1
helper code, its tests/fixtures, and the A1 spec) must be removed, and the progress tracker reset so
every catalog row reads `[pending]`. The **plans, briefs, the reuse-source old skill, and the empty
skill directory scaffolding are preserved.** The deletions are of git-tracked files (committed in
`d6b7824`), and the user chose to **delete + commit** so the repo history reflects the fresh start.

This plan covers file deletion, progress reset, and git — no new implementation.

## Verified current state (inventory)

**Tracked files to delete (5, all committed in `d6b7824`):**
- `.claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py`
- `.claude/skills/youtube-artifact-collector/tests/conftest.py`
- `.claude/skills/youtube-artifact-collector/tests/test_pure_helpers.py`
- `.claude/skills/youtube-artifact-collector/tests/fixtures/inputs/video_id_urls.json`
- `docs/specs/A1-pure-helpers.spec.md`

**Untracked build artifacts to delete:**
- `.claude/skills/youtube-artifact-collector/scripts/__pycache__/` and `…/tests/__pycache__/` (`.pyc`)

**Nothing to delete in `feature-requirement-extractor/`** — its `prompts/ scripts/ templates/ tests/`
dirs are already empty. **`data/` is empty.** **No gap files** exist under `docs/specs/`.

## Step 1 — Delete implementation artifacts

Remove the 5 tracked files (via `git rm`, so the deletions are staged) **and** the untracked
`__pycache__` dirs (via `rm -rf`). Use `git rm` for tracked paths so they're staged for the reset
commit in Step 4.

```
git rm .claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py \
       .claude/skills/youtube-artifact-collector/tests/conftest.py \
       .claude/skills/youtube-artifact-collector/tests/test_pure_helpers.py \
       .claude/skills/youtube-artifact-collector/tests/fixtures/inputs/video_id_urls.json \
       docs/specs/A1-pure-helpers.spec.md
rm -rf .claude/skills/youtube-artifact-collector/scripts/__pycache__ \
       .claude/skills/youtube-artifact-collector/tests/__pycache__
```

## Step 2 — Preserve (do NOT touch)

- All plan/brief docs: `IMPLEMENTATION_PLAN.md`, `IMPLEMENTATION_PLAN_v2.md`,
  `IMPLEMENTATION_PLAN-progress.md`, `IMPLEMENTATION_PLAN_DRAFT.md`, `0x_*.md`, `research_docs/`,
  `claude_plans/`.
- `CLAUDE.md`.
- `.claude/skills/youtube-transcript/` (old skill — reuse source, slated for later deprecation).
- **Empty directory scaffolding kept on disk** (they'll be empty after deletion; git won't track empty
  dirs, but they remain locally): `youtube-artifact-collector/{scripts,tests,tests/fixtures/inputs,tests/fixtures/expected}`
  and all `feature-requirement-extractor/*` dirs.

## Step 3 — Reset progress to all `[pending]`

In `docs/IMPLEMENTATION_PLAN-progress.md`, flip the only non-pending rows — `T-S1-01..04` (currently
`[green]`) — back to `[pending]`. All other rows (T-S1-05..11, T-S2-*, SK*, I-*, A-*) are already
`[pending]`. Keep the file's structure, the v2 header, and the Phase C Authoring section intact — only
the four states change.

## Step 4 — Git (delete + commit, per user choice)

There are **pre-existing uncommitted doc changes** in the tree (the earlier v2-consistency work:
`CLAUDE.md`, `IMPLEMENTATION_PLAN.md` banner, new `IMPLEMENTATION_PLAN_v2.md`, progress v2-sync). To
keep the reset as its own clean commit, do **two** commits via the `/commit` skill (security-scan →
stage-all → confirm):

1. **Commit A — finish the doc-consistency batch** (clears the tree of the prior pending edits):
   `docs: make v2 plan authoritative and sync progress/CLAUDE.md`.
2. Perform Steps 1 + 3, then **Commit B — the reset**:
   `chore: reset Phase-1 implementation, restart from scratch` (the `git rm` deletions + the four
   progress rows back to pending).

If the user would rather fold everything into a single commit, that's a trivial variation — but two
commits keep "adopt v2 plan" and "wipe implementation" as separate, legible history entries.

## Step 5 — Report

State exactly what was deleted, what was preserved, that progress is fully `[pending]`, and show the two
resulting commit lines.

## Verification

```
# nothing tracked left under the implementation paths:
git ls-files .claude/skills/youtube-artifact-collector docs/specs   # → empty
# the old skill survives:
test -f .claude/skills/youtube-transcript/SKILL.md && echo OK
# progress fully reset (expect 0 non-pending rows):
grep -cE '^\- \[(green|code-written|test-written|spec|drafted|accepted)\]' docs/IMPLEMENTATION_PLAN-progress.md   # → 0
grep -cE '^\- \[pending\]' docs/IMPLEMENTATION_PLAN-progress.md   # → 28
# tests are gone (collection finds nothing):
ls .claude/skills/youtube-artifact-collector/tests/   # → empty
git log --oneline -2
```
