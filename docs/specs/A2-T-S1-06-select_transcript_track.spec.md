# Spec — `select_transcript_track` (T-S1-06)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #4 `fetch_transcript`; §Canonical per-video JSON — the `transcript.selected` and
> `transcript.available_tracks` blocks; §Locked decisions "Transcript language"; catalog row T-S1-06).
> **No test code, no golden output tables here.**

## One-line purpose

From the list of transcript tracks a video offers, pick the single best track per a language-preference
list — preferring a **manually-created** track over an **auto-generated** one within the same language,
falling back to the first available track when no preferred language matches — and return both the
chosen track and the structured selection/inventory metadata.

## Signature

```python
def select_transcript_track(tracks, langs):
    # returns (selected_track, info)
```

Pure and deterministic; no I/O, no network. This is the selection logic factored out of
`fetch_transcript(video_id, langs)` (plan §Functions #4); the caller fetches `selected_track` separately.

## Inputs

- `tracks` — an ordered list of **track objects** (as enumerated from
  `YouTubeTranscriptApi().list(video_id)`), in the order the source lists them. Each track object exposes
  these attributes:
  - `.language_code: str` — e.g. `"tr"`, `"en"` (the short code).
  - `.language: str` — the human-readable language name, e.g. `"Turkish"`,
    `"Turkish (auto-generated)"`.
  - `.is_generated: bool` — `True` for auto-generated captions, `False` for manually-created.
  - `.is_translatable: bool`.
- `langs: list[str]` — an ordered language-code preference list (default at the call site is
  `["tr", "en"]`). Earlier entries are more preferred.

## Expected behavior

**1. Build the full inventory.** Map **every** input track, in input order, to an
`available_tracks` entry:

```
{ "language": <track.language_code>, "name": <track.language>,
  "is_generated": <track.is_generated>, "is_translatable": <track.is_translatable> }
```

(Note the field rename: inventory `language` ← `language_code`, inventory `name` ← `language`.)

**2. Select one track**, using this preference algorithm (language order is primary; within a language,
manual is preferred over auto):

- For each `lang` in `langs`, in order:
  1. If a track exists with `language_code == lang` **and** `is_generated == False` (manual), select it.
  2. Otherwise, if a track exists with `language_code == lang` **and** `is_generated == True` (auto),
     select it.
  3. Otherwise continue to the next `lang`.
- If no `lang` produced a match, **fall back** to the **first** track in `tracks` (input order).
- If `tracks` is empty, there is no selection.

When several tracks tie for a step (e.g. two manual `tr` tracks), the **first** such track in input
order wins.

**3. Build the `selected` descriptor** for the chosen track:

```
{ "language": <track.language_code>,
  "language_name": <track.language>,
  "type": "auto" if track.is_generated else "manual",
  "is_generated": <track.is_generated> }
```

**4. Return** the 2-tuple `(selected_track, info)`:

- `selected_track` — the chosen **track object** itself (so the caller can fetch it), or `None` when
  `tracks` is empty.
- `info` — a dict with exactly two keys:
  - `"selected"` — the `selected` descriptor dict above, or `None` when `tracks` is empty.
  - `"available_tracks"` — the inventory list from step 1 (an empty list when `tracks` is empty).

## Edge cases

- **Manual preferred over auto regardless of inventory order:** if an auto `tr` track is listed *before*
  a manual `tr` track, the manual one is still selected (type is the primary tiebreak within a language).
- **Language order beats track type:** with `langs = ["tr", "en"]`, an auto `tr` track is selected over a
  manual `en` track, because `tr` is tried (manual then auto) before `en` is considered at all.
- **No preferred language present:** with no `tr`/`en` track available, the first track in input order is
  selected, whatever its language/type; `available_tracks` still lists all of them.
- **Empty `tracks`:** returns `(None, {"selected": None, "available_tracks": []})`.

## Acceptance scenarios (Given / When / Then)

- **Given** tracks containing manual-`tr`, auto-`tr`, and manual-`en`, and `langs=["tr","en"]`, **when**
  selecting, **then** the manual-`tr` track is chosen and its descriptor has `type:"manual"`.
- **Given** tracks listing auto-`tr` before manual-`tr`, and `langs=["tr"]`, **when** selecting, **then**
  the manual-`tr` track is chosen.
- **Given** tracks with only manual-`en` and auto-`tr`, and `langs=["tr","en"]`, **when** selecting,
  **then** the auto-`tr` track is chosen (`type:"auto"`).
- **Given** tracks with only `de` and `fr` and `langs=["tr","en"]`, **when** selecting, **then** the
  first listed track is chosen and `available_tracks` lists every track.
- **Given** an empty track list, **when** selecting, **then** the result is
  `(None, {"selected": None, "available_tracks": []})`.

## Assumptions

- [ASSUMPTION] The selection algorithm mirrors `youtube-transcript-api`'s `find_transcript(langs)`
  semantics (language outer loop, manual-before-auto inner) per the plan's §Functions #4 note "within a
  matched language prefers manual over auto, per library default", then a first-track fallback.
- [ASSUMPTION] "First available track" for the fallback means the first element of the input `tracks`
  list (the source's own ordering), not a re-sorted order.
- [ASSUMPTION] Track objects expose `.language_code`, `.language`, `.is_generated`, `.is_translatable`
  (the `youtube-transcript-api` v1.x `Transcript` attribute names). The function returns the raw track
  object so the caller can `.fetch()` it.
- [ASSUMPTION] `type` is the string `"auto"` when `is_generated` is `True`, else `"manual"`.

## Key entities (canonical schema excerpt)

```jsonc
"transcript": {
  "available": true,
  "selected": { "language","language_name","type","is_generated" },
  "available_tracks": [ /* lang, name, is_generated, is_translatable */ ],
  ...
}
```

`info["selected"]` populates `transcript.selected`; `info["available_tracks"]` populates
`transcript.available_tracks` (the full inventory the brief requires so multi-language/multi-track videos
stay distinguishable).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] The exact key under which the fetched segments later attach is owned by
  `fetch_transcript`/`build_segments`, not this unit; `select_transcript_track` returns only the chosen
  track object and the `selected`/`available_tracks` metadata.
