# Plan — Close the "who authors the prose deliverables" gap in the implementation plan

## Context

The project's true deliverables are **two Claude-Code skills**, and each skill's *primary*
artifact is a `SKILL.md` (plus, for Skill 2, swappable `prompts/`, `templates/`, and
`.env.example`). Yet after running the blind implementer agents, only Python helper code
exists — no `SKILL.md`, no prompt/template assets.

This is **not** a bug in the implementers and **not** a wrong plan in substance. It is a
*workflow omission*: `docs/IMPLEMENTATION_PLAN.md` lists these prose/asset files as deliverables
(`Critical files`, lines 389–392) and as acceptance rows (`A-01`–`A-04`), but the **build sequence**
(`A1–A5` blind-TDD units, `B1–B7` integration/acceptance gates) never names *who* authors them, *in
which step*, or *with what agent role*. Blind-TDD agents correctly build only testable units
(pure functions); prose files have no unit test, so they belong to no step and were never produced.

**Outcome of this change:** insert an explicit, non-blind **Phase C (Authoring)** between the unit
layer (A) and the gate layer (B), assign each prose/asset deliverable to a concrete step and agent
role, and add matching rows to the progress checklist — so nothing falls through the cracks and the
blind-TDD bias barrier on the *code* stays intact.

This plan edits **only two documentation files**. No code changes.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Placement | **Single authoring phase (Phase C)** after all A units are green, before B gates. |
| Mode | **Normal agent session** — no blind barrier (these files have no tests). The `tests/**`, `conftest.py`, `fixtures/**` **denylist still applies** so the code's blind-TDD barrier is never broken. Authoring agents **may** read the finished scripts (they are source, not tests) to document CLI/flags/output accurately. |
| Progress tracking | **New "Authoring (non-blind)" section** with rows `SK1-DOC`, `SK2-ASSETS`, `SK2-DOC`. The existing `A-01`–`A-04` rows remain as the verification gates for them. |
| Prompt/template content | **Agent drafts** a reasonable first version matching the locked `<MODULE>-<FEATURE>-<NNN>` ID scheme; **user reviews** at `A-03`/`A-04` (swappable, so no code change to revise). |

### Why Phase C sits *between* A and B
- It must come **after A** so the authoring agent can read the *finished* `extract_artifacts.py` /
  `extract_requirements.py` and document real CLI flags, output layout, and — critically for Skill 2 —
  the exact `{{placeholder}}` names the OpenAI engine's `fill_prompt` (T-S2-02) expects. This resolves
  the prompt-vs-code coupling cleanly: unit tests used *fixture* prompts; the *real* prompt is now
  authored to match the shipped code.
- It must come **before B** because the gates depend on these files: `B4` tests Skill 1's `SKILL.md`
  trigger (`A-01`); `B5` *is* Skill 2's Claude-native engine (`SKILL.md` + prompts + template, no
  script) verified by `A-02`/`A-03`; `B6`'s OpenAI engine reads the real prompts/templates at runtime.

## File 1 — `docs/IMPLEMENTATION_PLAN.md`

### Edit 1a — add the authoring role (in "Roles", after the Reviser bullet, ~line 265)
Add a 6th role:
> 6. **Authoring agent (non-blind):** for the *prose/asset* deliverables that have no unit test
>    (`SKILL.md` ×2, Skill 2 `prompts/*`, `templates/*`, `.env.example`). Runs as a **normal**
>    session — there is no test to be blind against — but the **same denylist applies**
>    (`tests/**`, `**/conftest.py`, `**/fixtures/**`) so the code's blind-TDD barrier is preserved.
>    It **may** read the finished scripts (source, not tests) to document CLI flags, output layout,
>    and the exact `{{placeholder}}` contract. Verified by the human at the `A-*` gates.

### Edit 1b — insert Phase C into "Build & verification sequence" (between the A block ~line 360 and "B. Integration…" ~line 362)
Update the section intro (line 351) from "Two layers, in order" to "**Three** layers, in order: unit
blind-TDD (A) → authoring (C) → integration + acceptance gates (B)", then insert:

> **C. Authoring (non-blind)** — after all A units are green; runs as a normal session with the
> `tests/**` denylist still in force. Each step ticks its checklist row (`pending → drafted → accepted`,
> accepted at the mapped `A-*` gate):
> - **C1 → `SK1-DOC`**: author `youtube-artifact-collector/SKILL.md` — frontmatter (`name` +
>   description with the de-confliction trigger from line 169, "…**not** a quick single-video transcript
>   dump"), how to invoke `scripts/extract_artifacts.py`, and the CLI flags as actually shipped.
>   *(verified by A-01)*
> - **C2 → `SK2-ASSETS`**: author Skill 2's swappable files — `prompts/system_prompt.md`,
>   `prompts/extraction_prompt.md` (with `{{placeholders}}` matching the finished `fill_prompt`, plus the
>   **module/action code lookup table** for the `<MODULE>-<FEATURE>-<NNN>` scheme), `templates/requirement_doc.md`,
>   and `.env.example` (`OPENAI_API_KEY=…`). Agent drafts; **user reviews** the domain content.
>   *(verified by A-03, A-04)*
> - **C3 → `SK2-DOC`**: author `feature-requirement-extractor/SKILL.md` — Claude-native engine
>   instructions (read artifact JSON + `_manifest.json`, read the C2 prompt/template files, fill, then
>   write/print) + the trigger from line 229 + the optional `--engine openai` note. Depends on C2.
>   *(verified by A-02, A-03)*

Also add a one-line dependency note under the "B." block: "B4/B5/B6 require Phase C complete
(SKILL.md + Skill 2 assets must exist before trigger / Claude-native / OpenAI-engine gates run)."

### Edit 1c — annotate "Critical files" (lines 389–392)
Tag each prose/asset entry with its step, e.g. append `— authored in Phase C1` to the Skill 1
`SKILL.md` line, `— Phase C3` to the Skill 2 `SKILL.md` line, and `— Phase C2` to the
`{prompts/*,templates/*,.env.example}` line. (Documentation-only; no path changes.)

### Edit 1d — checklist-section note (lines 335–345)
Add one sentence: authoring rows use the lifecycle `pending → drafted → accepted` (no
`test-written`/`green` states, since they have no unit tests).

## File 2 — `docs/IMPLEMENTATION_PLAN-progress.md`

Insert a new section **between** the "Skill 2 … (unit / blind-TDD)" section (ends line 32) and the
"Integration tier" section (line 34) — so a top-down "first non-`accepted` row" resume naturally hits
authoring after all units and before the gates:

```markdown
## Authoring (non-blind; prose/assets — test-denylist still applies)

> Lifecycle: pending → drafted → accepted. Accepted at the mapped acceptance gate.

- [pending] SK1-DOC — youtube-artifact-collector/SKILL.md (Phase C1; gate A-01)
- [pending] SK2-ASSETS — Skill 2 prompts/{system_prompt,extraction_prompt}.md, templates/requirement_doc.md, .env.example (Phase C2; gates A-03, A-04)
- [pending] SK2-DOC — feature-requirement-extractor/SKILL.md (Phase C3; gates A-02, A-03)
```

(The existing `A-01`–`A-04` acceptance rows are unchanged — they remain the verification gates.)

## Where you resume (your actual question)

**You do not start over. Phase C is purely additive and lands *after* everything currently in flight,
so no existing work is invalidated or redone.** Concretely, by the resume rule ("continue from the
first non-`green` row"):

- Current state: `T-S1-01..04` are **`code-written`, not yet `green`** (the verifier hasn't confirmed
  them); `T-S1-05..11` and all of Skill 2 are `pending`.
- So the true next action is **not** new code — it's **running the verifier on A1 (`T-S1-01..04`)** to
  drive those four rows to `green`, then proceeding through `A2` (`T-S1-05..07`), `A3`, `A4`, `A5`
  exactly as the plan already says.
- **Only after all A rows are green** do you enter the **new Phase C** (C1→C2→C3), then the B gates.

In short: continue from where you left off (verify A1, then keep going down the unit list). This plan
just guarantees that when you reach the end of the units, the `SKILL.md` and Skill 2 assets are now an
*owned, sequenced step* (Phase C) instead of an unassigned gap.

## Verification

This change is to planning docs, so verification is consistency-of-spec, not test execution:
- `docs/IMPLEMENTATION_PLAN.md` "Build & verification sequence" now reads A → C → B, and every
  `A-01`–`A-04` acceptance row maps to a concrete Phase C step (C1↔A-01, C2↔A-03/A-04, C3↔A-02/A-03).
- Every prose/asset file in "Critical files" (lines 389–392) is traceable to a Phase C step.
- `docs/IMPLEMENTATION_PLAN-progress.md` contains the three new authoring rows positioned between the
  unit sections and the integration tier; existing rows are untouched.
- Sanity grep: `grep -n "Phase C\|SK1-DOC\|SK2-DOC\|SK2-ASSETS" docs/IMPLEMENTATION_PLAN*.md` returns
  hits in both files.
