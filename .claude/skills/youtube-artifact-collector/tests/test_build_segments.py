"""T-S1-07 — build_segments.
Spec: docs/specs/A2-T-S1-07-build_segments.spec.md
"""

from types import SimpleNamespace

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "build_segments.json")["cases"]
_EXPECTED = load_fixture("expected", "build_segments.json")["segment_lists"]

_PARAMS = [
    pytest.param(case["snippets"], segments, id=case["name"])
    for case, segments in zip(_CASES, _EXPECTED)
]


def _make_snippets(raw_snippets):
    """Build attribute-style snippet objects mimicking a FetchedTranscript's snippets."""
    return [SimpleNamespace(**s) for s in raw_snippets]


@pytest.mark.parametrize("raw_snippets, expected_segments", _PARAMS)
def test_build_segments(mod, raw_snippets, expected_segments):
    snippets = _make_snippets(raw_snippets)
    assert mod.build_segments(snippets) == expected_segments


def test_build_segments_text_byte_identical(mod):
    raw = _CASES[1]["snippets"]
    snippets = _make_snippets(raw)
    result = mod.build_segments(snippets)
    for produced, source in zip(result, raw):
        assert produced["text"] == source["text"]


def test_build_segments_index_is_zero_based_sequence(mod):
    snippets = _make_snippets(_CASES[0]["snippets"])
    result = mod.build_segments(snippets)
    assert [seg["index"] for seg in result] == list(range(len(snippets)))
