"""Opt-in integration: Skill 1 collects real metadata + transcript to disk.

Mirrors gate I-01. Runs only with RUN_INTEGRATION=1 and network (see conftest).
Assertions are intentionally loose (structure, not exact counts) so the test is
robust to upstream caption/metadata changes.

Split in two so the naming/metadata half stays verifiable even where YouTube
IP-blocks transcript fetching: that block is environmental, not a regression,
and it must not mask what it doesn't actually affect.
"""

import json
import subprocess
from pathlib import Path

import pytest

from conftest import SKILL1_SCRIPT

VIDEO_ID = "fl1DSmwQKKY"  # "What is Claude Code?" by Claude — public video with auto captions


def _collect(tmp_path) -> tuple[Path, dict]:
    """Run Skill 1 on VIDEO_ID into tmp_path; return (artifact_path, parsed artifact).

    Locates the artifact by globbing rather than rebuilding its name: since [v2.1]
    the basename is derived from the video *title*, and the plan tells consumers to
    resolve files through the manifest, never by reconstructing the name.
    """
    result = subprocess.run(
        ["uv", "run", str(SKILL1_SCRIPT), VIDEO_ID, "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr

    singles = tmp_path / "_singles"
    jsons = sorted(singles.glob("*.json"))
    assert len(jsons) == 1, f"expected exactly one artifact, got {[p.name for p in jsons]}"

    return jsons[0], json.loads(jsons[0].read_text(encoding="utf-8"))


@pytest.mark.integration
def test_skill1_single_video_writes_titled_artifact(require_network, tmp_path):
    artifact_path, art = _collect(tmp_path)

    assert art["video"]["id"] == VIDEO_ID, "artifact does not describe the requested video"
    assert art.get("schema_version"), "artifact missing schema_version"

    # [v2.1] the basename is the title slug; the video id is only a fallback for a
    # title that yields no usable slug, so seeing the raw id here means the naming
    # policy regressed.
    assert artifact_path.stem != VIDEO_ID, "artifact is named after the video id, not its title"

    # the readable Markdown view is written alongside the JSON, under the same basename
    assert (artifact_path.parent / f"{artifact_path.stem}.md").exists()


@pytest.mark.integration
def test_skill1_single_video_fetches_transcript(require_network, tmp_path):
    _, art = _collect(tmp_path)
    transcript = art.get("transcript") or {}

    # No tracks at all is a real signal (the source lost its captions); tracks that
    # exist but could not be fetched is YouTube blocking this IP — an environment
    # limit that says nothing about the code, so skip rather than fail or pass.
    tracks = transcript.get("available_tracks") or []
    assert tracks, "video exposes no caption tracks at all — the test source needs replacing"

    if not transcript.get("available"):
        pytest.skip(
            "caption tracks exist but the fetch failed (YouTube IP-block); "
            "transcript cannot be verified from this network"
        )

    segments = transcript.get("segments") or []
    assert segments, "expected a non-empty segment transcript"

    # segment indexes are the stable address — contiguous from 0
    indexes = [s.get("index") for s in segments]
    assert indexes == list(range(len(segments)))
