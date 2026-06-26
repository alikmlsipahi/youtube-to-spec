# Spec — `render_markdown` (T-S1-08)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #5 `render_markdown(artifact)` — "metadata header + `[MM:SS]`/`[HH:MM:SS]` transcript via
> `format_timestamp`"; §Canonical per-video JSON; catalog row T-S1-08; capability "Relational integrity"
> — the readable view must still carry video↔collection identity). **No test code, no golden output
> tables here.**

## One-line purpose

Render one canonical per-video artifact dict into the human-readable Markdown view — a metadata header
(title, url, channel, collection) followed by the transcript as one `[<timestamp>] <text>` line per
segment, where the timestamp is produced by `format_timestamp(segment.start)` (`MM:SS` under one hour,
`HH:MM:SS` at/over one hour).

## Signature

```python
def render_markdown(artifact: dict) -> str
```

Pure and deterministic; no I/O, no network. It only reads the artifact and returns a string. It reuses
`format_timestamp` (T-S1-02) for every timestamp it prints.

## Inputs

- `artifact: dict` — a full per-video artifact as assembled elsewhere in the script, shaped per the
  canonical schema:
  - `artifact["video"]` — the `video{}` block (`build_video_block` output): reads `title`, `url`,
    `channel` for the header.
  - `artifact["collection"]` — the `collection{}` block **or `None`** for a true single. When present it
    carries `type`, `id`, `title`, `uploader`, `position`, `total_members`; the header shows its `title`.
  - `artifact["transcript"]` — the `transcript{}` block: reads `available` (bool) and `segments` (list of
    `{index, start, duration, end, text}`). Segments are already in time order with `index` from `0`.

## Expected behavior

Produce a Markdown document with two parts, in this order:

1. **Metadata header** — must surface, as readable Markdown, at least:
   - the video **title** (rendered as the top-level `# ` heading),
   - the video **url**,
   - the **channel**,
   - the **collection** — its title when `collection` is present; an explicit placeholder (e.g. `—`)
     when `collection is None` (true single). The collection line is always emitted so the view records
     whether a video belongs to a collection.
2. **Transcript section** — introduced by a `## Transcript` heading, then:
   - if `transcript["available"]` is true: **one line per segment, in segment order**, each formatted as
     `[<ts>] <text>` where `<ts> = format_timestamp(segment["start"])` and `<text>` is the segment's
     `text` reproduced **unchanged**;
   - if `transcript["available"]` is false (or there are no segments): no segment lines are emitted; a
     short human note (e.g. `_No transcript available._`) stands in instead.

Timestamp rules (delegated to `format_timestamp`, T-S1-02):
- A segment starting at `0` renders `[00:00]` — so the **first** transcript line of an available
  transcript begins with `[00:00]`.
- A segment with `start < 3600` renders `MM:SS` (e.g. `75.0 → [01:15]`).
- A segment with `start >= 3600` renders `HH:MM:SS` (e.g. `3600.0 → [01:00:00]`, `3665.0 → [01:01:05]`).

Segment `text` is never altered (no trimming, escaping, or whitespace normalization) — the JSON remains
the lossless artifact; the Markdown is a faithful view of it.

## Edge cases

- **`collection is None`:** the header still emits a collection line with a placeholder; the function must
  not raise on a missing collection.
- **Transcript unavailable:** `transcript["available"] == False` → header still rendered, transcript
  section present but carries the no-transcript note, **no** `[..]` lines.
- **Empty segment list** while `available` is true: treated like "no segment lines" (no `[..]` lines).
- **Long video crossing one hour:** segments before `3600s` use `MM:SS`, segments at/after use
  `HH:MM:SS`, within the same document.
- **Unicode / Turkish text and multi-line segment text** appear verbatim in the output.
- **Missing optional header values** (`channel` is `None`): the line is still emitted with whatever value
  is present (a placeholder/empty is acceptable); the function does not raise.

## Acceptance scenarios (Given / When / Then)

- **Given** an artifact with a populated `video{}`, a non-null `collection{}`, and an available
  transcript whose first segment starts at `0.0`, **when** `render_markdown` runs, **then** the output
  contains the title, url, channel, and collection title in its header, and its first transcript line
  begins with `[00:00]` followed by that segment's text.
- **Given** a transcript that includes a segment starting at `3665.0`, **when** rendered, **then** that
  segment's line begins with `[01:01:05]` (HH:MM:SS past one hour), while a segment starting at `75.0`
  renders `[01:15]` (MM:SS under one hour).
- **Given** an artifact whose `collection` is `None`, **when** rendered, **then** a collection line is
  still present (placeholder) and the function does not raise.
- **Given** an artifact whose `transcript["available"]` is `False`, **when** rendered, **then** the
  output has the header and a transcript section with no `[..]` timestamp lines.

## Assumptions

- [ASSUMPTION] The header uses Markdown: `# <title>` as the heading and labelled bullet/line entries for
  URL, channel, and collection. The plan fixes the *fields* the header must carry (title/url/channel/
  collection) but not the exact Markdown layout; the precise label text/spacing is an implementer detail
  and is **not** asserted byte-for-byte by the tests (they check that each field's value appears and that
  the transcript-line `[<ts>] <text>` shape and timestamp formatting hold).
- [ASSUMPTION] The transcript section is introduced by a `## Transcript` heading and each segment is one
  line `[<ts>] <text>`; this matches the plan's "`[MM:SS]`/`[HH:MM:SS]` transcript" description.
- [ASSUMPTION] When `collection is None`, an explicit placeholder (`—`) marks "standalone"; the plan does
  not name the placeholder string.
- [ASSUMPTION] `format_timestamp(segment["start"])` (not `end`) is the printed timestamp.

## Key entities (canonical schema excerpt)

```jsonc
"video": { "title","url","channel", ... },
"collection": { "type","id","title","uploader","position","total_members" }, // null for true singles
"transcript": {
  "available": true,
  "segments": [ { "index":0,"start":0.0,"duration":3.2,"end":3.2,"text":"…" } ]
}
```

The Markdown is the readable *view* of this artifact; relational integrity (which video, which
collection) must remain visible in it, mirroring the lossless JSON.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Exact Markdown skeleton (label wording, ordering of header lines, the
  no-transcript note string) is unspecified by the plan. This spec fixes the **required content and the
  transcript-line shape**; cosmetic layout is left to the implementer and is intentionally not pinned by
  the unit tests, to keep the blind barrier robust.
- [NEEDS CLARIFICATION] Whether chapters/tags/description belong in the Markdown header is unspecified;
  the catalog row pins only title/url/channel/collection, so this unit treats those four as the required
  header content and leaves richer header content optional.
