"""T-S1-10 — parse_hidden_unavailable.
Spec: docs/specs/A3-T-S1-10-parse_hidden_unavailable.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "parse_hidden_unavailable.json")["cases"]
_COUNTS = load_fixture("expected", "parse_hidden_unavailable.json")["counts"]

_PARAMS = [
    pytest.param(case["stderr"], count, id=case["name"])
    for case, count in zip(_CASES, _COUNTS)
]

_BY_NAME = {c["name"]: c for c in _CASES}


@pytest.mark.parametrize("stderr, expected", _PARAMS)
def test_parse_hidden_unavailable(mod, stderr, expected):
    assert mod.parse_hidden_unavailable(stderr) == expected


@pytest.mark.parametrize("stderr, expected", _PARAMS)
def test_returns_int(mod, stderr, expected):
    assert isinstance(mod.parse_hidden_unavailable(stderr), int)


def test_absent_warning_returns_zero(mod):
    case = _BY_NAME["no_hidden_warning_other_warnings"]
    assert mod.parse_hidden_unavailable(case["stderr"]) == 0


def test_empty_string_returns_zero(mod):
    assert mod.parse_hidden_unavailable("") == 0


def test_double_digit_count(mod):
    case = _BY_NAME["double_digit_12_present"]
    assert mod.parse_hidden_unavailable(case["stderr"]) == 12
