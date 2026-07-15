"""T-S1-13 — artifact_basename / common_title_prefix.
Spec: docs/specs/A6-T-S1-13-artifact_basename_common_title_prefix.spec.md

Pure naming policy: both functions are deterministic and do no I/O, so every case
below is a direct call with inline values. Deliberately out of scope per the spec:
the same-title video-id disambiguator (adjudicated as ``main()``'s job) and every
item under the spec's NEEDS CLARIFICATION list.
"""

import pytest


# --- common_title_prefix: the shared boilerplate run --------------------------

def test_shared_boilerplate_returned_in_slug_form(mod):
    """Three members repeating a channel/series prefix (the plan's [v2.1] example)."""
    titles = [
        "edesis | Kayıt Modülü Nasıl Kullanılır? Şube Ekleme!",
        "edesis | Kayıt Modülü Nasıl Kullanılır? Personel Ekleme!",
        "edesis | Kayıt Modülü Nasıl Kullanılır? Rapor Alma!",
    ]
    assert mod.common_title_prefix(titles) == "edesis-kayit-modulu-nasil-kullanilir"


def test_prefix_is_the_longest_shared_run_not_a_shorter_portion(mod):
    titles = [
        "Alpha Beta Gamma One",
        "Alpha Beta Gamma Two",
        "Alpha Beta Gamma Three",
    ]
    result = mod.common_title_prefix(titles)
    assert result == "alpha-beta-gamma"
    # Not a shorter leading portion of the shared run.
    assert result != "alpha"
    assert result != "alpha-beta"


def test_prefix_rendered_lowercase_ascii_hyphen_joined(mod):
    titles = [
        "Şube Ekleme Rehberi Bir",
        "Şube Ekleme Rehberi İki",
        "Şube Ekleme Rehberi Uc",
    ]
    assert mod.common_title_prefix(titles) == "sube-ekleme-rehberi"


def test_comparison_is_token_bounded_not_character_bounded(mod):
    """`alpha` vs `alphabet` share characters but not a whole leading token."""
    titles = ["Alpha Beta One", "Alphabet Soup Two", "Alpha Gamma Three"]
    assert mod.common_title_prefix(titles) == ""


# --- common_title_prefix: the "meaningless" guard (< 3 usable titles) ---------

def test_empty_iterable_returns_empty_string(mod):
    assert mod.common_title_prefix([]) == ""


def test_single_title_returns_empty_string(mod):
    assert mod.common_title_prefix(["Alpha Beta One"]) == ""


def test_two_agreeing_titles_are_not_evidence_of_a_convention(mod):
    titles = ["Alpha Beta One", "Alpha Beta Two"]
    assert mod.common_title_prefix(titles) == ""


def test_three_entries_of_which_two_are_absent_returns_empty_string(mod):
    titles = ["Alpha Beta One", None, ""]
    assert mod.common_title_prefix(titles) == ""


def test_three_entries_of_which_two_slugify_to_nothing_returns_empty_string(mod):
    titles = ["Alpha Beta One", "🎉", "🚀🚀"]
    assert mod.common_title_prefix(titles) == ""


# --- common_title_prefix: unusable entries are excluded, not fatal ------------

def test_absent_entry_is_excluded_and_does_not_force_empty_result(mod):
    titles = ["Alpha Beta One", None, "Alpha Beta Two", "Alpha Beta Three"]
    assert mod.common_title_prefix(titles) == "alpha-beta"


def test_empty_string_entry_is_excluded_and_does_not_force_empty_result(mod):
    titles = ["Alpha Beta One", "", "Alpha Beta Two", "Alpha Beta Three"]
    assert mod.common_title_prefix(titles) == "alpha-beta"


# --- common_title_prefix: the "destructive" guard ----------------------------

def test_prefix_that_would_empty_one_member_returns_empty_string(mod):
    """The shared run is the whole slug of the first member — dropping it empties it."""
    titles = ["Alpha Beta Gamma", "Alpha Beta Gamma Delta", "Alpha Beta Gamma Epsilon"]
    assert mod.common_title_prefix(titles) == ""


def test_all_identical_titles_return_empty_string(mod):
    titles = ["Same Title", "Same Title", "Same Title"]
    assert mod.common_title_prefix(titles) == ""


def test_titles_sharing_no_leading_token_return_empty_string(mod):
    titles = ["Apple Pie", "Banana Bread", "Cherry Cake"]
    assert mod.common_title_prefix(titles) == ""


# --- artifact_basename: composition from title + position --------------------

def test_collection_member_is_padded_position_then_stripped_title_slug(mod):
    result = mod.artifact_basename(
        "abc123XYZ_1",
        "edesis | Kayıt Modülü Nasıl Kullanılır? Şube Ekleme!",
        15,
        19,
        "edesis-kayit-modulu-nasil-kullanilir",
    )
    assert result == "15-sube-ekleme"


def test_standalone_video_is_the_bare_title_slug(mod):
    assert mod.artifact_basename("fl1DSmwQKKY", "What is Claude Code?") == "what-is-claude-code"


def test_standalone_video_carries_no_numeric_prefix(mod):
    result = mod.artifact_basename("fl1DSmwQKKY", "Kayıt Modülü")
    assert result == "kayit-modulu"


# --- artifact_basename: zero-pad width ---------------------------------------

def test_two_digit_total_pads_single_digit_position(mod):
    result = mod.artifact_basename("vid00000001", "Sube Ekleme", 3, 19)
    assert result == "03-sube-ekleme"


def test_padded_position_sorts_lexically_before_two_digit_positions(mod):
    early = mod.artifact_basename("vid00000001", "Alpha", 3, 19)
    late = mod.artifact_basename("vid00000002", "Beta", 15, 19)
    assert early == "03-alpha"
    assert late == "15-beta"
    assert sorted([late, early]) == [early, late]


def test_three_digit_total_pads_to_three_digits(mod):
    result = mod.artifact_basename("vid00000001", "Sube Ekleme", 7, 100)
    assert result == "007-sube-ekleme"


def test_sub_ten_total_still_pads_to_the_two_digit_floor(mod):
    """[ADJUDICATED] A 5-member collection pads to two digits: `05-…`, not `5-…`."""
    result = mod.artifact_basename("vid00000001", "Sube Ekleme", 5, 5)
    assert result == "05-sube-ekleme"


def test_sub_ten_total_floor_applies_to_first_position_too(mod):
    result = mod.artifact_basename("vid00000001", "Alpha", 1, 9)
    assert result == "01-alpha"


def test_position_without_total_pads_to_the_two_digit_floor(mod):
    """[RESOLVED] `total` only widens padding past two, so its absence changes nothing."""
    result = mod.artifact_basename("vid00000001", "Sube Ekleme", 3)
    assert result == "03-sube-ekleme"


def test_position_without_total_matches_the_padding_a_two_digit_total_would_give(mod):
    without_total = mod.artifact_basename("vid00000001", "Alpha", 7)
    with_total = mod.artifact_basename("vid00000001", "Alpha", 7, 19)
    assert without_total == with_total == "07-alpha"


def test_two_digit_position_without_total_is_not_widened(mod):
    result = mod.artifact_basename("vid00000001", "Alpha", 15)
    assert result == "15-alpha"


# --- artifact_basename: video-id fallback ------------------------------------

def test_absent_title_falls_back_to_video_id(mod):
    assert mod.artifact_basename("fl1DSmwQKKY", None) == "fl1DSmwQKKY"


def test_empty_title_falls_back_to_video_id(mod):
    assert mod.artifact_basename("fl1DSmwQKKY", "") == "fl1DSmwQKKY"


def test_emoji_only_title_falls_back_to_video_id(mod):
    assert mod.artifact_basename("fl1DSmwQKKY", "🎉🎉🎉") == "fl1DSmwQKKY"


def test_fully_transliterated_away_title_falls_back_to_video_id(mod):
    """A title in a script slugify drops entirely leaves no usable slug."""
    assert mod.artifact_basename("fl1DSmwQKKY", "日本語のタイトル") == "fl1DSmwQKKY"


def test_video_id_fallback_preserves_original_casing(mod):
    result = mod.artifact_basename("A_b-C123XYZ", None)
    assert result == "A_b-C123XYZ"


def test_untitled_collection_member_keeps_its_position_prefix(mod):
    """[ASSUMPTION] The prefix rule applies uniformly, fallback included."""
    result = mod.artifact_basename("fl1DSmwQKKY", None, 3, 19)
    assert result == "03-fl1DSmwQKKY"


# --- artifact_basename: strip_prefix semantics -------------------------------

def test_default_strip_prefix_drops_nothing(mod):
    assert mod.artifact_basename("vid00000001", "Alpha Beta Gamma") == "alpha-beta-gamma"


def test_explicit_empty_strip_prefix_drops_nothing(mod):
    result = mod.artifact_basename("vid00000001", "Alpha Beta Gamma", strip_prefix="")
    assert result == "alpha-beta-gamma"


def test_strip_prefix_absent_from_this_title_drops_nothing(mod):
    result = mod.artifact_basename("vid00000001", "Alpha Beta", strip_prefix="gamma-delta")
    assert result == "alpha-beta"


def test_partial_token_strip_prefix_is_not_a_match(mod):
    """`alph` matches textually but not at a token boundary."""
    result = mod.artifact_basename("vid00000001", "Alpha Beta", strip_prefix="alph")
    assert result == "alpha-beta"


def test_strip_prefix_that_is_a_prefix_of_a_longer_leading_token_is_not_a_match(mod):
    result = mod.artifact_basename("vid00000001", "Alphabet Soup", strip_prefix="alpha")
    assert result == "alphabet-soup"


def test_leading_hyphen_left_by_the_cut_does_not_survive(mod):
    result = mod.artifact_basename("vid00000001", "Alpha Beta Gamma", strip_prefix="alpha-beta")
    assert result == "gamma"


def test_strip_prefix_is_front_anchored_only(mod):
    """[ASSUMPTION] A matching run that is not leading is left alone."""
    result = mod.artifact_basename("vid00000001", "One Alpha Beta", strip_prefix="alpha-beta")
    assert result == "one-alpha-beta"


def test_strip_prefix_equal_to_the_whole_title_slug_strips_nothing(mod):
    """[RESOLVED] Stripping needs a hyphen after the prefix; a slug equal to it has none."""
    result = mod.artifact_basename("vid00000001", "Alpha Beta Gamma", strip_prefix="alpha-beta-gamma")
    assert result == "alpha-beta-gamma"


def test_strip_prefix_equal_to_the_whole_slug_does_not_reach_the_video_id_fallback(mod):
    """The slug survives whole, so nothing is left empty and the id never stands in."""
    result = mod.artifact_basename("fl1DSmwQKKY", "Sube Ekleme", strip_prefix="sube-ekleme")
    assert result == "sube-ekleme"
    assert result != "fl1DSmwQKKY"


def test_strip_prefix_equal_to_a_single_token_slug_strips_nothing(mod):
    result = mod.artifact_basename("fl1DSmwQKKY", "Alpha", strip_prefix="alpha")
    assert result == "alpha"


def test_collection_member_whose_slug_equals_the_strip_prefix_keeps_slug_and_prefix(mod):
    result = mod.artifact_basename("fl1DSmwQKKY", "Alpha Beta", 3, 19, "alpha-beta")
    assert result == "03-alpha-beta"


# --- The two functions compose ------------------------------------------------

def test_common_title_prefix_output_feeds_artifact_basename(mod):
    titles = [
        "edesis | Kayıt Modülü Nasıl Kullanılır? Şube Ekleme!",
        "edesis | Kayıt Modülü Nasıl Kullanılır? Personel Ekleme!",
        "edesis | Kayıt Modülü Nasıl Kullanılır? Rapor Alma!",
    ]
    prefix = mod.common_title_prefix(titles)
    names = [
        mod.artifact_basename(f"vid0000000{i}", t, i, len(titles), prefix)
        for i, t in enumerate(titles, start=1)
    ]
    assert names == ["01-sube-ekleme", "02-personel-ekleme", "03-rapor-alma"]


def test_no_prefix_found_still_yields_usable_basenames(mod):
    titles = ["Apple Pie", "Banana Bread", "Cherry Cake"]
    prefix = mod.common_title_prefix(titles)
    assert prefix == ""
    names = [
        mod.artifact_basename(f"vid0000000{i}", t, i, len(titles), prefix)
        for i, t in enumerate(titles, start=1)
    ]
    assert names == ["01-apple-pie", "02-banana-bread", "03-cherry-cake"]


@pytest.mark.parametrize(
    "playlist_style_id",
    ["PLabcdEFGH123", "UUxyzABC", "dQw4w9WgXcQ"],
)
def test_video_id_is_never_slugified(mod, playlist_style_id):
    """Opaque ids are used verbatim — only title-derived text is slugified."""
    assert mod.artifact_basename(playlist_style_id, None) == playlist_style_id
