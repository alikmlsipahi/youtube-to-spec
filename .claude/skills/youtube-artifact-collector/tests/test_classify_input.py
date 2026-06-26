"""T-S1-03 — classify_input. Spec: docs/specs/A1-T-S1-03-classify_input.spec.md"""

import argparse

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "classify_input.json")["cases"]
_MODES = load_fixture("expected", "classify_input.json")["modes"]

_PAIRS = list(zip(_CASES, _MODES))


@pytest.mark.parametrize("case, expected_mode", _PAIRS)
def test_classify_input(mod, case, expected_mode):
    args = argparse.Namespace(urls=list(case["urls"]), playlist=case["playlist"])
    assert mod.classify_input(args) == expected_mode
