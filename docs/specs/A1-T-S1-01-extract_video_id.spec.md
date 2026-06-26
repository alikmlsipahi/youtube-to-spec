# Spec — `extract_video_id` (T-S1-01)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Reuse from the existing skill, §Functions). **No test code, no golden output tables here.**

## One-line purpose

Resolve any supported YouTube URL form — or a bare 11-character id — to the canonical 11-character
video id, raising on anything that is not recognizably a video reference.

## Signature

```python
def extract_video_id(url_or_id: str) -> str
```

Reuse mandate (plan §Reuse, lines 82): **copy verbatim** from
`.claude/skills/youtube-transcript/scripts/get_transcript.py` lines 19–29. The behavior below describes
exactly what that verbatim copy must do; it is not an invitation to re-derive a different algorithm.

## Inputs

- `url_or_id: str` — one of:
  - a full watch URL (`https://www.youtube.com/watch?v=<ID>`), possibly with extra query params
    (`&list=…`, `&index=…`, `&t=…`),
  - a short URL (`https://youtu.be/<ID>`),
  - an embed URL (`https://www.youtube.com/embed/<ID>`),
  - a legacy `/v/` URL (`https://www.youtube.com/v/<ID>`),
  - a bare 11-character id (`<ID>`),
  - host variants such as `m.youtube.com`, `http://` vs `https://`, and `www.`-less forms.

A YouTube **video id** is exactly 11 characters drawn from `[A-Za-z0-9_-]`.

## Expected behavior

1. Try, in order, two recognizers:
   - a URL recognizer that looks for one of the known prefixes
     (`youtube.com/watch?v=`, `youtu.be/`, `youtube.com/embed/`, `youtube.com/v/`) immediately followed
     by an 11-character id; and
   - a bare-id recognizer that matches the **whole** string as exactly 11 id-characters.
2. On the first recognizer that matches, return the captured 11-character id.
3. Because the URL recognizer captures the id sitting directly after `watch?v=`, a combined
   `watch?v=<ID>&list=<PLAYLIST>` URL resolves to the **video** id, not the playlist id. (Playlist-vs-video
   *routing* is `classify_input`'s job, T-S1-03; this function only ever returns a video id.)
4. If neither recognizer matches, raise `ValueError` whose message includes the offending input.

The function is pure: no I/O, no network, deterministic.

## Edge cases

- Bare id that is **not** 11 chars (too short or too long) → `ValueError` (the whole-string match is
  length-anchored).
- Empty string → `ValueError`.
- Non-YouTube URL (e.g. a Vimeo link) → `ValueError`.
- A watch URL whose id segment is shorter than 11 chars → `ValueError`.
- A bare 11-char id containing only the allowed character class (including `_` and `-`) is valid.
- Extra trailing query parameters after a valid id do not prevent a match.

## Acceptance scenarios (Given / When / Then)

- **Given** a standard watch URL, **when** called, **then** it returns the 11-char id embedded after `v=`.
- **Given** a `youtu.be`, `embed`, or `/v/` URL, **when** called, **then** it returns that id.
- **Given** a watch URL carrying both `v=` and `list=`, **when** called, **then** it returns the **video**
  id (the value after `v=`), ignoring the playlist.
- **Given** a bare valid 11-char id, **when** called, **then** it returns the id unchanged.
- **Given** a string that matches no recognizer (empty, wrong host, wrong length), **when** called,
  **then** it raises `ValueError`.

## Assumptions

- [ASSUMPTION] The recognizer set is exactly the four prefixes present in the reuse source; no additional
  forms (e.g. `youtube-nocookie.com`, `shorts/`) are required for Phase 1 — the plan mandates a *verbatim*
  copy, which does not include them.
- [ASSUMPTION] Matching is substring-based for URLs (as in the reuse source), so a host like
  `m.youtube.com/watch?v=` still matches because it contains `youtube.com/watch?v=`.

## Key entities (canonical schema excerpt)

The returned id populates `video.id` (and, via `video.url`, the canonical watch URL) in the per-video
artifact (`IMPLEMENTATION_PLAN_v2.md` §Canonical per-video JSON).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] None — behavior is fully pinned by the verbatim-copy mandate.
