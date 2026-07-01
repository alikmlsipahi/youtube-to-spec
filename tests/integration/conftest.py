"""Opt-in integration tier for the YouTube intelligence pipeline.

These tests hit the *real* network (YouTube via Skill 1) and the *real* OpenAI
API (Skill 2). They are deliberately isolated from the per-skill offline unit
suites: the documented unit commands target `skills/<skill>/tests/` and
never collect this directory, so normal runs stay fast, free, and deterministic.

They are **skipped by default** and only execute when explicitly opted in:

    RUN_INTEGRATION=1 uv run --with pytest --with openai --with python-dotenv \\
        pytest tests/integration -m integration -v

Each test additionally self-skips when its resource is unavailable (no network,
or no OPENAI_API_KEY) — so even opted-in, they never fail for lack of a key or
connectivity, and never incur a paid API call without a key present.
"""

import os
import socket
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL1_SCRIPT = REPO_ROOT / "skills/youtube-artifact-collector/scripts/extract_artifacts.py"
SKILL2_DIR = REPO_ROOT / "skills/spec-distiller"
SKILL2_SCRIPT = SKILL2_DIR / "scripts/extract_requirements.py"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: opt-in test hitting real network / OpenAI (skipped by default)",
    )


def _opted_in() -> bool:
    return os.environ.get("RUN_INTEGRATION") == "1"


def _has_network(host: str, port: int = 443, timeout: float = 4.0) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


@pytest.fixture
def require_network():
    if not _opted_in():
        pytest.skip("integration opt-in: set RUN_INTEGRATION=1")
    if not _has_network("www.youtube.com"):
        pytest.skip("no network to youtube.com")


@pytest.fixture
def openai_key():
    """Return a present OPENAI_API_KEY (loading the skill .env if needed) or skip.

    Secret-safe: the value is only handed to the OpenAI client, never logged.
    """
    if not _opted_in():
        pytest.skip("integration opt-in: set RUN_INTEGRATION=1")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        env_path = SKILL2_DIR / ".env"
        if env_path.exists():
            try:
                from dotenv import dotenv_values

                key = dotenv_values(env_path).get("OPENAI_API_KEY")
            except Exception:  # pragma: no cover - dotenv optional
                key = None
    if not key:
        pytest.skip("no OPENAI_API_KEY (env or skill .env)")
    if not _has_network("api.openai.com"):
        pytest.skip("no network to api.openai.com")
    return key
