"""T-S1-11 — graceful degradation: fetch_metadata returns None on subprocess failure.
Spec: docs/specs/A3-T-S1-11-graceful_degradation.spec.md

Offline: the yt-dlp subprocess is mocked via the stdlib ``subprocess.run`` so no
network/tool is touched. Patching the shared stdlib module object covers the
``import subprocess; subprocess.run(...)`` call convention.
"""

import json
import subprocess
from types import SimpleNamespace


def _fake_run(returncode, stdout="", stderr=""):
    def _run(*args, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _run


def test_nonzero_exit_returns_none(mod, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(1, stdout="", stderr="ERROR: unavailable"))
    assert mod.fetch_metadata("someVideoId") is None


def test_zero_exit_with_json_returns_dict(mod, monkeypatch):
    meta = {"id": "fl1DSmwQKKY", "title": "What is Claude Code?", "duration": 612}
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(meta)))
    result = mod.fetch_metadata("fl1DSmwQKKY")
    assert isinstance(result, dict)
    assert result == meta


def test_nonzero_exit_does_not_raise(mod, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(2, stderr="boom"))
    # Must degrade gracefully, never propagate / sys.exit.
    assert mod.fetch_metadata("anotherId00") is None


def test_failure_is_isolated_across_videos(mod, monkeypatch):
    """First video fails, second succeeds — the batch can continue."""
    meta_ok = {"id": "okvideoid000", "title": "Fine"}
    calls = {"n": 0}

    def _run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr="ERROR")
        return SimpleNamespace(returncode=0, stdout=json.dumps(meta_ok), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    first = mod.fetch_metadata("badvideoid00")
    second = mod.fetch_metadata("okvideoid000")
    assert first is None
    assert second == meta_ok
