# Behavioral Spec — A1: Skill 1 Pure Helpers (T-S1-01 … T-S1-04)

> **Role of this document.** This is a *behavioral contract* authored for the blind-TDD workflow in
> `docs/IMPLEMENTATION_PLAN.md` (§"Test strategy"). It tells an implementer what each helper must
> *do*, in prose. It deliberately contains **no test code, no assertions, and no golden/expected
> output values** — only signatures, behavior rules, edge cases, and acceptance criteria. Golden
> outputs live exclusively in the test-writer's `fixtures/expected/` and never appear here, so the
> implementer cannot teach to the test.
>
> **Scope:** the four *pure, offline, deterministic* helpers of Skill 1
> (`.claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py`):
> `extract_video_id`, `format_timestamp`, `classify_input`, and `slugify` / `collection_dir_name`.
>
> **Reuse note.** `extract_video_id` and `format_timestamp` are copied verbatim from the existing
> `youtube-transcript` skill (`scripts/get_transcript.py`, lines 19–29 and 32–39). Their specs below
> describe the *behavior to preserve*; the implementer should reproduce that behavior, not invent new
> semantics. `classify_input` and `slugify`/`collection_dir_name` are new.
>
> **Shared invariants for all four helpers**
> - **Pure & deterministic:** output depends only on the arguments. No network, no filesystem, no
>   clock, no global state, no environment reads. Calling twice with equal arguments yields equal
>   results.
> - **No side effects:** they compute and return; they do not print, write files, or mutate their
>   inputs.
> - **UTF-8 throughout:** inputs may contain non-ASCII (notably Turkish) text and must be handled
>   without raising encoding errors.

---

## T-S1-01 — `extract_video_id`

### Signature
```
extract_video_id(url_or_id: str) -> str
```

### Behavior
Accepts either a full YouTube URL (in any of the common forms) or a value that is already a bare
video ID, and returns the canonical 11-character video ID.

A YouTube video ID is exactly **11 characters** drawn from the character set
`A–Z`, `a–z`, `0–9`, `-`, and `_`.

The function recognizes a video ID embedded in any of these URL shapes:
- the standard watch URL (`…youtube.com/watch?v=<id>…`),
- the short-link form (`…youtu.be/<id>…`),
- the embed form (`…youtube.com/embed/<id>…`),
- the legacy `/v/` form (`…youtube.com/v/<id>…`),
- a raw, bare 11-character ID supplied on its own.

When the input matches one of these shapes, the 11-character ID is returned as-is (same casing,
same characters). When the input matches none of them, the function **raises `ValueError`** whose
message identifies the offending input.

### Edge cases
- **`watch?v=<id>&list=<playlist_id>` (video inside a playlist context):** the **video ID** is
  returned; the trailing `&list=…` (and any other query parameters) is ignored. The presence of a
  playlist parameter does **not** change this helper's output — playlist-vs-single routing is the job
  of `classify_input` (T-S1-03), not this helper.
- **Additional query parameters / fragments** after the ID (e.g. `&t=`, `&index=`, `#…`) are
  ignored; only the 11-character ID is extracted.
- **Bare ID input** that is exactly 11 valid characters is returned unchanged, even though it is not
  a URL.
- **Case sensitivity:** IDs are returned with their original casing; casing is significant and must
  not be altered.
- **Invalid inputs** — empty string, a string that contains no recognizable ID, or a candidate that
  is the wrong length / contains out-of-charset characters — raise `ValueError` rather than returning
  a partial, guessed, or empty result.

### Acceptance criteria
- All four URL forms above, plus a bare 11-character ID, resolve to the correct ID.
- A `watch?v=…&list=…` URL resolves to the **video** ID (the playlist segment is disregarded).
- Input from which no valid 11-character ID can be extracted causes a `ValueError`.
- The helper performs no I/O and is deterministic.

---

## T-S1-02 — `format_timestamp`

### Signature
```
format_timestamp(seconds: float) -> str
```

### Behavior
Converts a duration/offset expressed in seconds into a human-readable, zero-padded clock string for
use in the Markdown transcript view (`[MM:SS]` / `[HH:MM:SS]` prefixes).

- When the duration is **under one hour**, the result uses minutes-and-seconds form: two-digit
  minutes and two-digit seconds separated by a colon.
- When the duration is **one hour or more**, the result uses hours-minutes-seconds form: hours, then
  two-digit minutes, then two-digit seconds, each separated by colons.
- Minutes and seconds components are always padded to at least two digits.

### Edge cases
- **Zero seconds** produces the minutes-and-seconds form (i.e. the sub-one-hour shape), not the
  hours form.
- **Exactly one hour** (the 3600-second boundary) crosses into the hours form; anything strictly
  below it stays in the minutes form.
- **Fractional seconds are truncated toward zero** (floored for non-negative input), not rounded —
  the sub-second remainder is dropped before formatting.
- **Durations of ten hours or more** are still valid; the hours component is *at least* two digits
  but is not capped, so very long durations widen the hours field rather than overflowing the
  minutes/seconds fields.
- Minutes and seconds always render within their normal 0–59 range (the carry into the next-larger
  unit is handled before formatting).

### Acceptance criteria
- Sub-one-hour inputs render in `MM:SS` form; inputs at or above one hour render in `HH:MM:SS` form.
- A zero input renders as the two-component (minutes/seconds) form.
- Fractional input is floored before formatting (no rounding up).
- The helper performs no I/O and is deterministic.

---

## T-S1-03 — `classify_input`

### Signature
```
classify_input(args) -> <classification result>
```
`args` is the parsed CLI input for Skill 1: the list of positional `url_or_id` values the user
supplied, together with the boolean `--playlist` flag. (Concretely this is the argparse namespace, or
equivalently the positionals list plus the playlist flag.) The return value distinguishes the three
routing modes below and carries enough information for the caller to act: the **mode**
(`single` | `multiple` | `playlist`), the **target(s)** it applies to, and — for the playlist mode —
the **playlist URL/ID to enumerate**.

### Behavior
Decides how the run should be routed, based on *how many* inputs were given, *what kind* of URLs they
are, and whether `--playlist` was set. The three modes:

- **single** — exactly one input that designates one video. This covers a single video URL, a bare
  video ID, **and** a `watch?v=…&list=…` URL when `--playlist` was *not* given (the locked default:
  a watch-with-list URL is treated as one video, and the playlist context is ignored).
- **playlist** — the run should expand a playlist into its member videos. This applies when the sole
  input is a pure playlist URL (a `playlist?list=…` form that has no watchable video component),
  **or** when the input is a `watch?v=…&list=…` URL **and** `--playlist` was given (the flag promotes
  the watch-with-list URL from single to whole-playlist).
- **multiple** — more than one input was supplied; each is handled as its own video target.

The decisive rules, restated as precedence:
1. **More than one positional input → `multiple`.**
2. **A single pure-playlist URL → `playlist`.**
3. **A single `watch?v=…&list=…` URL →** `playlist` **iff** `--playlist` is set, otherwise `single`.
4. **A single plain video URL or bare ID → `single`.**

### Edge cases
- **`watch?v=…&list=…` without `--playlist`:** classified as **single** (default-single decision is
  load-bearing — see `IMPLEMENTATION_PLAN.md` Locked decisions).
- **`watch?v=…&list=…` with `--playlist`:** classified as **playlist**; the list component is what
  gets enumerated.
- **Pure playlist URL** (`playlist?list=…`, no `v=`): classified as **playlist** whether or not
  `--playlist` is present (the flag is redundant but harmless here).
- **`--playlist` set but no playlist identifier is present** in the input (e.g. a plain video URL or
  bare ID): there is nothing to expand, so the run does **not** become a playlist; it falls back to
  the single/multiple classification implied by the inputs. (The flag only promotes inputs that
  actually carry a playlist ID.)
- **Multiple inputs where one happens to carry a `list=` parameter:** still **multiple**; per-input
  playlist expansion is out of scope for this helper — each positional is one target.
- The helper **does not fetch or validate** anything over the network; it classifies purely from the
  string shapes and the flag. Whether the playlist/video actually exists is decided later by the
  enumeration/fetch steps.

### Acceptance criteria
- A single plain video URL or bare ID → `single`.
- Two or more inputs → `multiple`.
- A pure playlist URL → `playlist`.
- A `watch?v=…&list=…` URL → `single` by default and `playlist` only when `--playlist` is set.
- The result exposes the chosen mode and, for `playlist`, the playlist to enumerate.
- The helper performs no I/O and is deterministic.

---

## T-S1-04 — `slugify` / `collection_dir_name`

These two are specified together because `collection_dir_name` is defined in terms of `slugify`.
Both are the single source of truth for naming, so the project can change naming in one place.

### Signatures
```
slugify(text: str) -> str
collection_dir_name(title: str, playlist_id: str) -> str
```

### `slugify` — behavior
Transforms arbitrary human title text into a safe, lowercase, ASCII-only slug suitable for use as a
filesystem directory-name component. The transformation, in order:

1. **Turkish transliteration.** Turkish-specific letters are mapped to their closest plain-ASCII
   equivalents, for both lower- and upper-case forms, using this mapping:
   `ı→i`, `İ→i`, `ş→s`, `Ş→s`, `ğ→g`, `Ğ→g`, `ü→u`, `Ü→u`, `ö→o`, `Ö→o`, `ç→c`, `Ç→c`.
   (This is the *rule*, not a per-input expected output.)
2. **Lowercasing.** The whole string is folded to lower case.
3. **Whitespace → hyphen.** Runs of whitespace become a hyphen separator.
4. **Drop unsafe characters.** Any character not in the safe set (`a–z`, `0–9`, hyphen) is removed.
5. **Collapse & trim.** Consecutive hyphens collapse to one, and leading/trailing hyphens are
   stripped, so the result has no doubled or edge hyphens.

The result therefore contains only lowercase ASCII letters, digits, and single interior hyphens.

#### `slugify` edge cases
- **Turkish dotted/dotless `i` distinction** (`ı` vs `i`, `İ` vs `I`) is normalized per the mapping
  above — no Unicode-uppercase surprises (e.g. the dotted-capital-İ pitfall) leak through.
- **Multiple / leading / trailing spaces** do not produce doubled or edge hyphens (handled by the
  collapse-&-trim step).
- **Already-ASCII titles** survive intact apart from lowercasing and separator normalization.
- **Punctuation and symbols** (commas, slashes, parentheses, emojis, etc.) are dropped, not
  transliterated.
- **Degenerate input** — empty string, or a title consisting entirely of characters that all get
  stripped — yields an empty-or-trivial slug; the helper must return a stable, safe fallback rather
  than something that would create an unusable or hidden directory name. (The exact fallback is an
  implementation choice; it must be deterministic and filesystem-safe.)

### `collection_dir_name` — behavior
Builds the per-collection directory name by combining the slugified collection/playlist title with
the playlist's own ID, joined so the ID is a distinguishing suffix on the slug
(`<slug-of-title>-<playlist_id>`).

The playlist ID is appended **verbatim** — it is *not* passed through `slugify`, because yt-dlp
playlist IDs are already ASCII-safe identifiers (e.g. the `PL…` form) and their exact characters and
casing must be preserved so the directory name round-trips back to the playlist.

#### `collection_dir_name` edge cases
- **Identical titles, different playlists:** because the verbatim playlist ID is the suffix, two
  collections with the same title still produce **distinct** directory names — the ID guarantees
  uniqueness.
- **Title that slugifies to the degenerate/fallback case:** the directory name still ends with the
  verbatim playlist ID, so it remains unique and usable even when the title contributes little or
  nothing.
- Title casing/Turkish characters affect only the slug portion; the appended ID is untouched.

### Acceptance criteria
- Turkish characters in a title become their ASCII equivalents per the mapping above.
- Whitespace becomes hyphen separators with no doubled or edge hyphens.
- The output is lowercase, ASCII-only, and limited to letters, digits, and single interior hyphens.
- `collection_dir_name` appends the playlist ID **unmodified** as a suffix on the slug, yielding a
  name that is unique per playlist even when titles collide.
- Both helpers perform no I/O and are deterministic.
```
