"""Opt-in integration: Skill 1 collects real metadata + transcript to disk.

Mirrors gate I-01. Runs only with RUN_INTEGRATION=1 and network (see conftest).
Assertions are intentionally loose (structure, not exact counts) so the test is
robust to upstream caption/metadata changes.
"""

import json
import subprocess

import pytest

from conftest import SKILL1_SCRIPT

VIDEO_ID = "jNQXAC9IVRw"  # "Me at the zoo" — a stable public video with auto captions


@pytest.mark.integration
def test_skill1_single_video_writes_artifact(require_network, tmp_path):
    result = subprocess.run(
        ["uv", "run", str(SKILL1_SCRIPT), VIDEO_ID, "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr

    artifact_path = tmp_path / "_singles" / f"{VIDEO_ID}.json"
    assert artifact_path.exists(), "per-video JSON was not written"

    art = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert art.get("schema_version"), "artifact missing schema_version"

    transcript = art.get("transcript") or {}
    segments = transcript.get("segments") or []
    assert segments, "expected a non-empty segment transcript"

    # segment indexes are the stable address — contiguous from 0
    indexes = [s.get("index") for s in segments]
    assert indexes == list(range(len(segments)))

    # the readable Markdown view is written alongside the JSON
    assert (tmp_path / "_singles" / f"{VIDEO_ID}.md").exists()
