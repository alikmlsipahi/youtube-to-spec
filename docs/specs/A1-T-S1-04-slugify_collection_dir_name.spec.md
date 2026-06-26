# Spec — `slugify` / `collection_dir_name` (T-S1-04)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Locked decisions "File/manifest naming"; §Functions #7 "centralize all naming"; catalog row
> T-S1-04). **No test code, no golden output tables here.**

## One-line purpose

Turn a free-text collection/playlist title into a filesystem-safe, ASCII, hyphenated slug — correctly
transliterating Turkish characters — and compose the canonical per-collection directory name
`<slug>-<playlist_id>`.

## Signatures

```python
def slugify(title: str) -> str
def collection_dir_name(title: str, playlist_id: str) -> str
```

These are the **centralized** naming helpers (plan §Functions #7): any future layout change is a one-edit
change here.

## Inputs

- `title: str` — a human-authored playlist/collection title that may contain Turkish letters
  (`ı İ ş Ş ğ Ğ ü Ü ö Ö ç Ç`), uppercase/mixed case, runs of whitespace, punctuation, and digits.
- `playlist_id: str` — the YouTube playlist id (e.g. `PLabcdEFGH…`). It is an opaque identifier appended
  **verbatim** (its own casing preserved); it is **not** slugified.

## Expected behavior — `slugify`

Apply, in this exact order, a deterministic pipeline:

1. **Transliterate Turkish letters to ASCII** (both cases), per the map below.
2. **Lowercase** the whole string (safe now that Turkish letters are plain ASCII).
3. **Replace every run of whitespace** (spaces, tabs, newlines) with a single hyphen `-`.
4. **Remove every character** that is not a lowercase ASCII letter `a–z`, a digit `0–9`, or a hyphen `-`.
5. **Collapse** any run of consecutive hyphens into a single hyphen.
6. **Strip** leading and trailing hyphens.

Turkish transliteration map (rule, applied in step 1 — uppercase forms map to the same ASCII letter as
their lowercase counterpart because step 2 lowercases afterward):

| Turkish | ASCII | Turkish | ASCII |
|---|---|---|---|
| ı / I | i | ö / Ö | o |
| İ / i̇ | i | ç / Ç | c |
| ş / Ş | s | ü / Ü | u |
| ğ / Ğ | g |  |  |

The result is pure ASCII, lowercase, hyphen-separated, with no leading/trailing/double hyphens.

## Expected behavior — `collection_dir_name`

Return `slugify(title)` followed by a single hyphen and the **raw** `playlist_id`
(i.e. `"<slug>-<playlist_id>"`). The playlist id keeps its original casing and is not transformed; only
the title portion is slugified. This is the `data/<slug(title)>-<playlist_id>/` directory name from the
plan's §File layout.

Both functions are pure and deterministic; no I/O.

## Edge cases

- A title with the Turkish dotless `ı` or dotted `İ` must not produce a stray combining dot; the map
  yields plain `i` for both. (This is precisely why transliteration happens *before* `str.lower()`.)
- Multiple consecutive spaces collapse to a single hyphen (via steps 3 + 5).
- Leading/trailing whitespace produces no leading/trailing hyphen in the result (step 6).
- Punctuation (`#`, `:`, `!`, `?`, etc.) is dropped; surrounding hyphens that would otherwise double up
  are collapsed.
- Digits are preserved.
- `playlist_id` is appended exactly as given — its uppercase `PL…` prefix is **not** lowercased.

## Acceptance scenarios (Given / When / Then)

- **Given** a title containing Turkish letters, **when** slugified, **then** each Turkish letter is
  replaced by its ASCII equivalent per the map and the whole result is lowercase ASCII.
- **Given** a title with internal multiple spaces, **when** slugified, **then** they become a single
  hyphen.
- **Given** a title with leading/trailing whitespace, **when** slugified, **then** the result has no
  leading or trailing hyphen.
- **Given** a title with punctuation, **when** slugified, **then** the punctuation is removed and no
  doubled hyphens remain.
- **Given** a title and a playlist id, **when** `collection_dir_name` is called, **then** the result is
  the slug, a hyphen, and the playlist id with its original casing intact.

## Assumptions

- [ASSUMPTION] The output slug is **lowercase**. The plan specifies Turkish→ASCII and spaces→`-` but not
  casing; lowercase is the conventional slug form and is adopted here.
- [ASSUMPTION] Non-Turkish, non-ASCII characters (e.g. accented Latin `é`, `ñ`, emoji) are simply dropped
  by step 4 rather than transliterated; only the Turkish set has an explicit mapping. Such inputs are out
  of the tested scope.
- [ASSUMPTION] The separator between slug and playlist id is a single hyphen, matching
  `<slug(title)>-<playlist_id>` in the plan's file-layout diagram.

## Key entities (canonical schema excerpt)

`collection_dir_name` produces the on-disk folder `data/<slug>-<playlist_id>/` that holds
`_manifest.json` + per-video `<video_id>.json` / `.md` (plan §File layout). The slug also feeds the
human-readable identity of a `collection{}` block whose `id` is the raw playlist id.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether an all-symbol title that slugifies to the empty string should fall back to
  a placeholder (e.g. the playlist id alone). Not exercised in Phase 1; assumed not to occur for real
  playlist titles.
