"""T-S1-15 — enumerate_playlist.
Spec: docs/specs/A6-T-S1-15-enumerate_playlist.spec.md (v2.5)

Offline: the ``yt-dlp --flat-playlist --dump-single-json`` subprocess is mocked via the
stdlib ``subprocess.run`` so no network is touched. Behavior is pinned on the mocked
return code / stdout / stderr only — never on the exact yt-dlp argument vector, which the
spec leaves to the implementer (§Assumptions).

v2.3: the unit returns ``(playlist, failure)`` — a 2-tuple in which exactly one half is
ever non-``None``. The order-preservation, null-title and hidden-unavailable rules are
unchanged by the re-sign.

v2.4: stdout that *parses* as JSON but is not an object is a failure like any other —
``(None, "permanent")``, never an exception. See the section banner below for why this is
pinned separately from unparseable stdout.

v2.5: ``failure`` is now ``None`` / ``"transient"`` / ``"permanent"`` / ``"unknown"``. The
shape is untouched — the third verdict arrives here purely because classification is
delegated, and ``classify_failure`` (T-S1-16) gained it. Only the *value* for an
unrecognized failure moves: it used to be reported as ``"permanent"``, which claimed a
conclusion nothing had established. What this unit must pass through unchanged is pinned
below; what "unrecognized" *means* is T-S1-16's business, not this file's.

Classification is *delegated* to ``classify_failure`` (T-S1-16), so this file uses one
realistic representative stderr per verdict and does not enumerate signal lists, casing, or
the "Sign in to confirm" prefix trap — those belong to T-S1-16's own tier. Likewise the
hidden-unavailable parse rules belong to ``parse_hidden_unavailable`` (T-S1-10) and are not
re-pinned here. Retry itself lives in the orchestration loop: this unit is a single
subprocess call that reports a verdict.

Deliberately untested (spec §NEEDS CLARIFICATION): empty playlist, missing playlist-level
keys, an entry lacking an id, and a non-playlist URL.
"""

import json
import subprocess
from types import SimpleNamespace

import pytest

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp"

# The single non-zero return code used by BOTH classification tests below: the verdict is
# decided on stderr alone, never on the code.
FAILING_RC = 1

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

# One realistic representative stderr per verdict. Which fragments map to which verdict is
# T-S1-16's contract, not this unit's — these are only "evidence captured and passed on".
STDERR_PRIVATE_PLAYLIST = (
    "[youtube:tab] Extracting URL: https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp\n"
    "[youtube:tab] PLf2m1LSmwQKKY0examp: Downloading webpage\n"
    "ERROR: [youtube:tab] PLf2m1LSmwQKKY0examp: This playlist is private. "
    "Sign in if you've been granted access to this playlist\n"
)

STDERR_RATE_LIMITED = (
    "[youtube:tab] Extracting URL: https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp\n"
    "ERROR: [youtube:tab] PLf2m1LSmwQKKY0examp: Unable to download API page: "
    "HTTP Error 429: Too Many Requests (caused by <HTTPError 429: Too Many Requests>)\n"
)

# Stderr that describes a real-looking failure in wording nothing has been taught to
# recognize — a stand-in for the day YouTube or yt-dlp rewords a message we match on.
# Deliberately carries no fragment from either signal list.
STDERR_UNRECOGNIZED = (
    "[youtube:tab] Extracting URL: https://www.youtube.com/playlist?list=PLf2m1LSmwQKKY0examp\n"
    "[youtube:tab] PLf2m1LSmwQKKY0examp: Downloading webpage\n"
    "ERROR: [youtube:tab] PLf2m1LSmwQKKY0examp: The feed could not be assembled "
    "(reason code 8171). Please report this issue on the yt-dlp tracker\n"
)


def _fake_run(returncode, stdout="", stderr=""):
    def _run(*args, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return _run


def _recording_run(returncode, stdout="", stderr=""):
    """Like ``_fake_run``, but keeps the kwargs it was called with on ``.calls``."""
    calls = []

    def _run(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    _run.calls = calls
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


# --- failure paths: the same return code, classified on stderr alone ----------------
#
# One non-zero exit, four stderr texts, three verdicts. The code carries no information;
# every distinction below comes from what stderr offered the classifier to recognize.


def test_nonzero_exit_with_private_playlist_stderr_is_permanent(mod, monkeypatch):
    """A playlist that will never come back: no retry could help."""
    monkeypatch.setattr(
        subprocess, "run", _fake_run(FAILING_RC, stdout="", stderr=STDERR_PRIVATE_PLAYLIST)
    )
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "permanent")


def test_same_nonzero_exit_with_rate_limit_stderr_is_transient_not_permanent(mod, monkeypatch):
    """Same FAILING_RC as the private-playlist test above, opposite verdict.

    The return code carries no information here — the classification comes from stderr
    alone. This is the distinction the v2.3 re-sign exists to make: a bare None could not
    tell the caller that this playlist is worth another attempt.
    """
    monkeypatch.setattr(
        subprocess, "run", _fake_run(FAILING_RC, stdout="", stderr=STDERR_RATE_LIMITED)
    )
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "transient")


@pytest.mark.parametrize("returncode", [1, 2])
def test_nonzero_exit_with_empty_stderr_is_unknown(mod, monkeypatch, returncode):
    """Nothing was offered to recognize, so nothing was recognized — for any non-zero code."""
    monkeypatch.setattr(subprocess, "run", _fake_run(returncode, stdout="", stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "unknown")


def test_nonzero_exit_with_unrecognized_stderr_is_unknown_not_permanent(mod, monkeypatch):
    """The drift case, and the reason the third verdict exists.

    Same FAILING_RC as the private-playlist test above, and stderr that looks every bit as
    much like a hard failure — but in wording nothing matches. The verdict is "unknown", not
    "permanent": this call gates the entire run, and a failure nobody has characterized must
    not be passed on as one we understand.
    """
    monkeypatch.setattr(
        subprocess, "run", _fake_run(FAILING_RC, stdout="", stderr=STDERR_UNRECOGNIZED)
    )
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "unknown")


# --- failure paths: a clean exit that produced nothing usable ----------------------
#
# These never reach the classifier: the process said it succeeded, so there is no failure
# text to classify. The spec decides them directly — a clean exit emitting garbage is not a
# throttle — which is why "unknown" is not the answer here and these stay "permanent".


def test_unparseable_stdout_is_permanent(mod, monkeypatch):
    """Return code 0 but garbage on stdout must not propagate a parse exception."""
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="not json at all {", stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "permanent")


def test_empty_stdout_is_permanent(mod, monkeypatch):
    """A clean exit emitting nothing is not a throttle."""
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout="", stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "permanent")


# --- failure paths: a clean exit whose stdout PARSES but is not a playlist document ---
#
# Distinct from the unparseable case above, and the distinction is the whole point: there,
# json.loads raises and the parse guard catches it. Here json.loads *succeeds* — so a guard
# asking "did it parse" waves the value through, and the next read of it is what blows up.
# A playlist document is a mapping; a list / null / bare scalar cannot be read as one, so
# the guard has to ask "is this a dict".

NON_OBJECT_STDOUTS = [
    pytest.param("[1,2,3]", id="json-array"),
    pytest.param("null", id="json-null"),
    pytest.param('"a bare string"', id="bare-string"),
    pytest.param("42", id="bare-number"),
]


@pytest.mark.parametrize("stdout", NON_OBJECT_STDOUTS)
def test_parseable_but_non_object_stdout_is_permanent(mod, monkeypatch, stdout):
    """Parsing succeeding is not the same as the document being usable."""
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=stdout, stderr=""))
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "permanent")


@pytest.mark.parametrize("stdout", NON_OBJECT_STDOUTS)
def test_parseable_but_non_object_stdout_never_raises(mod, monkeypatch, stdout):
    """The "never raises" half of the contract, asserted on its own.

    A test that only compared the return value would still pass if the function raised some
    *other* way, and raising is exactly what this path historically did — so failure has to
    be signalled by the return value here, as on every other failure path.
    """
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=stdout, stderr=""))

    try:
        mod.enumerate_playlist(PLAYLIST_URL)
    except Exception as exc:  # noqa: BLE001 — any escaping exception breaks the contract
        pytest.fail(f"enumerate_playlist raised {type(exc).__name__} instead of returning: {exc}")


# --- failure paths: the subprocess itself raised, and nothing escapes ---------------


def test_missing_yt_dlp_executable_is_unknown(mod, monkeypatch):
    """yt-dlp not installed → graceful verdict, not an exception.

    No per-exception special-casing: the exception's name and text are handed to the
    classifier like any other evidence, and nothing recognizes them, so the verdict is
    "unknown". Retry behavior is unaffected — no retry installs a missing executable, and
    "unknown" is not retried either.
    """

    def _run(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory: 'yt-dlp'")

    monkeypatch.setattr(subprocess, "run", _run)
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "unknown")


def test_timed_out_call_is_transient(mod, monkeypatch):
    """An expired timeout is worth another attempt — and must not surface as an exception."""

    def _run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["yt-dlp", "--flat-playlist", "--dump-single-json", PLAYLIST_URL],
            timeout=120.0,
        )

    monkeypatch.setattr(subprocess, "run", _run)
    assert mod.enumerate_playlist(PLAYLIST_URL, timeout=120.0) == (None, "transient")


def test_other_subprocess_error_is_unknown(mod, monkeypatch):
    """Any other subprocess error degrades to a verdict as well, never to an exception.

    Its name and text match nothing either, so it lands where every uncharacterized failure
    now lands.
    """

    def _run(*args, **kwargs):
        raise subprocess.SubprocessError("subprocess blew up")

    monkeypatch.setattr(subprocess, "run", _run)
    assert mod.enumerate_playlist(PLAYLIST_URL) == (None, "unknown")


# --- the timeout parameter is additive ---------------------------------------------


def test_omitting_timeout_imposes_no_time_limit(mod, monkeypatch):
    """Default is None — the pre-v2.3 unbounded behavior stays reachable."""
    run = _recording_run(0, stdout=json.dumps(_playlist_doc(ORDERED_ENTRIES)), stderr="")
    monkeypatch.setattr(subprocess, "run", run)

    mod.enumerate_playlist(PLAYLIST_URL)

    assert run.calls[0].get("timeout") is None


def test_timeout_bounds_the_subprocess_call(mod, monkeypatch):
    run = _recording_run(0, stdout=json.dumps(_playlist_doc(ORDERED_ENTRIES)), stderr="")
    monkeypatch.setattr(subprocess, "run", run)

    mod.enumerate_playlist(PLAYLIST_URL, timeout=5.0)

    assert run.calls[0].get("timeout") == 5.0


def test_timeout_is_keyword_only(mod, monkeypatch):
    """An existing positional call site keeps compiling; timeout cannot be passed by position."""
    run = _recording_run(0, stdout=json.dumps(_playlist_doc(ORDERED_ENTRIES)), stderr="")
    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(TypeError):
        mod.enumerate_playlist(PLAYLIST_URL, 5.0)


# --- success path: playlist identity, paired with no failure ------------------------


def test_success_returns_a_two_tuple_with_no_failure(mod, monkeypatch):
    """Exactly one half is ever non-None."""
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    result = mod.enumerate_playlist(PLAYLIST_URL)

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], dict)
    assert result[1] is None


def test_success_returns_playlist_identity(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert failure is None
    assert playlist["id"] == "PLf2m1LSmwQKKY0examp"
    assert playlist["title"] == "Claude Code Deep Dive"
    assert playlist["uploader"] == "Anthropic"


def test_returned_dict_has_exactly_the_contract_keys(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert set(playlist) == {"id", "title", "uploader", "entries", "hidden_unavailable_count"}


def test_entry_records_carry_the_thin_flat_listing_fields(mod, monkeypatch):
    """Each entries record is {id, title} — the thin fields the flat listing supplies."""
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    for record in playlist["entries"]:
        assert set(record) == {"id", "title"}


# --- success path: order is the contract ------------------------------------------


def test_entries_preserve_playlist_order(mod, monkeypatch):
    """One record per member, in the same order the document listed them."""
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert [e["id"] for e in playlist["entries"]] == [
        "zAbC1234567",
        "mNoP7654321",
        "aXyZ0011223",
    ]
    assert [e["title"] for e in playlist["entries"]] == [
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

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert [e["id"] for e in playlist["entries"]] == [
        "repeatVid01",
        "otherVid002",
        "repeatVid01",
    ]


# --- success path: unavailable members are enumerated, not omitted -----------------


def test_null_title_members_stay_in_entries_at_their_positions(mod, monkeypatch):
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert len(playlist["entries"]) == 4
    assert [e["id"] for e in playlist["entries"]] == [
        "okVideo0001",
        "privVideo02",
        "okVideo0003",
        "delVideo04x",
    ]


def test_null_title_is_preserved_not_repaired(mod, monkeypatch):
    """Passed through exactly as yt-dlp reported it — no coercion to '' or to the id."""
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert playlist["entries"][1]["title"] is None
    assert playlist["entries"][3]["title"] is None


# --- success path: hidden_unavailable_count ---------------------------------------


def test_hidden_unavailable_count_is_zero_without_the_warning(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=STDERR_NO_WARNING)
    )

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert playlist["hidden_unavailable_count"] == 0
    assert isinstance(playlist["hidden_unavailable_count"], int)


def test_hidden_unavailable_count_is_zero_for_empty_stderr(mod, monkeypatch):
    doc = _playlist_doc(ORDERED_ENTRIES)
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=""))

    playlist, _failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert playlist["hidden_unavailable_count"] == 0


def test_warning_and_complete_listing_coexist(mod, monkeypatch):
    """The count is reported AND no member is dropped — the count is not a count of
    missing entries, so it must not be used to infer any are missing."""
    doc = _playlist_doc(MIXED_ENTRIES)
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(doc), stderr=STDERR_WITH_WARNING)
    )

    playlist, failure = mod.enumerate_playlist(PLAYLIST_URL)

    assert failure is None
    assert playlist["hidden_unavailable_count"] == 5
    assert len(playlist["entries"]) == len(MIXED_ENTRIES)
    assert [e["id"] for e in playlist["entries"]] == [
        "okVideo0001",
        "privVideo02",
        "okVideo0003",
        "delVideo04x",
    ]
