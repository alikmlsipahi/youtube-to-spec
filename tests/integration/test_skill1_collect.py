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
- **the permanent-failure gate** is deterministic on any network: a bogus video
  id fails everywhere, so it needs no fixture and no caption luck.
- **the drift gate** manufactures the failure it needs, because the failure it
  gates cannot be waited for: it runs a *copy* of the script with one caption
  signal renamed, so a real failure the classifier would recognize arrives
  unrecognized instead. It needs no caption luck either — its video's captions
  are switched off, so the failure lands immediately rather than after a
  rate-limit budget.
"""

import json
import subprocess
from pathlib import Path

import pytest

from conftest import SKILL1_SCRIPT

VIDEO_ID = "fl1DSmwQKKY"  # "What is Claude Code?" by Claude — public video with auto captions

# Syntactically a video id (11 chars), but no such video exists — so metadata
# fetch fails permanently, from any network, without a fixture to keep alive.
# Stands in for the private/deleted videos this path really serves.
BOGUS_VIDEO_ID = "zzzzzzzzzzz"

# A real video with its captions switched off: metadata fetches normally, and the
# transcript library refuses on any network, immediately, with no rate-limit budget
# to burn first. Blender's own upload of its own film — old, famous, and about as
# unlikely to be deleted or reworked as a YouTube fixture gets. What makes it usable
# here is that its failure is *recognized* today, which is what gives the drift
# something to break.
CAPTIONLESS_VIDEO_ID = "aqz-KE-bpKQ"

# The single string the drifted copy rewrites: the class name that makes a
# captions-disabled video a recognized permanent failure rather than an unrecognized
# one. Renaming it is precisely what the transcript library renaming its own
# exception would do to this collector.
RECOGNIZED_TRANSCRIPT_SIGNAL = '"TranscriptsDisabled"'
DRIFTED_TRANSCRIPT_SIGNAL = '"TranscriptsDisabledRenamedUpstream"'

# The transcript library's own words for the failure above, which the collector never
# writes and could not invent. Seeing them on stderr is the proof that the *raw*
# unrecognized text was reported, rather than a templated summary of it.
RAW_FAILURE_TEXT = "subtitles are disabled"


def _run(tmp_path, *extra) -> subprocess.CompletedProcess:
    """Run Skill 1 on VIDEO_ID into tmp_path; return the completed process."""
    return _run_video(tmp_path, VIDEO_ID, *extra)


def _run_video(tmp_path, video_id, *extra) -> subprocess.CompletedProcess:
    """Run Skill 1 on an arbitrary video id into tmp_path."""
    return subprocess.run(
        ["uv", "run", str(SKILL1_SCRIPT), video_id, "--root", str(tmp_path), *extra],
        capture_output=True,
        text=True,
        timeout=600,
    )


def _run_drifted(script, root, video_id, *extra) -> subprocess.CompletedProcess:
    """Run a *copy* of Skill 1 rather than the real script; otherwise `_run_video`.

    The copy is what lets the drift gate perturb the signal table without touching
    the file under test: the script is a self-contained PEP-723 script that imports
    nothing relative to itself, so `uv run` executes a copy from anywhere exactly as
    it executes the original.
    """
    return subprocess.run(
        ["uv", "run", str(script), video_id, "--root", str(root), *extra],
        capture_output=True,
        text=True,
        timeout=600,
    )


def _drifted_script(tmp_path) -> Path:
    """Skill 1, copied with one caption-failure signal renamed and nothing else changed.

    This is the whole trick behind the drift gate, and its honesty rests on how
    little it changes: the classifier, the fetch, the orchestration and the failure
    itself are all the real ones running against the real YouTube. Only the table of
    strings the classifier matches against has moved — which is not a fake failure,
    it is a faithful model of the *one* thing that actually goes wrong in the wild,
    where the wording drifts underneath a signal list that cannot know it.
    """
    source = SKILL1_SCRIPT.read_text(encoding="utf-8")

    # A sabotage that no longer applies is worse than no gate, because it keeps
    # reporting green: the copy would simply be the original, the failure would be
    # recognized, and the artifact would be written exactly as the unmutated control
    # writes it — so every assertion below would pass without the unknown path ever
    # existing. Refuse to run rather than "pass" on a mutation that missed.
    assert source.count(RECOGNIZED_TRANSCRIPT_SIGNAL) == 1, (
        f"expected exactly one {RECOGNIZED_TRANSCRIPT_SIGNAL} in the collector to rename, "
        f"found {source.count(RECOGNIZED_TRANSCRIPT_SIGNAL)} — the signal table moved and "
        "this gate is no longer perturbing anything; re-target it before trusting it again"
    )

    script_dir = tmp_path / "drifted-script"
    script_dir.mkdir()
    script = script_dir / "extract_artifacts_drifted.py"
    script.write_text(
        source.replace(RECOGNIZED_TRANSCRIPT_SIGNAL, DRIFTED_TRANSCRIPT_SIGNAL),
        encoding="utf-8",
    )
    return script


def _artifacts(tmp_path) -> list[Path]:
    """The per-video JSON artifacts written under tmp_path, if any.

    Globs rather than rebuilding the name: since [v2.1] the basename is derived
    from the video *title*, and the plan tells consumers to resolve files through
    the manifest, never by reconstructing the name.
    """
    singles = tmp_path / "_singles"
    return sorted(singles.glob("*.json")) if singles.is_dir() else []


def _was_rate_limited(result) -> bool:
    """Whether the run gave up on a transient block rather than a real failure.

    Excludes a crash explicitly. This helper is what lets a test take the "that was
    environmental, skip" escape route, so a crash reaching it would be excused as a
    network condition and never reported — the worst way to lose a real regression.
    A run that died after printing the warning is not a rate-limited run.
    """
    return (
        result.returncode != 0
        and "Rate-limited" in result.stderr
        and "Traceback (most recent call last)" not in result.stderr
    )


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


@pytest.mark.integration
def test_skill1_single_permanent_failure_is_not_silent(require_network, tmp_path):
    """A run that collects nothing because the video is gone must say so, and fail.

    A single permanently-unavailable video (private, deleted, bogus id) exits 0,
    writes no file, and prints nothing: the run claims success while collecting
    nothing and explaining nothing. Anything driving the script from outside — a
    CI job, a shell loop — reads that exit 0 as "done".

    The rate-limited sibling already warns and exits 1 when nothing was collected,
    so today the two failure kinds behave inconsistently. This pins the permanent
    one to the same contract. Partial success is *not* covered here and is
    unchanged: a playlist that lands some members still exits 0 and lists its
    failures in the manifest (see test_skill1_playlist.py).

    Unlike the rest of this file, this gate is deterministic: a bogus id fails on
    any network, blocked or not, so it never rides on caption availability.
    """
    result = _run_video(tmp_path, BOGUS_VIDEO_ID)

    # A rate limit would also exit non-zero and also print — it would satisfy every
    # assertion below without the permanent path ever running. That is an
    # environmental confound, not evidence, so refuse to pass on it.
    if _was_rate_limited(result):
        pytest.skip(
            "the run was rate-limited before it could resolve the video as "
            "permanently unavailable; the permanent-failure path did not execute"
        )

    # Check this before the exit code: a crash also exits non-zero and also prints,
    # so it satisfies every assertion below without the code ever having handled
    # anything. Failing *correctly* and failing *apart* are not the same result, and
    # only this line can tell them apart. Caught for real while fixing this defect —
    # a NameError in the exit rule produced a textbook-looking exit 1 + stderr.
    assert "Traceback (most recent call last)" not in result.stderr, (
        f"the run crashed rather than reporting a failed video:\n{result.stderr}"
    )
    assert result.returncode != 0, (
        "collecting a permanently-unavailable video exited 0 — a caller sees "
        "success for a run that collected nothing"
    )
    assert result.stderr.strip(), (
        "nothing was collected and nothing was said about why — the failure has "
        "no manifest to land in either, so stderr is the only report there is"
    )
    assert BOGUS_VIDEO_ID in result.stderr, (
        "stderr does not name the video that failed; with no artifact and no "
        "manifest, the id is the only thing identifying it"
    )

    # Nothing anywhere under the root — not the artifact, not a stub, not a manifest.
    assert not [p for p in tmp_path.rglob("*") if p.is_file()], (
        "a video that could not be fetched left files behind: "
        f"{[str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*') if p.is_file()]}"
    )


@pytest.mark.integration
def test_skill1_never_writes_an_unrecognized_transcript_failure(require_network, tmp_path):
    """An unrecognized failure is not evidence that a video has no captions.

    `classify_failure` is a wall of string literals matched against someone else's
    copy. When YouTube or the transcript library rewords a message the signal stops
    matching, the failure falls through, and the collector writes the video down as
    "this video has no captions" — the same silent, permanent data loss the
    rate-limit work exists to remove, arriving through a different door and breaking
    no test on the way in. Only a *recognized* permanent failure licenses recording
    that conclusion as fact; an unrecognized one licenses nothing.

    Drift cannot be waited for — a fixture pins text already seen, and drift is by
    definition text nobody has seen — so this gate manufactures it. What it perturbs
    is one string in a table; the video, the failure, the classifier, the fetch and
    the orchestration are all real, and the failure really does arrive from YouTube.

    The gate is the *pair* of runs, not either one:

    - the **control** (unmutated script, same video) pins the licensed half — this
      failure is recognized, so the artifact is written, and it is that write which
      makes the drifted run's empty root mean something. Without it, a video that
      simply failed to fetch would satisfy a "wrote nothing" assertion forever.
    - the **drifted** run pins the half that does not exist yet: rename the signal,
      and the identical failure must now be reported and *not* written down.

    Not covered here: the `unrecognized` member status. It lives in a manifest, and a
    manifest only exists for a collection — gating it would mean finding a playlist
    that contains a captions-disabled member and then collecting every one of its
    members' transcripts, which is a fragile fixture and a lot of traffic aimed at
    the service whose rate limit this whole area is about. It stays a unit concern.
    """
    control_root = tmp_path / "control"
    drifted_root = tmp_path / "drifted"
    control_root.mkdir()
    drifted_root.mkdir()

    # --- control: the failure as the collector recognizes it today ---------------
    control = _run_video(control_root, CAPTIONLESS_VIDEO_ID)

    if _was_rate_limited(control):
        pytest.skip(
            "the control run was rate-limited before it could reach the caption "
            "failure (YouTube IP-block); the recognized-permanent path did not execute"
        )
    assert "Traceback (most recent call last)" not in control.stderr, (
        f"the control run crashed rather than collecting the video:\n{control.stderr}"
    )
    assert control.returncode == 0, (
        "the control run failed to collect a video that merely has its captions "
        f"switched off — either that is a regression, or the fixture video "
        f"{CAPTIONLESS_VIDEO_ID} is gone and needs replacing:\n{control.stderr}"
    )

    control_jsons = _artifacts(control_root)
    assert len(control_jsons) == 1, (
        "a recognized permanent transcript failure was not written as an artifact — "
        "a video that genuinely has no captions is complete, and is the one case that "
        f"licenses writing that down: {[p.name for p in control_jsons]}"
    )
    control_transcript = json.loads(
        control_jsons[0].read_text(encoding="utf-8")
    ).get("transcript") or {}

    # The fixture has to *fail* for this gate to have anything to drift. A video that
    # has since gained captions succeeds instead, so the drift below would perturb a
    # signal nothing ever matches and the run would write a perfectly good artifact.
    # That is upstream moving, not this code regressing — so skip, but say plainly
    # that the fixture has stopped serving and someone has to pick a new one.
    if control_transcript.get("available") or (control_transcript.get("available_tracks") or []):
        pytest.skip(
            f"the fixture video {CAPTIONLESS_VIDEO_ID} now offers captions, so it no "
            "longer produces the recognized caption failure this gate drifts; replace "
            "it with a video whose captions are switched off"
        )

    # --- drifted: the same failure, arriving unrecognized -------------------------
    drifted = _run_drifted(_drifted_script(tmp_path), drifted_root, CAPTIONLESS_VIDEO_ID)

    # A rate limit is still recognized in the copy (only the caption signal moved), so
    # a blocked run declines to write for a completely different and already-gated
    # reason. It would satisfy every assertion below while the unknown path never ran:
    # the confound that would turn this gate into a green light.
    if _was_rate_limited(drifted):
        pytest.skip(
            "the drifted run was rate-limited before it could reach the caption "
            "failure; the unrecognized-failure path did not execute"
        )

    # Before anything else, as the permanent-failure gate above learned the hard way:
    # a crash also exits non-zero, also prints, and also writes nothing, so it clears
    # every bar below without a line of handling existing.
    assert "Traceback (most recent call last)" not in drifted.stderr, (
        f"the run crashed rather than reporting an unrecognized failure:\n{drifted.stderr}"
    )

    # The point of the whole change. The control proved this same failure gets written
    # when it is recognized; unrecognized, the same evidence no longer supports the
    # same conclusion, so nothing may land — not the artifact, not a stub, not a
    # manifest. A written `available: false` here is the silent data loss itself:
    # `scan_existing` would index it and `--skip-existing` would skip it forever.
    leftovers = [p for p in drifted_root.rglob("*") if p.is_file()]
    assert not leftovers, (
        "an unrecognized transcript failure was written to disk as an artifact — the "
        "collector recorded 'this video has no captions' from a failure it did not "
        "recognize, which is the conclusion it has not earned: "
        f"{[str(p.relative_to(drifted_root)) for p in leftovers]}"
    )

    assert drifted.returncode != 0, (
        "the run collected nothing and exited 0 — the same lie the permanent-failure "
        "gate pins, told about a failure nobody has characterized"
    )
    assert CAPTIONLESS_VIDEO_ID in drifted.stderr, (
        "stderr does not name the video that failed; with no artifact and no manifest, "
        "the id is the only thing identifying it"
    )

    # The canary. An unrecognized failure is the only moment its evidence exists: a
    # drifted 429 that has since cleared can never be reproduced, and the text is the
    # only thing that tells a human *what* moved. A verdict alone reports that
    # something was not recognized while withholding the one detail that acts on it.
    assert RAW_FAILURE_TEXT in drifted.stderr.lower(), (
        "the unrecognized failure text was not reported — either the run swallowed it, "
        "or it printed a summary of its own instead of the text it did not recognize. "
        f"(If the transcript library has reworded {RAW_FAILURE_TEXT!r}, that is this "
        f"very drift one level up: re-read it off the failure and re-pin it.)\n"
        f"{drifted.stderr}"
    )
