"""T-S1-05 — build_video_block.
Spec: docs/specs/A2-T-S1-05-build_video_block.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "build_video_block.json")["cases"]
_EXPECTED = load_fixture("expected", "build_video_block.json")["blocks"]

_PARAMS = [
    pytest.param(case["meta"], block, id=case["name"])
    for case, block in zip(_CASES, _EXPECTED)
]

_CANONICAL_KEYS = {
    "id", "url", "title", "channel", "channel_id", "uploader", "upload_date",
    "duration_seconds", "description", "tags", "categories", "chapters",
    "default_language", "availability",
}


@pytest.mark.parametrize("meta, expected_block", _PARAMS)
def test_build_video_block(mod, meta, expected_block):
    assert mod.build_video_block(meta) == expected_block


@pytest.mark.parametrize("meta, expected_block", _PARAMS)
def test_build_video_block_has_exactly_canonical_keys(mod, meta, expected_block):
    assert set(mod.build_video_block(meta).keys()) == _CANONICAL_KEYS


def test_build_video_block_drops_unknown_fields(mod):
    full = _CASES[0]["meta"]
    result = mod.build_video_block(full)
    assert "view_count" not in result
    assert "thumbnails" not in result
    assert "extra_unknown_field" not in result
