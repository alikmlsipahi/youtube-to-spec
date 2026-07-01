"""T-S2-05 — composite-key uniqueness (dedupe_requirements).
Spec: docs/specs/A4-T-S2-05-composite_key_uniqueness.spec.md
"""

import copy

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "dedupe_requirements.json")["cases"]
_EXPECTED = load_fixture("expected", "dedupe_requirements.json")["deduped"]

_PARAMS = [
    pytest.param(case["requirements"], expected, id=case["name"])
    for case, expected in zip(_CASES, _EXPECTED)
]

_BY_NAME = {c["name"]: c for c in _CASES}


@pytest.mark.parametrize("requirements, expected", _PARAMS)
def test_dedupe_matches_expected(mod, requirements, expected):
    assert mod.dedupe_requirements(requirements) == expected


def test_same_id_two_videos_both_kept(mod):
    reqs = _BY_NAME["same_id_two_videos_both_kept"]["requirements"]
    result = mod.dedupe_requirements(reqs)
    assert len(result) == 2
    assert {r["source_video_id"] for r in result} == {"VIDAAAAAAAA", "VIDBBBBBBBB"}


def test_diff_id_same_video_both_kept(mod):
    reqs = _BY_NAME["diff_id_same_video_both_kept"]["requirements"]
    assert len(mod.dedupe_requirements(reqs)) == 2


def test_exact_duplicate_keeps_first(mod):
    reqs = _BY_NAME["exact_duplicate_collapses_first_wins"]["requirements"]
    result = mod.dedupe_requirements(reqs)
    assert len(result) == 1
    assert result[0]["text"] == "first"


def test_interleaved_order_preserved(mod):
    reqs = _BY_NAME["interleaved_duplicate_preserves_order"]["requirements"]
    result = mod.dedupe_requirements(reqs)
    assert [r["id"] for r in result] == ["REG-ADD-001", "REG-DEL-002"]


def test_no_duplicates_unchanged(mod):
    reqs = _BY_NAME["no_duplicates_unchanged"]["requirements"]
    assert mod.dedupe_requirements(reqs) == reqs


def test_empty_list(mod):
    assert mod.dedupe_requirements([]) == []


def test_does_not_mutate_input(mod):
    reqs = _BY_NAME["interleaved_duplicate_preserves_order"]["requirements"]
    before = copy.deepcopy(reqs)
    mod.dedupe_requirements(reqs)
    assert reqs == before
