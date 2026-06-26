# Spec — `fill_prompt` (T-S2-02)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 — OpenAI engine "loads the **same** external prompts/template, **fills placeholders**…";
> §Risks "Prompt-vs-code placeholder drift" — the real `extraction_prompt.md` is authored later against
> *this* `fill_prompt` contract; catalog row T-S2-02 "every `{{placeholder}}` replaced from artifact; no
> residual `{{…}}`"; `02_PRODUCT_BRIEF.md` §LLM Entegrasyonu — "promptları harici dosyalardan okuyabilmek"
> and "transcript ve metadata'yı bu promptlarla birlikte modele göndermek"). **No test code, no golden
> output tables here.**

## One-line purpose

Substitute every `{{placeholder}}` token in an externally-authored prompt template with the corresponding
value drawn (defensively) from a Skill 1 video artifact, leaving **no** unresolved `{{…}}` token in the
returned prompt.

## Signature

```python
def fill_prompt(template: str, artifact: dict) -> str
```

Pure and deterministic; no I/O, no network. The caller is responsible for reading the template file and
the artifact JSON from disk; this unit only transforms text. The template uses double-brace
`{{placeholder}}` markers (so single braces and JSON braces in transcript text are never touched).

## Inputs

- `template: str` — the raw text of an external prompt file containing zero or more `{{placeholder}}`
  markers. Authored later in Phase C2 **against this contract**; the unit-test tier uses a fixture
  template, not the shipped one.
- `artifact: dict` — one canonical Skill 1 `<video_id>.json` object (`schema_version` `"1.0"`,
  `kind: "video_artifact"`), with `video{}`, `collection{}` (may be `null`), and `transcript{}` blocks.

## Recognized placeholder vocabulary (the contract)

`fill_prompt` recognizes exactly these placeholders and maps each to a value derived from the artifact.
All reads are **defensive**: a missing/`null` source yields the empty string `""` (never an exception,
never the literal `None`).

| placeholder | source in artifact | when missing/null |
|---|---|---|
| `{{video_id}}` | `video.id` | `""` |
| `{{video_url}}` | `video.url` | `""` |
| `{{video_title}}` | `video.title` | `""` |
| `{{channel}}` | `video.channel` | `""` |
| `{{description}}` | `video.description` | `""` |
| `{{collection_title}}` | `collection.title` (when `collection` is not `null`) | `""` |
| `{{transcript}}` | rendered transcript (below) | `"(no transcript available)"` |

**Transcript rendering for `{{transcript}}`:** when `transcript.available` is true, render the segments as
text, **one segment per line**, each line carrying the segment's stable `index` and `start` time so the
LLM can produce `trace{timestamp, segment_index}` values, followed by the **verbatim** segment text — for
example `[<index>] (<start>s) <text>`. Segment text is never modified. When the transcript is unavailable
(`transcript.available` false or the block absent), the placeholder becomes `"(no transcript available)"`.

## Expected behavior

1. Replace **every** occurrence of each recognized placeholder with its derived value (a placeholder may
   appear more than once and every occurrence is replaced).
2. After substitution, the returned string contains **no** residual `{{…}}` token.
3. If the template contains an **unrecognized** `{{…}}` token (one not in the vocabulary above), raise a
   clear `ValueError` naming the offending placeholder — this is the guard that surfaces prompt-vs-code
   drift rather than silently shipping a half-filled prompt.
4. Text outside placeholders (instructions, the module/action lookup table, examples) is passed through
   unchanged.
5. The function never mutates the input `artifact`.

## Edge cases

- **`collection` is `null`** (a true single video) → `{{collection_title}}` resolves to `""`, with no
  error.
- **Transcript unavailable** → `{{transcript}}` resolves to the fixed marker, with no error.
- **A placeholder appears multiple times** → all occurrences replaced.
- **A recognized placeholder's source field is absent** → replaced with `""` (defensive read), not left
  as a literal marker.
- **An unrecognized placeholder is present** → `ValueError` (not a silent leftover, not an empty string).
- **Transcript text contains brace characters or `{ }`** → untouched, because only `{{double-brace}}`
  tokens are substitution targets.
- **A template with no placeholders** → returned unchanged.

## Acceptance scenarios (Given / When / Then)

- **Given** a template using each recognized placeholder once and a fully-populated artifact, **when**
  `fill_prompt` runs, **then** every placeholder is replaced by its artifact-derived value and the result
  contains no `{{` substring.
- **Given** an artifact whose `description` is absent, **when** filled, **then** `{{description}}` becomes
  the empty string and no `{{description}}` marker remains.
- **Given** an artifact with `collection: null`, **when** filled, **then** `{{collection_title}}` becomes
  empty and the call does not raise.
- **Given** an artifact whose transcript is unavailable, **when** filled, **then** `{{transcript}}`
  becomes `"(no transcript available)"`.
- **Given** an available transcript, **when** filled, **then** each segment's verbatim text appears in the
  result and the segment `index` values are present (so traces can be produced).
- **Given** a template containing `{{unknown_field}}`, **when** filled, **then** a `ValueError` is raised
  naming `unknown_field`.
- **Given** a placeholder appearing twice, **when** filled, **then** both occurrences are replaced.

## Assumptions

- [ASSUMPTION] Signature is `fill_prompt(template, artifact)` — the artifact is the single source of
  values; collection/module context is read from the artifact's own `collection{}` block rather than a
  separately-passed manifest (the plan mentions `_manifest.json` for module context at the *engine* level,
  not for this pure unit).
- [ASSUMPTION] The placeholder vocabulary above is the contract; the plan does not enumerate the exact
  names, so this list is authoritative for both the implementer and the Phase C2 `extraction_prompt.md`.
- [ASSUMPTION] Markers are double-brace `{{name}}` (single braces and JSON braces are never substitution
  targets), and unrecognized markers raise rather than being left in place — the strongest reading of "no
  residual `{{…}}`".
- [ASSUMPTION] The exact transcript line format (`[<index>] (<start>s) <text>`) is illustrative; the
  load-bearing requirements are that segment text is verbatim and each segment's `index` is present.
- [ASSUMPTION] Missing scalar fields render as `""` rather than the string `"None"`.

## Key entities (canonical schema excerpt)

```jsonc
{
  "video": { "id","url","title","channel","description", … },
  "collection": { "type","id","title", … } | null,
  "transcript": {
    "available": true,
    "segments": [ { "index":0, "start":0.0, "duration":3.2, "end":3.2, "text":"…" } ]
  }
}
```

`transcript.segments[].index` is the stable address the downstream `trace{segment_index}` relies on, so it
must survive into the filled prompt.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether an unrecognized placeholder should hard-`raise` (chosen here) or be left
  untouched and merely reported. Raising best satisfies "no residual `{{…}}`" and catches drift early;
  confirm at the acceptance gate.
- [NEEDS CLARIFICATION] The precise transcript serialization (timestamp vs. raw seconds, delimiter) is
  provisional and will be reconciled with the Phase C2 prompt; it does not affect the placeholder contract.
