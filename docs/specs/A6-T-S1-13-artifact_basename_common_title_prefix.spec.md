# Spec — `artifact_basename` / `common_title_prefix` (T-S1-13)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Functions #7 "centralize all naming", **[v2.1]**; §File layout; the **[v2.1] Artifact basename**
> paragraph, `docs/IMPLEMENTATION_PLAN_v2.md:162-167`), `skills/youtube-artifact-collector/SKILL.md`
> (§Artifact naming, §Output layout), `docs/IMPLEMENTATION_PLAN-progress.md` (SK1-ORCH **[v2.1]** note),
> and the two functions' own signatures + docstrings. Grouped as one unit because they compose a single
> naming policy (precedent: T-S1-04 groups `slugify` + `collection_dir_name`).
> **No test code, no golden output tables here.**

## One-line purpose

Derive the canonical per-video artifact basename from the video's **title** — position-prefixed inside a
collection, bare when standalone, with shared boilerplate dropped and the video id as fallback — and
compute the boilerplate token prefix that a collection's titles share.

## Signatures

```python
def common_title_prefix(titles) -> str
def artifact_basename(
    video_id: str,
    title: str | None = None,
    position: int | None = None,
    total: int | None = None,
    strip_prefix: str = "",
) -> str
```

`artifact_basename` is one of the **centralized** naming helpers (plan §Functions #7): layout changes are
a one-edit change here. It reuses `slugify` (T-S1-04) unchanged. Both functions are pure and
deterministic — no I/O, no network.

## Inputs

- `titles` — an iterable of the collection members' raw titles. Individual entries may be absent/empty
  (a private or deleted member carries no title).
- `video_id: str` — the YouTube video id. Opaque; used verbatim, never slugified.
- `title: str | None` — the video's raw human-authored title, possibly containing Turkish letters,
  punctuation, and boilerplate. `None`/empty for an unavailable video.
- `position: int | None` — the member's 1-based playlist position; `None` for a standalone video.
- `total: int | None` — the collection's member count, which sets the zero-pad width; `None` standalone.
- `strip_prefix: str` — the shared boilerplate to drop, expressed as a **slug-token string** (the value
  `common_title_prefix` returns). Default `""` means "drop nothing".

## Expected behavior — `common_title_prefix`

Collection members routinely repeat a channel/series boilerplate on every title, which would otherwise
dominate every basename (plan **[v2.1]**: `edesis | Kayıt Modülü Nasıl Kullanılır? Şube Ekleme!` must
yield `15-sube-ekleme`, not a 55-character prefix repeated on each member).

- Compare titles at the level of **slug tokens**, not raw characters: each title is slugified (T-S1-04)
  and split on `-`. The returned prefix is the **longest leading run of tokens that every usable title
  shares**, rendered in the same hyphen-joined slug form so it is directly consumable as
  `artifact_basename`'s `strip_prefix`.
- A title that is absent/empty, or that slugifies to nothing, is **not usable** and does not participate
  in the comparison.
- Return `""` — meaning "no boilerplate, drop nothing" — whenever a prefix would be either:
  - **meaningless**: fewer than **three** usable titles are available to compare. Two agreeing titles are
    not evidence of a series-wide convention.
  - **destructive**: stripping the prefix would leave **some** member with nothing left. A prefix is only
    worth dropping if every member retains a name.
- The guard against emptying a member lives **here**, not in `artifact_basename`.

## Expected behavior — `artifact_basename`

Compose the basename from the title, in this order:

1. **Slugify the title** via `slugify` (T-S1-04), yielding lowercase ASCII hyphenated tokens.
2. **Drop `strip_prefix`** from the front of that slug when present, at a **token boundary** — the prefix
   is a slug-token run, so a partial-token match is not a match. Leading hyphens left behind by the cut
   do not survive into the result.
3. **Fall back to the video id** when steps 1–2 leave **no usable slug**. Per the plan, the fallback
   covers an absent title, an emoji-only title, and a title in a script that `slugify` transliterates
   away entirely. The video id is used verbatim, with its original casing.
4. **Prefix the playlist position** for collection members: `<position>-<slug>`. The position is
   **zero-padded to the width of the member count (`total`), with a floor of two digits**, so lexical
   file order matches playlist order past nine members and every collection's names start alike. A
   19-member collection pads to two digits, a 100-member collection to three, and a 5-member collection
   still pads to two (`05-…`, not `5-…`). A standalone video carries **no** prefix and is named
   `<slug>` alone.

   > **[ADJUDICATED 2026-07-15]** The plan's wording ("zero-padded to the member count") read literally
   > implies width 1 for a sub-ten-member collection. The two-digit floor is the intended behavior:
   > it keeps names visually uniform and stable if a playlist later grows past nine members. The plan
   > wording is being corrected to match, not the code.

The result is a bare basename — no directory, no extension. Callers append `.json` / `.md` and place it
under `data/<slug(title)>-<playlist_id>/` or `data/_singles/` (plan §File layout).

Consumers **never rebuild** this name: `_manifest.json` records each member's actual filenames under
`files{json,md}`, and that is the resolution path (plan **[v2.1]**; SKILL.md §Artifact naming).

## Edge cases

- **Absent title** (`None` or empty) → the video id is the basename; a collection member still carries its
  position prefix. [ASSUMPTION]
- **Title that slugifies to the empty string** (emoji-only, fully transliterated away) → video-id
  fallback, same as an absent title. These are the cases the plan names explicitly.
- **`strip_prefix` empty (default)** → nothing is dropped; the full title slug is used.
- **`strip_prefix` not actually present** on this title → nothing is dropped; the function does not fail.
- **`strip_prefix` equal to the whole title slug** → would leave nothing. `common_title_prefix` is
  specified never to return such a prefix, so this is a caller-contract violation rather than a normal
  path; see NEEDS CLARIFICATION.
- **Standalone videos sharing a title** → the video id is *appended* as a disambiguator (plan
  **[v2.1]**; SKILL.md §Artifact naming). **[ADJUDICATED 2026-07-15]** This is **outside this unit's
  contract**: the signature carries no parameter conveying that a collision exists, so the function
  cannot detect one. Detecting a taken basename and appending the id belongs to the `main()`
  orchestration loop, which alone knows what other videos in the run have claimed. This unit is not
  expected to implement, and must not be tested for, the disambiguator.
- **`common_title_prefix` with fewer than three usable titles** (including the empty iterable, one title,
  or three titles of which two are unusable) → `""`.
- **`common_title_prefix` where all titles are identical** → the shared run is the entire slug, so
  stripping would empty every member → `""` by the destructive guard.
- **`common_title_prefix` where titles share no leading token** → `""` (there is no common run).
- The playlist id and video id are never slugified; only title-derived text is (T-S1-04 contract).

## Acceptance scenarios (Given / When / Then)

- **Given** a collection of at least three titles that all begin with the same boilerplate token run,
  **when** `common_title_prefix` runs, **then** it returns that shared run in slug form, and it is the
  **longest** such run rather than a shorter leading portion of it.
- **Given** titles that agree on a leading run whose removal would leave one member with an empty name,
  **when** `common_title_prefix` runs, **then** it returns `""`.
- **Given** only two usable titles, however much they agree, **when** `common_title_prefix` runs,
  **then** it returns `""`.
- **Given** a collection whose entries include an absent title, **when** `common_title_prefix` runs,
  **then** the absent entry is excluded from the comparison and does not by itself force `""`.
- **Given** a title, a position, a total, and the collection's shared prefix, **when**
  `artifact_basename` runs, **then** the result is the position — zero-padded to the width of the member
  count — a hyphen, and the title slug with the shared prefix removed.
- **Given** a title and no position/total, **when** `artifact_basename` runs, **then** the result is the
  bare title slug with no numeric prefix.
- **Given** a total that requires two digits, **when** `artifact_basename` runs for a single-digit
  position, **then** the position is zero-padded so it sorts lexically before the two-digit positions.
- **Given** a total requiring three digits, **when** `artifact_basename` runs, **then** the position is
  padded to three digits.
- **Given** a total of fewer than ten members, **when** `artifact_basename` runs, **then** the position
  is still padded to two digits (the floor), not left bare.
- **Given** a title that yields no usable slug, **when** `artifact_basename` runs, **then** the video id
  stands in for the slug portion, with its original casing preserved.
- **Given** a `strip_prefix` that matches only part of a leading token of the title slug, **when**
  `artifact_basename` runs, **then** nothing is stripped (the match is token-bounded, not textual).

## Assumptions

- [ASSUMPTION] The video-id fallback still receives the position prefix for a collection member (i.e. an
  untitled member is named `<position>-<video_id>`). The plan states the prefix rule for "collection
  members" without carving out the fallback, so it is applied uniformly.
- [ASSUMPTION] The pad width is the digit count of `total` (a 19-member collection pads to two digits, a
  100-member collection to three). The plan says "zero-padded to the member count … so lexical order
  matches playlist order past nine members", which this reading satisfies.
- [ASSUMPTION] `common_title_prefix` returns the prefix in **slug form** (lowercase ASCII,
  hyphen-joined), not raw title text — that is what makes it directly consumable as `strip_prefix`, and
  the docstring describes it as a "slug-token run".
- [ASSUMPTION] The "at least three titles" threshold counts **usable** titles (those that slugify to
  something), not raw entries in the iterable. The docs give the number without defining the population.
- [ASSUMPTION] `strip_prefix` is matched only as a **leading** prefix, not anywhere in the slug — both
  the plan ("the token prefix every member … shares") and the docstring ("Longest slug-token **run**"
  shared by every title) describe a front-anchored run.
- [ASSUMPTION] Both functions are pure and deterministic, doing no I/O — consistent with the other
  naming helpers (T-S1-04) and with `scan_existing` (T-S1-14) being the unit that owns disk access.

## Key entities (canonical schema excerpt)

`artifact_basename` produces the `<basename>` of the on-disk pair `<basename>.json` / `<basename>.md`
under `data/<slug(title)>-<playlist_id>/` (collection members, position-prefixed) or `data/_singles/`
(standalone) — plan §File layout, **[v2.1]**. Those exact filenames are recorded per member in
`_manifest.json` under `members[].files{json,md}`, which is the **only** supported way for consumers to
resolve an artifact. `position` and `total` correspond to the artifact's
`collection{position, total_members}` block (`null` for true singles); `video_id` corresponds to
`video.id`. Skill 2 mirrors this basename for its `<basename>.requirements.{md,json}` outputs, keeping
Skill 1 the sole owner of naming policy (plan §Skill 2 Output, **[v2.1]**).

`slugify` (T-S1-04) is reused here **unchanged**; none of this unit's fallback, position-prefix, or
prefix-stripping rules constrain it.

## NEEDS CLARIFICATION

Two items raised in drafting have been **adjudicated** and folded into the behavior above: the
minimum pad width (floor of two digits — plan wording to be corrected) and the video-id disambiguator
(out of this unit's scope; the `main()` loop owns it).

The items below remain genuinely unspecified by the documented policy. **They are deliberately left
out of this unit's tested contract**: writing a test for them would freeze whatever the code happens
to do today into a contract nobody has decided on. They are logged in `to-do.md` as documentation
gaps to settle on their own merits.

- [NEEDS CLARIFICATION] **`position` supplied without `total`** (or vice versa). Whether this is a valid
  call, and what pad width applies, is not described. The `main()` loop always supplies both for a
  collection member and neither for a standalone video, so no real caller reaches this combination.
- [NEEDS CLARIFICATION] **A `strip_prefix` that would empty this title's slug.** `common_title_prefix`
  guards against returning one, but `artifact_basename` accepts `strip_prefix` from any caller. Whether
  it should then fall back to the video id, or leave the prefix in place, is unspecified.
- [NEEDS CLARIFICATION] Whether `common_title_prefix`'s "destructive" guard tests only the *usable*
  titles it compared, or every entry passed in.
- [NEEDS CLARIFICATION] Whether the shared-prefix comparison is case-/punctuation-sensitive beyond what
  `slugify` already normalizes away — i.e. whether two titles differing only in punctuation are treated
  as agreeing. Presumed yes (they slugify identically), but not stated.
