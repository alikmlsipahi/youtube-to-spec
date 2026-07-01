"""Shared pytest setup for the youtube-artifact-collector unit tier.

The unit tests are strictly offline and deterministic. They import the target script
(`scripts/extract_artifacts.py`) by file path and stub its heavyweight network dependencies
(`yt_dlp`, `youtube_transcript_api`) in ``sys.modules`` *before* import, so the pure helpers
under test never require those packages to be installed and never touch the network.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).parent
SCRIPT_PATH = TESTS_DIR.parent / "scripts" / "extract_artifacts.py"
FIXTURES_DIR = TESTS_DIR / "fixtures"


def _stub_network_deps():
    """Install MagicMock stand-ins for the script's optional network deps.

    Top-level ``import yt_dlp`` / ``from youtube_transcript_api import ...`` in the target
    module then succeed without the real packages; the pure helpers exercised here never
    call into them.
    """
    for name in ("yt_dlp", "youtube_transcript_api"):
        sys.modules[name] = MagicMock(name=name)


@pytest.fixture(scope="session")
def mod():
    """Import and return the target module (`extract_artifacts`) offline.

    Skips the whole tier with a clear message if the script has not been implemented yet,
    so the suite can be authored (and collected) before the blind implementer writes code.
    """
    if not SCRIPT_PATH.exists():
        pytest.skip(f"not yet implemented: {SCRIPT_PATH}")
    _stub_network_deps()
    spec = importlib.util.spec_from_file_location("extract_artifacts", SCRIPT_PATH)
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
