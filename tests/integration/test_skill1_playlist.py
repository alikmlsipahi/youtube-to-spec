"""Opt-in integration: Skill 1 collects a real playlist into an ordered manifest.

Mirrors gate I-02, which until now existed only as a prose prompt for a human to
run — which is why the [v2.1] rename to `<position>-<slug>` basenames drifted past
the suite unnoticed. This is the gate that should have caught it.

Runs only with RUN_INTEGRATION=1 and network (see conftest). Uses --metadata-only:
transcripts are IP-blocked from some networks (see I-01) and say nothing about
playlist enumeration, so skipping them halves the calls and removes that coupling.

Assertions are structural and internally consistent rather than pinned to upstream
counts. The playlist really does hold 24 members / 5 unavailable today, but pinning
those would break the moment the channel adds a video — the exact mistake I-01 made.
What is pinned is what the code owns: ordering, manifest/disk agreement, graceful
degradation, and the [v2.1] naming policy.
"""

import json
import re
import subprocess

import pytest

from conftest import SKILL1_SCRIPT

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLk-DU0q6QMPP7RfYiyhiJY7qQOXoaFKHL"


@pytest.fixture(scope="module")
def collected_playlist(tmp_path_factory):
    """Collect the playlist once; both tests read the same manifest."""
    if not _opted_in_with_network():
        pytest.skip("integration opt-in + network required")

    root = tmp_path_factory.mktemp("playlist")
    result = subprocess.run(
        ["uv", "run", str(SKILL1_SCRIPT), PLAYLIST_URL, "--metadata-only", "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr

    collections = [p for p in root.iterdir() if p.is_dir()]
    assert len(collections) == 1, f"expected one collection dir, got {[p.name for p in collections]}"

    manifest_path = collections[0] / "_manifest.json"
    assert manifest_path.exists(), "_manifest.json was not written"

    return collections[0], json.loads(manifest_path.read_text(encoding="utf-8"))


def _opted_in_with_network() -> bool:
    from conftest import _has_network, _opted_in

    return _opted_in() and _has_network("www.youtube.com")


@pytest.mark.integration
def test_skill1_playlist_manifest_is_ordered_and_consistent(collected_playlist):
    _, manifest = collected_playlist

    collection = manifest["collection"]
    assert collection["type"] == "playlist"
    assert collection["id"], "collection carries no playlist id"
    assert collection["title"], "collection carries no title"

    members = manifest["members"]
    assert members, "playlist produced no members"

    # Positions are the playlist relation: contiguous 1..N, in order.
    assert [m["position"] for m in members] == list(range(1, len(members) + 1))

    # The regex anchors on the stable "<N> unavailable videos" phrase in yt-dlp's
    # stderr. Its own spec (A3-T-S1-10) flagged that the wording could drift and
    # deferred the live check to this gate — and the wording HAS since drifted, so
    # this assertion is the one proving the anchor still holds against real output.
    # Pinned as > 0, not == 5: the count is upstream data, the parse is ours.
    assert collection["hidden_unavailable_count"] > 0, (
        "no hidden-unavailable count parsed from real yt-dlp stderr — "
        "the anchor phrase may have drifted"
    )

    summary = manifest["summary"]
    assert summary["total"] == len(members)
    assert summary["ok"] + summary["failed"] == summary["total"]
    assert summary["ok"] == sum(1 for m in members if m["status"] == "ok")
    assert summary["failed"] == sum(1 for m in members if m["status"] != "ok")


@pytest.mark.integration
def test_skill1_playlist_degrades_gracefully_and_names_by_title(collected_playlist):
    collection_dir, manifest = collected_playlist
    members = manifest["members"]

    ok = [m for m in members if m["status"] == "ok"]
    failed = [m for m in members if m["status"] != "ok"]

    assert ok, "no member succeeded — the run tells us nothing about naming"

    # This playlist carries unavailable members, so degradation is actually
    # exercised rather than merely available. Losing them would silently reduce
    # what this gate covers, so treat it as a failure worth looking at.
    assert failed, (
        "expected at least one unavailable member — this playlist had 5; "
        "if upstream restored them, this gate no longer covers degradation"
    )

    # Failed members are listed with a reason, never dropped, and carry no files.
    for member in failed:
        assert member["status"] == "metadata_failed"
        assert member["reason"], "failed member carries no reason"
        assert member["files"] is None
        assert member["video_id"], "failed member lost its video id"

    for member in ok:
        files = member["files"]
        assert files and files["json"], "ok member has no json file recorded"

        # The manifest is the resolution path, so what it names must exist.
        json_path = collection_dir / files["json"]
        assert json_path.exists(), f"manifest names {files['json']} but it is not on disk"

        # [v2.1]: <position>-<title-slug>, not the video id.
        stem = json_path.stem
        assert re.match(r"^\d{2,}-", stem), f"{stem} carries no zero-padded position prefix"
        assert stem != member["video_id"], f"{stem} is named after the video id, not its title"
        assert not stem.endswith(member["video_id"]), f"{stem} fell back to the video id"
