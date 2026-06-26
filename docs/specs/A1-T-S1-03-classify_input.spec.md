# Spec — `classify_input` (T-S1-03)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 1 Functions #1; §Locked decisions "`watch?v=…&list=…`"; catalog row T-S1-03).
> **No test code, no golden output tables here.**

## One-line purpose

Decide how a run's positional inputs should be processed — as a **single** video, a batch of **multiple**
videos, or a whole **playlist** — honoring the rule that a `watch?v=…&list=…` URL is a single video
unless the user explicitly opts into the playlist with `--playlist`.

## Signature

```python
def classify_input(args) -> str
```

Returns one of the string literals `"single"`, `"multiple"`, `"playlist"`.

## Inputs

`args` is the parsed CLI namespace (argparse `Namespace` or equivalent) exposing at least:

- `args.urls: list[str]` — the positional `<url_or_id>…` inputs, in the order given. (See assumption on
  the attribute name.)
- `args.playlist: bool` — the `--playlist` flag (`True` when the user passed it).

## Expected behavior

Let `inputs = args.urls` and `flag = args.playlist`.

Define two predicates over a single input string `s`:

- **playlist URL** — `s` references a playlist *collection* page, i.e. it contains `list=` and does **not**
  carry a watch-video reference (no `watch?v=` and no `v=` query key). A canonical example is
  `…/playlist?list=<PLAYLIST_ID>`.
- **watch+list URL** — `s` carries **both** a video reference (`watch?v=` / `v=`) **and** a `list=`
  parameter (a video opened in the context of a playlist).

Classification rules, evaluated for the count of `inputs`:

1. **More than one input** → `"multiple"` (a batch of distinct videos/URLs).
2. **Exactly one input** that is a **playlist URL** → `"playlist"` (with or without `--playlist`; a bare
   playlist page is always a playlist).
3. **Exactly one input** that is a **watch+list URL**:
   - if `flag` is `True` → `"playlist"` (user explicitly expands the playlist),
   - else → `"single"` (default: just that one video).
4. **Exactly one input** that is any other single video URL or bare id → `"single"`.

The function is pure: it inspects only `args`, performs no network or disk I/O, and is deterministic.

## Edge cases

- A single `watch?v=…&list=…` URL with `--playlist` flips from `"single"` to `"playlist"` — this is the
  one case the locked decision calls out explicitly.
- A single bare 11-char id (no URL, no `list=`) → `"single"`.
- A single short/embed URL with no `list=` → `"single"`.
- An empty `inputs` list is not expected from the CLI (argparse requires ≥1 positional); behavior is
  unspecified (see NEEDS CLARIFICATION).

## Acceptance scenarios (Given / When / Then)

- **Given** one bare video id and no flag, **when** classified, **then** the mode is single.
- **Given** two or more inputs, **when** classified, **then** the mode is multiple.
- **Given** one playlist-collection URL, **when** classified, **then** the mode is playlist, regardless of
  the flag.
- **Given** one `watch?v=…&list=…` URL **without** `--playlist`, **when** classified, **then** the mode is
  single.
- **Given** the same `watch?v=…&list=…` URL **with** `--playlist`, **when** classified, **then** the mode
  is playlist.

## Assumptions

- [ASSUMPTION] The positional inputs are exposed on the namespace as `args.urls`. If the implementer
  chooses a different argparse `dest`, this contract requires it to remain reachable as `args.urls`
  (the test harness constructs the namespace with that attribute).
- [ASSUMPTION] "Multiple inputs" takes precedence over per-item playlist detection — passing several URLs
  at once is always a multi-video batch even if one of them happens to contain `list=`. The plan only
  specifies single-input playlist routing.
- [ASSUMPTION] `--playlist` is only meaningful for a single input; combining it with multiple inputs is
  not exercised and stays `"multiple"`.

## Key entities (canonical schema excerpt)

The chosen mode drives whether a `collection{type,id,title,uploader,position,total_members}` block and a
`_manifest.json` are produced (playlist/multiple) versus a `_singles/` placement with `collection: null`
(single) — `IMPLEMENTATION_PLAN_v2.md` §Canonical per-video JSON and §File layout.

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Exact detection of a "playlist URL" vs a "watch+list URL" is specified here by the
  presence/absence of a `v=`/`watch?v=` token alongside `list=`. If the project prefers strict URL-path
  parsing (`/playlist` path) over substring inspection, confirm — the observable classification outcomes
  are identical for all forms in scope.
- [NEEDS CLARIFICATION] Behavior for an empty positional list is undefined; assumed unreachable via the
  CLI.
