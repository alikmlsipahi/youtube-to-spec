# Spec — `parse_response` / `render_markdown` (T-S2-03)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 — OpenAI engine "requests **structured JSON output**, then **renders Markdown from it**";
> §Skill 2 Output — "Doc = source header (video url/title/channel/collection) + mini-summary +
> Module→Feature→Requirements (each requirement: `id`=`<MODULE>-<FEATURE>-<NNN>`, `text`,
> `source_video_id`, `trace{timestamp,segment_index}`) + Assumptions & Open Questions. JSON mirrors the
> doc."; catalog row T-S2-03 "captured json_schema response → Markdown (REQ ids + trace) and mirrored
> JSON"; §Acceptance — "Engine-agnostic output: Claude-native and OpenAI engines emit the same shape").
> **No test code, no golden output tables here.**

## One-line purpose

Turn a captured OpenAI **json_schema** chat-completion response into (a) the canonical structured
requirements **document object** (the "mirrored JSON" that is stored alongside the artifact) and (b) a
human-readable **Markdown** view of that same document — losslessly preserving requirement ids, traces,
and the source header.

## Signatures

```python
def parse_response(response) -> dict
def render_markdown(doc: dict, artifact: dict | None = None) -> str
```

Both are pure and deterministic: no network, no file I/O, no OpenAI call. The caller performs the OpenAI
request and passes the *returned response object* into `parse_response`; the parsed document is then
handed to `render_markdown`. The dict that `parse_response` returns **is** the JSON that the engine
persists (`<video_id>.requirements.json`) — i.e. the JSON and the Markdown are two views of one document,
satisfying the "JSON mirrors the doc" and "engine-agnostic same shape" requirements.

## Inputs

- `response` — the object returned by an OpenAI chat-completion call made with a `json_schema` /
  structured-output response format. Its assistant message carries the model's answer as a **JSON
  string** at `response.choices[0].message.content`. The model may instead refuse, in which case the
  content is absent/`None` (and/or a `refusal` field is set).
- `doc: dict` — the structured requirements document (the object `parse_response` returns). Shape under
  "Key entities" below.
- `artifact: dict | None` — one canonical Skill 1 `<video_id>.json` object, used **only** to populate the
  source header (video url/title/channel + collection title) deterministically. When `None`, the header
  is drawn from the document's own optional `source{}` block.

## The structured document shape (the contract)

`parse_response` returns, and `render_markdown` consumes, a document of this shape:

```jsonc
{
  "summary": "one short paragraph",
  "modules": [
    {
      "code": "REG",                 // <MODULE> — 3–6 uppercase
      "title": "Kayıt Modülü",       // optional human label
      "features": [
        {
          "code": "ADD-STU",         // <FEATURE> — ACTION or ACTION-ENTITY
          "title": "Öğrenci Ekleme", // optional human label
          "requirements": [
            {
              "id": "REG-ADD-STU-001",          // <MODULE>-<FEATURE>-<NNN>
              "text": "…requirement statement…",
              "source_video_id": "EXAMPLE1234",
              "trace": { "timestamp": "00:03", "segment_index": 1 }
            }
          ]
        }
      ]
    }
  ],
  "assumptions": [ "…" ],
  "open_questions": [ "…" ]
}
```

## Expected behavior — `parse_response`

1. Extract the assistant message text from `response.choices[0].message.content` and `json.loads` it,
   returning the resulting `dict`.
2. The returned object is the canonical structured document (the "mirror"): no information from the
   model's JSON is dropped — keys/values round-trip intact.
3. Raise a **clear, non-leaking** error (e.g. `ValueError`) when the response cannot yield a document:
   - no `choices` (empty list / missing),
   - the assistant message content is absent or `None` (e.g. a refusal),
   - the content string is **not valid JSON**.
   The error message describes the failure ("empty/no content", "invalid JSON") and never embeds an API
   key or other secret.
4. Never performs I/O or a network call; never mutates `response`.

## Expected behavior — `render_markdown`

1. Render a Markdown document containing, in order:
   - a **source header** — the video **title**, **url**, **channel**, and the **collection** label, taken
     from `artifact` when supplied (else from `doc["source"]`);
   - a **mini-summary** — `doc["summary"]`;
   - the **Module → Feature → Requirements** hierarchy: for each module its code (and optional title),
     for each feature its code (and optional title), and for each requirement its **`id`**, its **text**,
     and its **trace** (`timestamp` and `segment_index`) so a reader can locate the originating segment;
   - an **Assumptions** section listing `doc["assumptions"]`;
   - an **Open Questions** section listing `doc["open_questions"]`.
2. Every requirement `id` and every requirement `text` from `doc` appears verbatim in the output. Trace
   `timestamp` and `segment_index` values appear for each requirement.
3. Returns a `str`. Pure; never mutates `doc` or `artifact`.
4. Defensive: missing optional fields (no `title`, empty `assumptions`/`open_questions`, missing
   `trace`) degrade gracefully — no exception, no literal `None` text.

## Edge cases

- **Refusal / empty content** → `parse_response` raises a clear error (not a silent empty dict).
- **Malformed JSON content** → `parse_response` raises a clear error.
- **Empty `choices`** → `parse_response` raises a clear error.
- **`doc` with multiple modules / multiple features / multiple requirements** → all are rendered; order
  preserved.
- **`artifact` is `None`** → `render_markdown` falls back to `doc["source"]` for the header and still
  renders.
- **Empty `assumptions` / `open_questions`** → the sections render without error (may be empty/"none").
- **Requirement text containing Markdown/brace characters** → reproduced verbatim (no escaping that
  alters the text).
- **A requirement missing its `trace`** → rendered without crashing (trace omitted or shown empty).

## Acceptance scenarios (Given / When / Then)

- **Given** a captured json_schema response whose content is a valid document JSON, **when**
  `parse_response` runs, **then** it returns a dict equal to that document (round-trips losslessly).
- **Given** a response with no `choices`, **when** `parse_response` runs, **then** it raises a clear
  error.
- **Given** a response whose message content is `None` (a refusal), **when** `parse_response` runs,
  **then** it raises a clear error that does not leak any secret.
- **Given** a response whose content is not valid JSON, **when** `parse_response` runs, **then** it raises
  a clear error.
- **Given** a parsed document and the source artifact, **when** `render_markdown` runs, **then** the
  video title, url, channel and collection title all appear in the output.
- **Given** that document, **when** rendered, **then** every requirement `id` and `text` appears, and each
  requirement's trace `timestamp` and `segment_index` appear.
- **Given** that document, **when** rendered, **then** the summary text, every assumption, and every open
  question appear.
- **Given** `artifact=None` but a `doc["source"]` block, **when** rendered, **then** the header still
  shows the source fields and no exception is raised.

## Assumptions

- [ASSUMPTION] `parse_response` reads the **response object** via attribute access
  (`response.choices[0].message.content`), matching the OpenAI SDK return shape; the engine, not this
  unit, decides the request parameters. (Captured fixtures emulate this object shape.)
- [ASSUMPTION] The structured-output content is a **JSON string** inside the assistant message (the
  json_schema/json_object convention), not a pre-parsed object.
- [ASSUMPTION] The document shape under "Key entities" is the contract for *both* engines; the plan names
  the required fields (`id`, `text`, `source_video_id`, `trace{timestamp,segment_index}`, summary,
  Module→Feature→Requirements, Assumptions & Open Questions) but not the exact container keys — the names
  `modules`/`features`/`requirements`/`code`/`assumptions`/`open_questions`/`summary` are fixed here so
  the Phase C2 prompt's `json_schema` and this renderer agree.
- [ASSUMPTION] The "mirrored JSON" stored on disk **is** `parse_response`'s return value (optionally with
  the source header injected by the engine); the Markdown is derived from the same object — so there is no
  separate "build JSON" unit.
- [ASSUMPTION] The source header is taken from the **artifact** when available (relational integrity,
  determinism) and falls back to `doc["source"]` otherwise.
- [ASSUMPTION] The exact Markdown layout (heading levels, bullet vs. table) is the implementer's choice;
  the load-bearing requirement is that ids, texts, traces, summary, assumptions and open questions are all
  present and readable.

## Key entities (canonical schema excerpts)

Response envelope this unit reads from:

```jsonc
{ "choices": [ { "message": { "role": "assistant", "content": "<JSON string of the document>" } } ] }
```

Source header fields pulled from the artifact:

```jsonc
{
  "video": { "id","url","title","channel", … },
  "collection": { "title", … } | null
}
```

Document shape: see "The structured document shape" above. `requirement.id` must conform to the locked
`<MODULE>-<FEATURE>-<NNN>` scheme (validated separately by T-S2-04); `requirement.trace.segment_index`
ties back to `transcript.segments[].index` from Skill 1.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether `parse_response` should also tolerate a **dict-shaped** response (already
  `model_dump()`-ed) in addition to the SDK object. This spec fixes the object shape; a dual-shape read
  can be added without breaking the contract if a later caller needs it.
- [NEEDS CLARIFICATION] Whether the engine injects the source header into the stored JSON (so the JSON is
  fully self-describing) or leaves it only in the Markdown view. Either is compatible; confirm at the
  A-03 acceptance gate.
- [NEEDS CLARIFICATION] Exact `trace.timestamp` format (`MM:SS` vs raw seconds). The renderer reproduces
  whatever the document carries; reconciled with the Phase C2 prompt at A-03.
