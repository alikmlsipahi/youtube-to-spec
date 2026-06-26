---
name: feature-requirement-extractor
description: >-
  Turn already-extracted YouTube artifacts (the JSON produced by the
  youtube-artifact-collector skill) into a structured Module→Feature→Requirement
  document, with each requirement traced back to a transcript segment. Use when
  the user wants requirement extraction, feature/product discovery, business-rule
  extraction, or a spec/requirements document FROM existing artifacts — e.g.
  "extract requirements from this artifact", "what features does this video
  demonstrate", "build a requirements doc from this collection". Runs offline by
  default (Claude-native, no API key); an optional OpenAI engine is available via
  `--engine openai`. This consumes Skill 1 JSON, not URLs — it does not download
  videos or transcripts.
---

# feature-requirement-extractor

Skill 2 of the YouTube intelligence pipeline — a **consumption-layer** analysis.
It reads the lossless artifacts produced by `youtube-artifact-collector` (Skill 1)
and produces a **Module → Feature → Requirement** document. It never touches
YouTube; the only input is artifact JSON, and the only coupling to Skill 1 is the
artifact's `schema_version` (read defensively).

## When to use this skill

Use it when the request is to **analyze already-collected artifacts**:

- "Extract the requirements from this artifact."
- "What features and business rules does this video/collection demonstrate?"
- "Build a requirements/spec document from this collection."

If the user instead wants to *collect* metadata/transcripts from URLs or a
playlist, that is Skill 1 (`youtube-artifact-collector`), not this skill.

## Engines

This skill ships two interchangeable engines that **emit the same output shape**:

- **`claude` (default, offline)** — no script runs. You (Claude) read the artifact
  and the external prompt/template files in-chat and produce the document. No API
  key required.
- **`openai`** — runs `scripts/extract_requirements.py`, which calls the OpenAI
  API. Selected with `--engine openai`; needs `OPENAI_API_KEY` (see
  `.env.example`).

The prompts and template are **external and swappable** — editing them changes the
output for *both* engines without any code change.

## Inputs

Either:

- a single artifact file — `<video_id>.json` produced by Skill 1, or
- a **collection folder** — a directory containing `_manifest.json`; process each
  member whose `status` is `ok` (in manifest order), using the manifest for
  module/collection context.

## Claude-native engine — how to run it (default)

When asked to extract requirements with the default engine, do this in-chat:

1. **Resolve the input.** If given a `<video_id>.json`, use it directly. If given
   a collection folder, read its `_manifest.json` and process every member with
   `status: ok`, in order; the manifest also gives the collection/module title.
2. **Read the artifact JSON.** Pull the `video{}` block (id, title, url, channel,
   description), the `collection{}` block (module/collection title), and the
   `transcript.segments[]` (each with its stable `index`, `start`, and verbatim
   `text`). Treat transcript text as read-only — never edit it.
3. **Read the prompt files** at runtime (this is what makes them swappable):
   - `prompts/system_prompt.md` — the analyst role, the strict output JSON
     contract, and the `<MODULE>-<FEATURE>-<NNN>` id rules.
   - `prompts/extraction_prompt.md` — the task instructions, the
     `{{placeholders}}` for the artifact data, and the **module/action code
     lookup table**.
4. **Fill the prompt** by substituting the artifact values for the placeholders
   (`{{video_id}}`, `{{video_title}}`, `{{video_url}}`, `{{channel}}`,
   `{{description}}`, `{{collection_title}}`, `{{transcript}}`).
5. **Produce the structured document** following the system-prompt contract:
   `summary`, `modules[] → features[] → requirements[]` (each requirement with
   `id` = `<MODULE>-<FEATURE>-<NNN>`, `text`, `source_video_id`, and a
   `trace{timestamp, segment_index}`), plus `assumptions` and `open_questions`.
   Number requirements **video-locally from `001`**; never embed the video id in
   an `id`.
6. **Render and save.** Format the document using
   `templates/requirement_doc.md` and write `<video_id>.requirements.md` plus a
   mirrored `<video_id>.requirements.json` alongside the source artifact (same
   collection folder or `_singles/`), unless the user asks to print instead.

## OpenAI engine — how to run it (optional)

```bash
uv run .claude/skills/feature-requirement-extractor/scripts/extract_requirements.py \
  <artifact.json | collection_dir> --engine openai [flags]
```

It loads the **same** `prompts/` and `templates/` files, fills the placeholders,
calls OpenAI requesting structured JSON output, and renders the same document
shape. Configuration precedence is **CLI flag > env var > built-in default**.

| Flag | Env var | Default | Meaning |
| --- | --- | --- | --- |
| `--engine claude\|openai` | — | `claude` | Engine selector. |
| `--model NAME` | `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model. |
| `--temperature T` | `OPENAI_TEMPERATURE` | `0.2` | Sampling temperature. |
| `--max-tokens N` | `OPENAI_MAX_TOKENS` | `4096` | Max completion tokens. |
| `--response-format json_schema\|text` | `OPENAI_RESPONSE_FORMAT` | `json_schema` | Structured-output mode. |
| `--timeout S` | `OPENAI_TIMEOUT` | `60` | Request timeout (seconds). |
| `--retries N` | `OPENAI_RETRIES` | `3` | Retry attempts. |
| `--concurrency N` | `OPENAI_CONCURRENCY` | `4` | Parallel requests across members. |
| `--out-dir NAME` | — | alongside source | Override the output directory. |
| `--no-save` / `--print` | — | off | Print instead of writing files. |

The key is read from a `.env` in the working directory (then process env); copy
`.env.example` to `.env` and set `OPENAI_API_KEY`. A missing key fails with a
clear, secret-safe error.

## Output

`<video_id>.requirements.md` + `<video_id>.requirements.json` (the JSON mirrors
the document). The document = source header (title / url / channel / collection)
+ summary + Module→Feature→Requirements (with per-requirement traces) +
Assumptions + Open Questions.

## Swapping the analysis

Because the prompt and template files are read at runtime, switching the analysis
task (e.g. business-rule extraction, product discovery, a different doc style, or
a different module/action code scheme) is done by **editing
`prompts/extraction_prompt.md` / `prompts/system_prompt.md` /
`templates/requirement_doc.md`** — no code change, and the change applies to both
engines.
