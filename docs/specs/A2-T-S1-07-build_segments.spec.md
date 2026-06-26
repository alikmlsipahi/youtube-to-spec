# Spec — `build_segments` (T-S1-07)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #4 `fetch_transcript` "segments `{index,start,duration,end,text}`. **Never modify
> transcript text.**"; §Canonical per-video JSON — `transcript.segments`; §Grounding "Segment
> addressability is load-bearing", `03_ROADMAP.md:53`; catalog row T-S1-07). **No test code, no golden
> output tables here.**

## One-line purpose

Convert the raw fetched transcript snippets into the canonical, addressable segment list — assigning each
a stable zero-based `index`, computing `end = start + duration`, and carrying the snippet text through
**byte-for-byte unchanged**.

## Signature

```python
def build_segments(snippets) -> list[dict]
```

Pure and deterministic; no I/O, no network.

## Inputs

- `snippets` — an ordered list of **snippet objects** as returned by the transcript fetch
  (`youtube-transcript-api` v1.x `FetchedTranscript.snippets`). Each snippet object exposes:
  - `.start: float` — start time in seconds.
  - `.duration: float` — duration in seconds.
  - `.text: str` — the caption text for this snippet (may contain leading/trailing spaces, embedded
    newlines, Unicode/Turkish characters, or be empty).

## Expected behavior

Return a list with **one dict per input snippet, in the same order**. For the snippet at position `i`
(counting from `0`), emit a dict with exactly these keys:

```
{ "index":   i,                         # zero-based position, stable addressable id
  "start":    <snippet.start>,          # passed through unchanged
  "duration": <snippet.duration>,       # passed through unchanged
  "end":      <snippet.start + snippet.duration>,   # computed sum
  "text":     <snippet.text> }          # byte-identical to the source; NEVER modified
```

Rules:

- `index` starts at `0` and increments by `1`, matching list order; it is the stable address that future
  artifact types (per `03_ROADMAP.md:53`) reference.
- `start` and `duration` are copied through **without** rounding, coercion, or reformatting.
- `end` is the arithmetic sum `start + duration` (ordinary float addition).
- `text` is copied **exactly** — no stripping, normalization, collapsing of whitespace, escaping, or any
  edit whatsoever. Whitespace, newlines, empty strings, and non-ASCII characters survive verbatim.
- An empty `snippets` input yields an empty list `[]`.

## Edge cases

- **Empty input:** `[]` in → `[]` out.
- **Empty / whitespace-only text:** `""` and `"  spaced  "` are preserved unchanged.
- **Embedded newline in text:** preserved (e.g. `"line one\nline two"` stays two-line).
- **Unicode / Turkish text:** preserved byte-for-byte (`"kayıt ekranı"`).
- **Zero duration:** `duration == 0.0` yields `end == start`.
- **Ordering:** output order strictly follows input order; `index` is positional, never re-sorted by
  time.

## Acceptance scenarios (Given / When / Then)

- **Given** a list of three snippets, **when** `build_segments` runs, **then** the output has three dicts
  with `index` `0, 1, 2` in input order.
- **Given** a snippet with `start=1.5, duration=2.0`, **when** built, **then** that segment has
  `end=3.5`.
- **Given** a snippet whose text has leading/trailing spaces and an embedded newline, **when** built,
  **then** the segment's `text` equals the source text exactly.
- **Given** a snippet with `duration=0.0`, **when** built, **then** `end` equals `start`.
- **Given** an empty snippet list, **when** built, **then** the result is `[]`.

## Assumptions

- [ASSUMPTION] `build_segments` receives the **list of snippet objects** (i.e. the `.snippets` of a
  fetched transcript), not the fetched-transcript wrapper itself.
- [ASSUMPTION] Snippet objects expose `.start`, `.duration`, `.text` (the `youtube-transcript-api` v1.x
  snippet attribute names, consistent with `get_transcript.py`'s reuse pattern).
- [ASSUMPTION] `end` is the plain float sum `start + duration` with no rounding; callers needing exact
  display formatting handle that separately (`format_timestamp`).

## Key entities (canonical schema excerpt)

```jsonc
"transcript": {
  ...
  "segment_count": 60,
  "segments": [ { "index":0,"start":0.0,"duration":3.2,"end":3.2,"text":"…" } ]
  // index = stable addressable id
}
```

`transcript.segments[].index` is the stable address `03_ROADMAP.md:53` requires for future screenshot /
derived artifacts to reference a specific transcript segment.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] `transcript.segment_count` (the count of segments) is part of the surrounding
  `transcript{}` block assembled by `fetch_transcript`, not produced by `build_segments`; this unit emits
  only the `segments` list.
