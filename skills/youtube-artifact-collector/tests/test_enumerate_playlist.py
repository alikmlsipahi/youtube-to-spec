"""T-S1-15 — enumerate_playlist.
Spec: docs/specs/A6-T-S1-15-enumerate_playlist.spec.md

Offline: the ``yt-dlp --flat-playlist --dump-single-json`` subprocess is mocked via the
stdlib ``subprocess.run`` so no network is touched. Behavior is pinned on the mocked
return code / stdout / stderr only — never on the exact yt-dlp argument vector, which the
spec leaves to the implementer (§Assumptions).

Deliberately untested (spec §NEEDS CLARIFICATION): empty playlist, missing playlist-level
keys, an entry lacking an id, a non-playlist URL, and whether --sleep-requests applies here.
"""

import json
import subprocess
from types import SimpleNamespace

import pytest

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp"

# yt-dlp's hidden-unavailable WARNING, embedded among unrelated stderr lines.
# Wording per the T-S1-10 reuse contract: the count immediately precedes "unavailable videos".
STDERR_WITH_WARNING = (
    "[youtube:tab] Extracting URL: https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp\n"
    "WARNING: [youtube:tab] YouTube said: INFO - 5 unavailable videos are hidden\n"
    "[youtube:tab] Downloading just the video, but the playlist was requested\n"
)

STDERR_NO_WARNING = (
    "[youtube:tab] Extracting URL: https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp\n"
    "WARNING: unrelated deprecation notice\n"
)


def _fake_run(returncode, stdout="", stderr=""):
    def _run(*args, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return _run


def _entry(video_id, title):
    return {"id": video_id, "title": title, "url": f"https://youtu.be/{video_id}"}


def _playlist_doc(entries):
    """A small fake flat-playlist document, shaped like yt-dlp --dump-single-json output."""
    return {
        "_type": "playlist",
        "id": "PLf2m1LSmwQKKY0examp",
        "title": "Claude Code Deep Dive",
        "uploader": "Anthropic",
        "entries": entries,
    }


# Intentionally NOT in alphabetical order by id or title: sorting would be detectable.
ORDERED_ENTRIES = [
    _entry("zAbC1234567", "Zebra: getting started"),
    _entry("mNoP7654321", "Alpha: the middle one"),
    _entry("aXyZ0011223", "Mango: the last one"),
]

MIXED_ENTRIES = [
    _entry("okVideo0001", "First available"),
    _entry("privVideo02", None),  # unavailable member: listed, with a null title
    _entry("okVideo0003", "Third available"),
    _entry("delVideo04x", None),  # unavailable member: listed, with a null title
]


# --- failure paths: always None, never raise --------------------------------------


@pytest.mark.parametrize("returncode", [1, 2])
def test_nonzero_exit_returns_none(mod, monkeypatch, returncode):
    monkeypatch.setattr(
        subprocess, "run", _fake_run(returncode, stdout="", stderr="ERROR: playlist is private")
    )
    assert mod.enumerate_playlist(PLAYLIST_URL) is None


def test_unparseable_stdout_returns_none(mod, monkeypatch):
    """Return code 0 but garbage on stdout must not propagate a parse exception."""
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="not json at all {", stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) is None


def test_empty_stdout_returns_none(mod, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="", stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) is None


def test_missing_yt_dlp_executable_returns_none(mod, monkeypatch):
    """yt-dlp not installed → FileNotFoundError → graceful None, not an exception."""

    def _run(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory: 'yt-dlp'")

    monkeypatch.setattr(subprocess, "run", _run)
    assert mod.enumerate_playlist(PLAYLIST_URL) is None


def test_subprocess_error_returns_none(mod, monkeypatch):
    """Any other subprocess error degrades to None as well."""

    def _run(*args, **kwargs):
        raise subprocess.SubprocessError("subprocess blew up")

    monkeypatch.setattr(subprocess, "run", _run)
    assert mod.enumerate_playlist(PLAYLIST_URL) is None


# --- success path: playlist identity ----------------------------------------------


def test_success_returns_playlist_identity(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert isinstance(result, dict)
    assert result["id"] == "PLf2m1LSmwQKKY0examp"
    assert result["title"] == "Claude Code Deep Dive"
    assert result["uploader"] == "Anthropic"


def test_returned_dict_has_exactly_the_contract_keys(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert set(result) == {"id", "title", "uploader", "entries", "hidden_unavailable_count"}


def test_entry_records_carry_the_thin_flat_listing_fields(mod, monkeypatch):
    """Each entries record is {id, title} — the thin fields the flat listing supplies."""
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    for record in result["entries"]:
        assert set(record) == {"id", "title"}


# --- success path: order is the contract ------------------------------------------


def test_entries_preserve_playlist_order(mod, monkeypatch):
    """One record per member, in the same order the document listed them."""
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert [e["id"] for e in result["entries"]] == [
        "zAbC1234567",
        "mNoP7654321",
        "aXyZ0011223",
    ]
    assert [e["title"] for e in result["entries"]] == [
        "Zebra: getting started",
        "Alpha: the middle one",
        "Mango: the last one",
    ]


def test_repeated_member_is_not_deduplicated(mod, monkeypatch):
    """A video listed twice stays twice — dropping it would shift later positions."""
    twice = [
        _entry("repeatVid01", "Intro"),
        _entry("otherVid002", "Middle"),
        _entry("repeatVid01", "Intro"),
    ]
    doc = _playlist_doc(twice)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert [e["id"] for e in result["entries"]] == [
        "repeatVid01",
        "otherVid002",
        "repeatVid01",
    ]


# --- success path: unavailable members are enumerated, not omitted -----------------


def test_null_title_members_stay_in_entries_at_their_positions(mod, monkeypatch):
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert len(result["entries"]) == 4
    assert [e["id"] for e in result["entries"]] == [
        "okVideo0001",
        "privVideo02",
        "okVideo0003",
        "delVideo04x",
    ]


def test_null_title_is_preserved_not_repaired(mod, monkeypatch):
    """Passed through exactly as yt-dlp reported it — no coercion to '' or to the id."""
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert result["entries"][1]["title"] is None
    assert result["entries"][3]["title"] is None


# --- success path: hidden_unavailable_count ---------------------------------------


def test_hidden_unavailable_count_is_zero_without_the_warning(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=STDERR_NO_WARNING)
    )

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert result["hidden_unavailable_count"] == 0
    assert isinstance(result["hidden_unavailable_count"], int)


def test_hidden_unavailable_count_is_zero_for_empty_stderr(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert result["hidden_unavailable_count"] == 0


def test_warning_and_complete_listing_coexist(mod, monkeypatch):
    """The count is reported AND no member is dropped — the count is not a count of
    missing entries, so it must not be used to infer any are missing."""
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=STDERR_WITH_WARNING)
    )

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert result["hidden_unavailable_count"] == 5
    assert len(result["entries"]) == len(MIXED_ENTRIES)
    assert [e["id"] for e in result["entries"]] == [
        "okVideo0001",
        "privVideo02",
        "okVideo0003",
        "delVideo04x",
    ]
