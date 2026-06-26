"""T-S1-06 — select_transcript_track.
Spec: docs/specs/A2-T-S1-06-select_transcript_track.spec.md
"""

from types import SimpleNamespace

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "select_transcript_track.json")["cases"]
_RESULTS = load_fixture("expected", "select_transcript_track.json")["results"]

_PARAMS = [
    pytest.param(case, result, id=case["name"])
    for case, result in zip(_CASES, _RESULTS)
]


def _make_tracks(raw_tracks):
    """Build attribute-style track objects mimicking youtube-transcript-api's Transcript."""
    return [SimpleNamespace(**t) for t in raw_tracks]


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_info_matches(mod, case, expected):
    tracks = _make_tracks(case["tracks"])
    _selected_track, info = mod.select_transcript_track(tracks, case["langs"])
    assert info == {
        "selected": expected["selected"],
        "available_tracks": expected["available_tracks"],
    }


@pytest.mark.parametrize("case, expected", _PARAMS)
def test_selected_track_identity(mod, case, expected):
    tracks = _make_tracks(case["tracks"])
    selected_track, _info = mod.select_transcript_track(tracks, case["langs"])
    if expected["selected_index"] is None:
        assert selected_track is None
    else:
        assert selected_track is tracks[expected["selected_index"]]
