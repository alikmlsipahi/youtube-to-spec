# Spec — `build_video_block` (T-S1-05)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Canonical per-video JSON — the `video{}` block; §Functions #3 `fetch_metadata`; catalog row
> T-S1-05; capability "Metadata collection"). **No test code, no golden output tables here.**

## One-line purpose

Project a captured yt-dlp `--dump-json` metadata dict down to the canonical, fixed-shape `video{}`
block of the per-video artifact — mapping/renaming the relevant yt-dlp fields, tolerating any missing
optional field, and guaranteeing a usable `url`.

## Signature

```python
def build_video_block(meta: dict) -> dict
```

Pure and deterministic; no I/O, no network. `meta` is the parsed JSON object that
`fetch_metadata(video_id)` (plan §Functions #3) returns from `yt-dlp --skip-download --dump-json`.

## Inputs

- `meta: dict` — a parsed yt-dlp per-video JSON object. It always carries `id`. Every other field is
  **optional** and may be absent. Relevant source keys (yt-dlp names) this function reads:
  - `id` (str, 11-char video id) — assumed always present.
  - `webpage_url` (str) — canonical watch URL.
  - `title` (str).
  - `channel` (str), `channel_id` (str), `uploader` (str).
  - `upload_date` (str, `YYYYMMDD`).
  - `duration` (number, seconds).
  - `description` (str, may contain newlines).
  - `tags` (list[str]), `categories` (list[str]).
  - `chapters` (list of `{start_time, end_time, title}` or `null`).
  - `language` (str | null) — the video's default language.
  - `availability` (str, e.g. `"public"`).
  - yt-dlp emits many other keys (e.g. `view_count`, `thumbnails`, …) that this function does **not**
    place into the canonical block.

## Expected behavior

Return a dict whose keys are **exactly** the canonical `video{}` keys, in this set:

```
id, url, title, channel, channel_id, uploader, upload_date,
duration_seconds, description, tags, categories, chapters,
default_language, availability
```

Field-by-field rules:

- **Same-named pass-through** (`id`, `title`, `channel`, `channel_id`, `uploader`, `upload_date`,
  `description`, `tags`, `categories`, `chapters`, `availability`): take the source value **when the key
  is present** (even if the value is falsy/empty, e.g. `0`, `[]`, `""`, `null`), otherwise `None`. In
  other words, use `dict.get(key)` semantics — *absent* maps to `None`, *present-but-empty* is preserved
  as-is.
- **Renamed fields:**
  - `duration_seconds` ← source `duration` (same get-semantics; absent → `None`).
  - `default_language` ← source `language` (absent → `None`).
- **`url` (guaranteed non-null):** if source `webpage_url` is present and non-empty, use it **verbatim**;
  otherwise construct the canonical watch URL `https://www.youtube.com/watch?v=<id>` from the video id.
- The block carries **only** the canonical keys above. Extra yt-dlp keys present in `meta`
  (`view_count`, etc.) are **not** copied into the block.

Values are passed through without transformation (no trimming, no type coercion, no date reformatting);
only the renames and the `url` fallback alter the source.

## Edge cases

- **Minimal input** (`{"id": ..., "title": ...}` only): every other canonical key is `None`, and `url`
  is constructed from `id`.
- **Missing `webpage_url`:** `url` falls back to the constructed watch URL; an empty-string
  `webpage_url` also triggers the fallback.
- **Present-but-falsy values:** `duration: 0`, `tags: []`, `description: ""` are preserved exactly
  (not converted to `None`).
- **`chapters: null` / `language: null`** present in source: preserved as `None` (indistinguishable from
  absent, which is acceptable).
- **Extra/unknown yt-dlp fields:** ignored — they never appear in the canonical block.

## Acceptance scenarios (Given / When / Then)

- **Given** a full yt-dlp dict with all relevant fields plus extra unknown fields, **when**
  `build_video_block` runs, **then** the result has exactly the canonical keys with the renamed fields
  (`duration_seconds`, `default_language`) populated and the extra fields absent.
- **Given** a dict missing `webpage_url`, **when** the block is built, **then** `url` is
  `https://www.youtube.com/watch?v=<id>`.
- **Given** a dict containing only `id` and `title`, **when** the block is built, **then** all other
  canonical keys are `None` and `url` is constructed from `id`.
- **Given** a dict with `duration: 0` and `tags: []`, **when** the block is built, **then**
  `duration_seconds` is `0` and `tags` is `[]` (falsy values preserved, not nulled).

## Assumptions

- [ASSUMPTION] `url` maps from yt-dlp's `webpage_url` (the field name yt-dlp uses for the canonical watch
  URL); the plan's schema names the canonical key `url` but does not name its source.
- [ASSUMPTION] `duration_seconds` ← `duration` and `default_language` ← `language` are the intended
  renames; the plan lists the canonical key names but not the yt-dlp source names.
- [ASSUMPTION] The constructed fallback URL form is `https://www.youtube.com/watch?v=<id>`.
- [ASSUMPTION] `id` is always present in `meta` (yt-dlp guarantees it); the function does not specially
  handle a missing `id`.

## Key entities (canonical schema excerpt)

```jsonc
"video": { "id","url","title","channel","channel_id","uploader",
           "upload_date","duration_seconds","description","tags",
           "categories","chapters","default_language","availability" }
```

This block is one node of the per-video artifact (`schema_version: "1.0"`, `kind: "video_artifact"`).
`schema_version` + the nested shape let roadmap artifact types be added as siblings without rework.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] The capability-level acceptance note "unknown-but-present yt-dlp fields
  preserved" is **not** satisfied inside this fixed-shape block. This spec follows the catalog row
  (T-S1-05: "canonical `video{}` keys; missing optional fields tolerated"), which enumerates a closed key
  set. Lossless retention of the full raw yt-dlp object, if required, is assumed to live at a higher level
  (e.g. an as-stored raw metadata field) outside `build_video_block`, and is out of scope for this unit.
