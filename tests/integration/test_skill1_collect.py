"""Opt-in integration: Skill 1 collects real metadata + transcript to disk.

Mirrors gate I-01. Runs only with RUN_INTEGRATION=1 and network (see conftest).
Assertions are intentionally loose (structure, not exact counts) so the test is
robust to upstream caption/metadata changes.

Split in three so each half stays verifiable independently of the others:

- **naming/metadata** runs `--metadata-only`, so it is deterministic on any
  network. It asserts a naming policy that has nothing to do with transcripts,
  and it used to ride on a full collect purely by habit — which made it fail
  from a transcript-blocked network for a reason it does not test.
- **transcript** needs a real transcript, so it skips where YouTube IP-blocks
  the fetch. That block is environmental, not a regression.
- **the invariant** is checkable from *either* network, which is the point of
  having it: whatever the network does, a JSON on disk means a complete
  artifact.
"""

import json
import subprocess
from pathlib import Path

import pytest

from conftest import SKILL1_SCRIPT

VIDEO_ID = "fl1DSmwQKKY"  # "What is Claude Code?" by Claude — public video with auto captions


def _run(tmp_path, *extra) -> subprocess.CompletedProcess:
    """Run Skill 1 on VIDEO_ID into tmp_path; return the completed process."""
    return subprocess.run(
        ["uv", "run", str(SKILL1_SCRIPT), VIDEO_ID, "--root", str(tmp_path), *extra],
        capture_output=True,
        text=True,
        timeout=600,
    )


def _artifacts(tmp_path) -> list[Path]:
    """The per-video JSON artifacts written under tmp_path, if any.

    Globs rather than rebuilding the name: since [v2.1] the basename is derived
    from the video *title*, and the plan tells consumers to resolve files through
    the manifest, never by reconstructing the name.
    """
    singles = tmp_path / "_singles"
    return sorted(singles.glob("*.json")) if singles.is_dir() else []


def _was_rate_limited(result) -> bool:
    """Whether the run gave up on a transient block rather than a real failure."""
    return result.returncode != 0 and "Rate-limited" in result.stderr


@pytest.mark.integration
def test_skill1_single_video_writes_titled_artifact(require_network, tmp_path):
    # --metadata-only: this test is about naming, and naming does not depend on
    # captions. A full collect would tie it to transcript availability, which is
    # exactly what made it fail from a blocked network for an unrelated reason.
    result = _run(tmp_path, "--metadata-only")
    assert result.returncode == 0, result.stderr

    jsons = _artifacts(tmp_path)
    assert len(jsons) == 1, f"expected exactly one artifact, got {[p.name for p in jsons]}"
    artifact_path = jsons[0]
    art = json.loads(artifact_path.read_text(encoding="utf-8"))

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
    result = _run(tmp_path)

    # A transient block means the artifact is deliberately not written, so there is
    # nothing to read back. That is the contract, not a failure — but it says
    # nothing about the code, so skip rather than pass.
    if _was_rate_limited(result):
        pytest.skip(
            "transcript fetch was rate-limited after its full retry budget "
            "(YouTube IP-block); transcript cannot be verified from this network"
        )

    assert result.returncode == 0, result.stderr
    jsons = _artifacts(tmp_path)
    assert len(jsons) == 1, f"expected exactly one artifact, got {[p.name for p in jsons]}"
    art = json.loads(jsons[0].read_text(encoding="utf-8"))
    transcript = art.get("transcript") or {}

    tracks = transcript.get("available_tracks") or []
    assert tracks, "video exposes no caption tracks at all — the test source needs replacing"
    assert transcript.get("available"), "artifact written with an unavailable transcript"

    segments = transcript.get("segments") or []
    assert segments, "expected a non-empty segment transcript"

    # segment indexes are the stable address — contiguous from 0
    indexes = [s.get("index") for s in segments]
    assert indexes == list(range(len(segments)))


@pytest.mark.integration
def test_skill1_never_writes_a_transiently_blocked_transcript(require_network, tmp_path):
    """A JSON on disk means a complete artifact — from either network.

    This is the gate on the bug the retry work exists to remove: a rate-limited
    transcript used to be written as an ordinary `available: false` artifact,
    indistinguishable from a video that genuinely has no captions. `scan_existing`
    then indexed it and the next `--skip-existing` run skipped it forever, so the
    block became permanent silent data loss.

    Unlike its two siblings this asserts in *both* environments, which is what
    makes it a real gate rather than a network-dependent one: blocked, it pins
    that nothing was written; unblocked, it pins that what was written is whole.
    """
    result = _run(tmp_path)
    jsons = _artifacts(tmp_path)

    if _was_rate_limited(result):
        assert not jsons, (
            "a transiently-blocked transcript was written to disk — "
            "--skip-existing would skip it forever and the block would become permanent"
        )
        return

    assert result.returncode == 0, result.stderr
    for path in jsons:
        art = json.loads(path.read_text(encoding="utf-8"))
        transcript = art.get("transcript") or {}
        if transcript.get("available"):
            continue
        # The one legitimate way to be on disk without a transcript: the video
        # genuinely has no captions to fetch. Tracks on offer means it had some
        # and we failed to get them, which is the case that must never land.
        assert not (transcript.get("available_tracks") or []), (
            f"{path.name} was written with caption tracks on offer but no transcript — "
            "a failed fetch recorded as a complete artifact"
        )
