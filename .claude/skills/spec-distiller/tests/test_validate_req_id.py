"""T-S2-04 — validate_req_id.
Spec: docs/specs/A4-T-S2-04-validate_req_id.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "validate_req_id.json")


@pytest.mark.parametrize("req_id", _CASES["valid"])
def test_valid_ids(mod, req_id):
    assert mod.validate_req_id(req_id) is True


@pytest.mark.parametrize("req_id", _CASES["invalid"])
def test_invalid_ids(mod, req_id):
    assert mod.validate_req_id(req_id) is False


@pytest.mark.parametrize(
    "case",
    _CASES["embedding"],
    ids=[c["req_id"] + "|" + c["video_id"] for c in _CASES["embedding"]],
)
def test_video_id_embedding(mod, case):
    assert mod.validate_req_id(case["req_id"], case["video_id"]) is case["expected"]


def test_embedding_check_skipped_without_video_id(mod):
    # Same code that would fail the embedding check passes when no video_id is given.
    assert mod.validate_req_id("ABC-VID0-001") is True
    assert mod.validate_req_id("ABC-VID0-001", "VID0") is False
