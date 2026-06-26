"""T-S1-09 — build_manifest.
Spec: docs/specs/A3-T-S1-09-build_manifest.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "build_manifest.json")["cases"]
_EXPECTED = load_fixture("expected", "build_manifest.json")["manifests"]

_PARAMS = [
    pytest.param(case, manifest, id=case["name"])
    for case, manifest in zip(_CASES, _EXPECTED)
]

_BY_NAME = {c["name"]: c for c in _CASES}

_TOP_KEYS = {"collection", "members", "summary"}
_MEMBER_KEYS = {"position", "video_id", "title", "status", "reason", "files", "transcript"}


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_build_manifest_matches_expected(mod, case, expected):
    assert mod.build_manifest(case["collection"], case["members"]) == expected


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_top_level_keys(mod, case, expected):
    assert set(mod.build_manifest(case["collection"], case["members"]).keys()) == _TOP_KEYS


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_member_order_preserved(mod, case, expected):
    result = mod.build_manifest(case["collection"], case["members"])
    assert [m["video_id"] for m in result["members"]] == [m["video_id"] for m in case["members"]]
    assert [m["position"] for m in result["members"]] == [m["position"] for m in case["members"]]


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_each_member_has_canonical_keys(mod, case, expected):
    result = mod.build_manifest(case["collection"], case["members"])
    for member in result["members"]:
        assert set(member.keys()) == _MEMBER_KEYS


def test_failed_members_have_null_files_and_reason(mod):
    case = _BY_NAME["mixed_ok_and_failed_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    failed = [m for m in result["members"] if m["status"] != "ok"]
    assert failed, "fixture must contain failed members"
    for member in failed:
        assert member["files"] is None
        assert member["reason"] is not None


def test_failed_member_files_forced_null_even_if_provided(mod):
    case = _BY_NAME["mixed_ok_and_failed_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    # position 3 (CCCCCCCCCCC) is metadata_failed but its input record carried a files dict
    member = next(m for m in result["members"] if m["video_id"] == "CCCCCCCCCCC")
    assert member["status"] == "metadata_failed"
    assert member["files"] is None


def test_ok_members_keep_files(mod):
    case = _BY_NAME["mixed_ok_and_failed_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    for member in result["members"]:
        if member["status"] == "ok":
            assert member["files"] is not None


def test_summary_counts_mixed(mod):
    case = _BY_NAME["mixed_ok_and_failed_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    assert result["summary"] == {"total": 4, "ok": 2, "failed": 2, "no_transcript": 1}


def test_summary_counts_empty(mod):
    case = _BY_NAME["empty_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    assert result["members"] == []
    assert result["summary"] == {"total": 0, "ok": 0, "failed": 0, "no_transcript": 0}


def test_collection_passed_through(mod):
    case = _BY_NAME["mixed_ok_and_failed_members"]
    result = mod.build_manifest(case["collection"], case["members"])
    assert result["collection"] == case["collection"]
    assert result["collection"]["hidden_unavailable_count"] == 5
