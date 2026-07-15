# Spec — `parse_hidden_unavailable` (T-S1-10)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #2 `enumerate_playlist` — "`hidden_unavailable_count` parsed from stderr WARNING";
> §Grounding — yt-dlp reports the hidden-unavailable count on stderr; catalog row T-S1-10;
> capability "Graceful degradation" — the hidden-unavailable count is captured).
> *(Provenance corrected 2026-07-15: this header used to quote §Grounding's "yt-dlp **omits** the 5
> hidden unavailable videos from the flat list", which was measured false — they are listed, with a
> null title. This unit only parses stderr, so its behavior is unaffected; only the quoted rationale
> was wrong. See T-S1-15 `enumerate_playlist`.)*
> **No test code, no golden output tables here.**

## One-line purpose

Parse yt-dlp's stderr text and return the number of unavailable videos that yt-dlp hid from a playlist's
flat listing — extracting the integer `N` from its WARNING line, or `0` when no such warning is present.

## Signature

```python
def parse_hidden_unavailable(stderr: str) -> int
```

Pure and deterministic; no I/O, no network. Operates purely on the captured stderr string from the
`enumerate_playlist` subprocess call.

## Inputs

- `stderr: str` — the full standard-error text captured from the
  `yt-dlp --flat-playlist --dump-single-json …` subprocess. It may be empty, may contain unrelated
  warnings/log lines, or may contain the hidden-unavailable WARNING somewhere among many lines. When a
  playlist hides unavailable (private/deleted) videos, yt-dlp emits a WARNING line stating how many.

## Expected behavior

- Search `stderr` for the WARNING that reports hidden unavailable videos. yt-dlp phrases it as a count
  immediately followed by the words "unavailable videos" (e.g. "There are **5 unavailable videos** that
  are hidden from this list" / "**5 unavailable videos** are hidden"). Extract that integer count and
  return it as an `int`.
- If no such warning appears anywhere in `stderr` (including the empty-string case and the
  unrelated-warnings-only case), return `0`.
- If the warning appears more than once, return the count from the **first** occurrence.

The function only reads — it never raises on unexpected/empty input; the worst case degrades to `0`.

## Edge cases

- **Warning present, single digit:** `"… 5 unavailable videos …"` → `5`.
- **Warning present, multi-digit:** `"… 12 unavailable videos …"` → `12`.
- **No warning / empty string:** `""` → `0`; stderr with only unrelated warnings → `0`.
- **Warning embedded among many other stderr lines:** still found and parsed.
- **Count of zero phrased explicitly** (unlikely from yt-dlp, which omits the line when none are hidden):
  if literally present as `"0 unavailable videos"`, returns `0` — indistinguishable from "absent", which
  is acceptable.
- **First-occurrence rule:** if two such lines appear, the first count wins.

## Acceptance scenarios (Given / When / Then)

- **Given** a multi-line stderr containing a WARNING that 5 unavailable videos are hidden, **when**
  `parse_hidden_unavailable` runs, **then** it returns `5`.
- **Given** a stderr with a two-digit count (e.g. 12), **when** parsed, **then** it returns `12`.
- **Given** a stderr with no hidden-unavailable warning (other warnings or empty), **when** parsed,
  **then** it returns `0`.

## Assumptions

- [ASSUMPTION] The number to extract is the integer that immediately precedes the phrase "unavailable
  videos" in the WARNING; this matches yt-dlp's real phrasing. The match is robust to surrounding text
  ("There are N unavailable videos that are hidden …" and "N unavailable videos are hidden" both parse).
- [ASSUMPTION] Matching is line/substring-based over the whole stderr string; the literal token
  `WARNING:` need not be required for a match (the count + "unavailable videos" phrase is the anchor), so
  minor yt-dlp wording changes still parse.
- [ASSUMPTION] Return type is a plain `int`; absence maps to `0` (not `None`), matching the manifest's
  `hidden_unavailable_count` field which is always an integer.

## Key entities (canonical schema excerpt)

```jsonc
// _manifest.json → collection{}
"collection": { "type","id","title","uploader","source_url","hidden_unavailable_count" }
```

`hidden_unavailable_count` is the field this value populates; it lets a downstream consumer know the
playlist had more members than the flat listing returned (graceful-degradation visibility).

## NEEDS CLARIFICATION

- [RESOLVED 2026-07-15] The exact yt-dlp wording can vary by version. This spec anchors on the
  `<N> unavailable videos` phrase (the stable part). If a future yt-dlp drops that phrasing, the parser
  would return `0` and the count would be silently lost — acceptable for Phase 1, noted for the
  integration tier (I-02 verifies the count against a live playlist).

  **The predicted drift has since happened, and the anchor held.** This tier's fixture wording is
  `"There are 5 unavailable videos that are hidden from this list."`; current yt-dlp emits
  `"YouTube said: INFO - 5 unavailable videos are hidden"` — a different sentence that still contains
  the anchor, so both parse to `5`. The anchor choice was right.

  I-02 is now an automated gate (`tests/integration/test_skill1_playlist.py`), where it was previously
  only a prose prompt — i.e. this deferral pointed at a gate that did not exist, and the drift above
  went unnoticed for a year. The gate asserts `hidden_unavailable_count > 0` rather than `== 5`: the
  count is upstream data that changes when the channel does, whereas *the parse still firing on real
  stderr* is what this unit owns and what silent loss would look like.
