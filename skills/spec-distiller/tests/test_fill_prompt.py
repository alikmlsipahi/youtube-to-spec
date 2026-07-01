"""T-S2-02 — fill_prompt.
Spec: docs/specs/A4-T-S2-02-fill_prompt.spec.md

Structural / behavioral assertions only (placeholder substitution, no-residual,
verbatim segment text, defensive empties); the exact filled layout is intentionally
not pinned, to keep the blind barrier robust.
"""

import copy

import pytest

from conftest import load_fixture, read_text_fixture

_ART = load_fixture("inputs", "fill_prompt.json")
_TEMPLATE = read_text_fixture("inputs", "sample_prompt.md")


def _no_residual(text):
    return "{{" not in text and "}}" not in text


def test_all_placeholders_replaced_no_residual(mod):
    out = mod.fill_prompt(_TEMPLATE, _ART["artifact_full"])
    assert _no_residual(out)


def test_scalar_values_present(mod):
    art = _ART["artifact_full"]
    out = mod.fill_prompt(_TEMPLATE, art)
    assert art["video"]["title"] in out
    assert art["video"]["id"] in out
    assert art["video"]["url"] in out
    assert art["video"]["channel"] in out
    assert art["video"]["description"] in out
    assert art["collection"]["title"] in out


def test_repeated_placeholder_replaced_everywhere(mod):
    art = _ART["artifact_full"]
    out = mod.fill_prompt(_TEMPLATE, art)
    # {{video_title}} appears more than once in the template.
    assert out.count(art["video"]["title"]) >= 2
    assert _no_residual(out)


def test_transcript_segments_verbatim_and_indexed(mod):
    art = _ART["artifact_full"]
    out = mod.fill_prompt(_TEMPLATE, art)
    for seg in art["transcript"]["segments"]:
        assert seg["text"] in out
        assert str(seg["index"]) in out


def test_missing_description_becomes_empty_no_residual(mod):
    out = mod.fill_prompt(_TEMPLATE, _ART["artifact_no_description"])
    assert _no_residual(out)
    assert "None" not in out


def test_null_collection_does_not_raise_no_residual(mod):
    out = mod.fill_prompt(_TEMPLATE, _ART["artifact_null_collection"])
    assert _no_residual(out)
    assert "None" not in out


def test_unavailable_transcript_uses_marker(mod):
    out = mod.fill_prompt(_TEMPLATE, _ART["artifact_no_transcript"])
    assert "(no transcript available)" in out
    assert _no_residual(out)


def test_unknown_placeholder_raises_value_error(mod):
    bad_template = "Intro {{video_title}} then {{unknown_field}} end."
    with pytest.raises(ValueError):
        mod.fill_prompt(bad_template, _ART["artifact_full"])


def test_template_without_placeholders_unchanged(mod):
    plain = "No placeholders here at all."
    assert mod.fill_prompt(plain, _ART["artifact_full"]) == plain


def test_does_not_mutate_artifact(mod):
    art = _ART["artifact_full"]
    before = copy.deepcopy(art)
    mod.fill_prompt(_TEMPLATE, art)
    assert art == before


def test_returns_string(mod):
    for key in ("artifact_full", "artifact_null_collection", "artifact_no_transcript"):
        assert isinstance(mod.fill_prompt(_TEMPLATE, _ART[key]), str)
