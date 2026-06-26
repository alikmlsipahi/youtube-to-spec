"""Blind-TDD unit tests for the four pure helpers of Skill 1
(`youtube-artifact-collector`):

    T-S1-01  extract_video_id
    T-S1-02  format_timestamp
    T-S1-03  classify_input
    T-S1-04  slugify / collection_dir_name

These tests are offline, deterministic, and have no side effects. They are
written from the behavioral spec (docs/specs/A1-pure-helpers.spec.md) and the
canonical schema in docs/IMPLEMENTATION_PLAN.md — never from implementation.

Import contract: the helpers live in `scripts/extract_artifacts.py`, made
importable as a top-level module by conftest.py.
"""

import re

import pytest

from extract_artifacts import (
    classify_input,
    collection_dir_name,
    extract_video_id,
    format_timestamp,
    slugify,
)

# Reused across slug assertions: the safe-charset invariant of a finished slug.
_SLUG_CHARSET = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ====================================================================== #
# T-S1-01 — extract_video_id
# ====================================================================== #

def test_extract_video_id_recognized_forms(load_input):
    """Every recognized URL form and bare id resolves to the canonical 11-char id."""
    cases = load_input("video_id_urls.json")["valid"]
    for case in cases:
        assert extract_video_id(case["input"]) == case["expected"], case["form"]


def test_extract_video_id_bare_id_unchanged():
    """A bare 11-char id is returned verbatim, preserving casing and -/_ chars."""
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("fl1DSmwQKKY") == "fl1DSmwQKKY"
    assert extract_video_id("a_b-c1234XY") == "a_b-c1234XY"


def test_extract_video_id_casing_preserved():
    """Casing is significant and must not be folded."""
    out = extract_video_id("https://www.youtube.com/watch?v=AbCdEfGhIjK")
    assert out == "AbCdEfGhIjK"


def test_extract_video_id_watch_with_list_returns_video_id(load_input):
    """watch?v=ID&list=... yields the VIDEO id; the &list= segment is ignored."""
    for case in load_input("video_id_urls.json")["watch_with_list"]:
        assert extract_video_id(case["input"]) == case["expected"]


def test_extract_video_id_invalid_raises(load_input):
    """Inputs with no extractable 11-char id raise ValueError, not a guess."""
    for bad in load_input("video_id_urls.json")["invalid"]:
        with pytest.raises(ValueError):
            extract_video_id(bad)


def test_extract_video_id_error_names_offending_input():
    """The ValueError message identifies the offending input."""
    with pytest.raises(ValueError) as excinfo:
        extract_video_id("totally-bogus")
    assert "totally-bogus" in str(excinfo.value)


# ====================================================================== #
# T-S1-02 — format_timestamp
# ====================================================================== #

@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "00:00"),          # zero -> minutes form, not hours form
        (5, "00:05"),
        (59, "00:59"),
        (60, "01:00"),
        (61, "01:01"),
        (599, "09:59"),
        (3599, "59:59"),       # one tick below the 1h boundary -> still MM:SS
    ],
)
def test_format_timestamp_under_one_hour(seconds, expected):
    assert format_timestamp(seconds) == expected


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (3600, "01:00:00"),    # exactly 1h crosses into HH:MM:SS
        (3661, "01:01:01"),
        (7325, "02:02:05"),
        (36000, "10:00:00"),   # 10h: hours field widens, no overflow into mm/ss
        (360000, "100:00:00"), # >=100h: hours not capped
    ],
)
def test_format_timestamp_at_or_above_one_hour(seconds, expected):
    assert format_timestamp(seconds) == expected


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0.9, "00:00"),        # fractional floored toward zero, not rounded up
        (59.999, "00:59"),
        (61.5, "01:01"),
        (3599.9, "59:59"),     # must NOT round up across the 1h boundary
        (3600.9, "01:00:00"),
    ],
)
def test_format_timestamp_fractional_is_floored(seconds, expected):
    assert format_timestamp(seconds) == expected


def test_format_timestamp_minutes_seconds_within_range():
    """The carry into the next unit happens before formatting (mm,ss in 0..59)."""
    out = format_timestamp(7384)  # 2h 03m 04s
    h, m, s = out.split(":")
    assert (h, m, s) == ("02", "03", "04")
    assert 0 <= int(m) <= 59 and 0 <= int(s) <= 59


# ====================================================================== #
# T-S1-03 — classify_input
# ====================================================================== #

# Sample identifiers reused below.
_VID = "dQw4w9WgXcQ"
_PL = "PLxA1B2C3D4E5F6"
_WATCH = f"https://www.youtube.com/watch?v={_VID}"
_WATCH_LIST = f"https://www.youtube.com/watch?v={_VID}&list={_PL}"
_PURE_PLAYLIST = f"https://www.youtube.com/playlist?list={_PL}"


def _mode(result):
    """Extract the routing mode from classify_input's result, tolerant of shape.

    The spec deliberately leaves the result's concrete representation open
    (it must merely *expose* the mode). Accept a bare string, a dict, an object
    with a ``.mode`` attribute, or a tuple/namedtuple whose mode is findable.
    """
    if isinstance(result, str):
        return result.lower()
    if isinstance(result, dict):
        val = result.get("mode") or result.get("kind") or result.get("type")
        if val is not None:
            return str(val).lower()
    val = getattr(result, "mode", None)
    if val is not None:
        return str(val).lower()
    if isinstance(result, (tuple, list)) and result:
        return str(result[0]).lower()
    raise AssertionError(f"could not determine mode from result: {result!r}")


def _blob(result):
    """Stringify a result for substring checks regardless of its concrete shape."""
    parts = [repr(result)]
    d = getattr(result, "__dict__", None)
    if d:
        parts.append(repr(d))
    return " ".join(parts)


def test_classify_single_plain_video_url(make_args):
    assert _mode(classify_input(make_args(_WATCH))) == "single"


def test_classify_single_bare_id(make_args):
    assert _mode(classify_input(make_args(_VID))) == "single"


def test_classify_multiple_when_more_than_one_input(make_args):
    assert _mode(classify_input(make_args([_WATCH, _VID]))) == "multiple"


def test_classify_multiple_takes_precedence_over_list_param(make_args):
    """Multiple positionals stay 'multiple' even if one carries a &list= param."""
    assert _mode(classify_input(make_args([_WATCH_LIST, _VID]))) == "multiple"


def test_classify_pure_playlist_url_is_playlist(make_args):
    assert _mode(classify_input(make_args(_PURE_PLAYLIST))) == "playlist"


def test_classify_pure_playlist_url_playlist_flag_redundant(make_args):
    """A pure playlist URL is 'playlist' with or without --playlist."""
    assert _mode(classify_input(make_args(_PURE_PLAYLIST, playlist=True))) == "playlist"


def test_classify_watch_with_list_default_single(make_args):
    """The load-bearing default: watch?v=..&list=.. WITHOUT --playlist -> single."""
    assert _mode(classify_input(make_args(_WATCH_LIST))) == "single"


def test_classify_watch_with_list_promoted_by_flag(make_args):
    """watch?v=..&list=.. WITH --playlist -> playlist."""
    assert _mode(classify_input(make_args(_WATCH_LIST, playlist=True))) == "playlist"


def test_classify_playlist_flag_without_list_id_does_not_promote(make_args):
    """--playlist on a plain video (no list id) has nothing to expand -> single."""
    assert _mode(classify_input(make_args(_WATCH, playlist=True))) == "single"
    assert _mode(classify_input(make_args(_VID, playlist=True))) == "single"


def test_classify_playlist_result_exposes_playlist_to_enumerate(make_args):
    """For playlist mode the result must surface the playlist to enumerate."""
    for result in (
        classify_input(make_args(_PURE_PLAYLIST)),
        classify_input(make_args(_WATCH_LIST, playlist=True)),
    ):
        assert _mode(result) == "playlist"
        assert _PL in _blob(result)


def test_classify_single_watch_with_list_keeps_video_target(make_args):
    """Default-single watch+list keeps the VIDEO as the target."""
    result = classify_input(make_args(_WATCH_LIST))
    assert _mode(result) == "single"
    assert _VID in _blob(result)


# ====================================================================== #
# T-S1-04 — slugify
# ====================================================================== #

@pytest.mark.parametrize(
    "text, expected",
    [
        # Turkish transliteration (lower + upper forms) then slugging.
        ("Kayıt Modülü", "kayit-modulu"),
        ("Öğrenci Şubesi", "ogrenci-subesi"),
        ("Sınav Çıkışı", "sinav-cikisi"),
        ("İstanbul", "istanbul"),          # dotted capital I pitfall -> i
        ("ÇĞIİÖŞÜ", "cgiiosu"),            # all uppercase Turkish letters
        ("çğıiöşü", "cgiiosu"),            # all lowercase Turkish letters
        # Already-ASCII titles: lowercase + separator normalization only.
        ("My Cool Video", "my-cool-video"),
        ("Already-Slugged-123", "already-slugged-123"),
        # Whitespace handling: no doubled / edge hyphens.
        ("  Hello   World  ", "hello-world"),
        ("Tab\tand\nNewline", "tab-and-newline"),
        # Punctuation / symbols dropped (not transliterated).
        ("Video #1: Intro (HD)!", "video-1-intro-hd"),
        ("rock&roll", "rockroll"),
        ("A/B Testing", "ab-testing"),
        ("Rocket 🚀 Launch", "rocket-launch"),
    ],
)
def test_slugify_known_outputs(text, expected):
    assert slugify(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "My Cool Video",
        "Kayıt Modülü",
        "Video #1: Intro (HD)!",
        "İstanbul",
        "Rocket 🚀 Launch",
    ],
)
def test_slugify_result_is_safe_ascii_lowercase(text):
    """Output is lowercase ASCII, only letters/digits/single interior hyphens."""
    out = slugify(text)
    assert out == out.lower()
    assert out.isascii()
    assert _SLUG_CHARSET.fullmatch(out)
    assert "--" not in out
    assert not out.startswith("-") and not out.endswith("-")


@pytest.mark.parametrize("text", ["", "   ", "!!! ###", "🚀🚀🚀", "/\\:*?"])
def test_slugify_degenerate_returns_safe_fallback(text):
    """Degenerate input yields a stable, filesystem-safe, non-hidden fallback.

    The exact fallback string is an implementation choice, so only invariants
    are asserted: non-empty, ascii, safe charset, not starting with '.' or '-'.
    """
    out = slugify(text)
    assert isinstance(out, str)
    assert out != ""
    assert out.isascii()
    assert _SLUG_CHARSET.fullmatch(out)
    assert not out.startswith(".")
    assert not out.startswith("-") and not out.endswith("-")


def test_slugify_is_deterministic():
    assert slugify("Kayıt Modülü") == slugify("Kayıt Modülü")


# ====================================================================== #
# T-S1-04 — collection_dir_name
# ====================================================================== #

def test_collection_dir_name_is_slug_plus_verbatim_id():
    """Defined as '<slugify(title)>-<playlist_id>', id appended verbatim."""
    title, pid = "Kayıt Modülü", "PLabc123"
    assert collection_dir_name(title, pid) == f"{slugify(title)}-{pid}"
    assert collection_dir_name(title, pid) == "kayit-modulu-PLabc123"


def test_collection_dir_name_preserves_id_casing_and_chars():
    """The playlist id is NOT slugified: casing and -/_ must round-trip."""
    pid = "PLxYz_-123"
    out = collection_dir_name("İstanbul", pid)
    assert out.endswith(f"-{pid}")
    assert out == f"istanbul-{pid}"


def test_collection_dir_name_unique_for_same_title_different_ids():
    """Same title, different playlists -> distinct names (id guarantees uniqueness)."""
    a = collection_dir_name("Same Title", "PL_AAA")
    b = collection_dir_name("Same Title", "PL_BBB")
    assert a != b
    assert a.endswith("-PL_AAA")
    assert b.endswith("-PL_BBB")


def test_collection_dir_name_degenerate_title_still_ends_with_id():
    """Even a title that slugifies to the fallback keeps the verbatim id suffix."""
    out = collection_dir_name("###", "PLZZZ")
    assert out.endswith("-PLZZZ")
    # Still a usable, non-hidden name overall.
    assert not out.startswith(".") and not out.startswith("-")
