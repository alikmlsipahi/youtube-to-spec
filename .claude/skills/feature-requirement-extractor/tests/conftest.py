"""Shared pytest setup for the feature-requirement-extractor unit tier.

The unit tests are strictly offline and deterministic. They import the OpenAI-engine
script (`scripts/extract_requirements.py`) by file path and stub its heavyweight
network/optional dependencies (`openai`, `dotenv`) in ``sys.modules`` *before* import,
so the pure helpers under test never require those packages to be installed and never
touch the network or the OpenAI API.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).parent
SCRIPT_PATH = TESTS_DIR.parent / "scripts" / "extract_requirements.py"
FIXTURES_DIR = TESTS_DIR / "fixtures"


def _stub_external_deps():
    """Install MagicMock stand-ins for the script's optional deps.

    Top-level ``import openai`` / ``from dotenv import load_dotenv`` in the target
    module then succeed without the real packages; the pure helpers exercised here
    never call into them.
    """
    for name in ("openai", "dotenv"):
        sys.modules[name] = MagicMock(name=name)


@pytest.fixture(scope="session")
def mod():
    """Import and return the target module (`extract_requirements`) offline.

    Skips the whole tier with a clear message if the script has not been implemented
    yet, so the suite can be authored (and collected) before the blind implementer
    writes code.
    """
    if not SCRIPT_PATH.exists():
        pytest.skip(f"not yet implemented: {SCRIPT_PATH}")
    _stub_external_deps()
    spec = importlib.util.spec_from_file_location("extract_requirements", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def fixtures_dir():
    return FIXTURES_DIR


def load_fixture(*parts):
    """Read a JSON fixture under ``tests/fixtures`` (e.g. ``load_fixture('inputs', 'x.json')``)."""
    path = FIXTURES_DIR.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_fixture(*parts):
    """Read a non-JSON text fixture (e.g. a prompt template) under ``tests/fixtures``."""
    path = FIXTURES_DIR.joinpath(*parts)
    return path.read_text(encoding="utf-8")
