"""Shared pytest fixtures / import wiring for the youtube-artifact-collector tests.

Makes ``from extract_artifacts import ...`` resolve to the skill's script module
(`scripts/extract_artifacts.py`) without any packaging, matching the PEP-723
single-script style used by the skill.
"""

import argparse
import json
import sys
from pathlib import Path

import pytest

# --- import path wiring --------------------------------------------------- #
_TESTS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _TESTS_DIR.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# --- fixture access helpers ---------------------------------------------- #
@pytest.fixture
def inputs_dir() -> Path:
    """Directory holding captured / hand-authored input fixtures."""
    return _TESTS_DIR / "fixtures" / "inputs"


@pytest.fixture
def load_input(inputs_dir):
    """Load a JSON fixture from fixtures/inputs/ by filename."""

    def _load(name: str):
        return json.loads((inputs_dir / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def make_args():
    """Build the parsed-CLI object that ``classify_input`` consumes.

    Mirrors the Skill 1 argparse namespace: the positional ``url_or_id`` values
    (a list) plus the boolean ``--playlist`` flag.
    """

    def _make(inputs, playlist: bool = False) -> argparse.Namespace:
        if isinstance(inputs, str):
            inputs = [inputs]
        return argparse.Namespace(url_or_id=list(inputs), playlist=playlist)

    return _make
