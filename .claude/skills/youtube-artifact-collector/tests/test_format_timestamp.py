"""T-S1-02 — format_timestamp. Spec: docs/specs/A1-T-S1-02-format_timestamp.spec.md"""

import pytest

from conftest import load_fixture

_SECONDS = load_fixture("inputs", "format_timestamp.json")["seconds"]
_FORMATTED = load_fixture("expected", "format_timestamp.json")["formatted"]

_CASES = list(zip(_SECONDS, _FORMATTED))


@pytest.mark.parametrize("seconds, expected", _CASES)
def test_format_timestamp(mod, seconds, expected):
    assert mod.format_timestamp(seconds) == expected
