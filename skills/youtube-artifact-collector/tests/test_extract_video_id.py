"""T-S1-01 — extract_video_id. Spec: docs/specs/A1-T-S1-01-extract_video_id.spec.md"""

import pytest

from conftest import load_fixture

_INPUTS = load_fixture("inputs", "extract_video_id.json")
_EXPECTED = load_fixture("expected", "extract_video_id.json")

_VALID = list(zip(_INPUTS["valid"], _EXPECTED["valid_ids"]))
_INVALID = _INPUTS["invalid"]


@pytest.mark.parametrize("url_or_id, expected_id", _VALID)
def test_resolves_to_video_id(mod, url_or_id, expected_id):
    assert mod.extract_video_id(url_or_id) == expected_id


@pytest.mark.parametrize("bad_input", _INVALID)
def test_unrecognized_input_raises_value_error(mod, bad_input):
    with pytest.raises(ValueError):
        mod.extract_video_id(bad_input)
