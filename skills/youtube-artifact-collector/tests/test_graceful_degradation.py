"""T-S1-11 — graceful degradation: fetch_metadata returns (meta, failure_kind).
Spec: docs/specs/A3-T-S1-11-graceful_degradation.spec.md

Re-signed in v2.3: the return type is now ``tuple[dict | None, str | None]``.
Exactly one half is ever non-``None`` — a success is ``(dict, None)``, a failure
is ``(None, "transient" | "permanent" | "unknown")``. The old bare-``None``
contract made "this video is private" and "YouTube rate-limited us" the same
value, which is why the pair of opposite-classification tests below is the
centre of this file.

v2.5 adds a third verdict, ``"unknown"``, for failures nothing recognizes. This
unit's *shape* is untouched by that: it delegates, so it passes the third verdict
through for free. Only the value returned for an unrecognized failure moves —
from ``"permanent"`` to ``"unknown"``.

Scope: this unit **delegates** classification to ``classify_failure`` (T-S1-16).
It is tested here only for capturing the right evidence and passing the verdict
through, using one realistic representative stderr per verdict. Which strings map
to which verdict — the signal lists, casing, the "Sign in to confirm" prefix
trap, name-vs-text precedence — is T-S1-16's contract and lives in
``test_classify_failure.py``.

Offline: the yt-dlp subprocess is mocked via the stdlib ``subprocess.run`` so no
network/tool is touched. Patching the shared stdlib module object covers the
``import subprocess; subprocess.run(...)`` call convention.
"""

import json
import subprocess
from types import SimpleNamespace

# The two opposite-classification scenarios must differ *only* in stderr, so they
# share this one return code deliberately.
_SAME_NONZERO_CODE = 1

# One realistic representative per verdict. Real stderr is multi-line and
# prefixed, and the signal lives inside a longer line — the evidence this unit
# must capture whole rather than discard.
_PERMANENT_STDERR = (
    "WARNING: [youtube] Falling back to generic n function search\n"
    "ERROR: [youtube] dQw4w9WgXcQ: Private video. Sign in if you've been "
    "granted access to this video\n"
)
_TRANSIENT_STDERR = (
    "WARNING: [youtube] Falling back to generic n function search\n"
    "ERROR: [youtube] dQw4w9WgXcQ: Unable to download webpage: HTTP Error 429: "
    "Too Many Requests\n"
)
# Real stderr in shape, carrying nothing any signal list claims — the drift case
# stands in for a reworded upstream message nobody has seen yet.
_UNRECOGNIZED_STDERR = (
    "WARNING: [youtube] Falling back to generic n function search\n"
    "ERROR: [youtube] dQw4w9WgXcQ: Unable to extract player response; please "
    "report this issue on the yt-dlp issue tracker\n"
)


def _fake_run(returncode, stdout="", stderr="", record=None):
    def _run(*args, **kwargs):
        if record is not None:
            record.append(kwargs)
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    return _run


def _raising_run(exc):
    def _run(*args, **kwargs):
        raise exc
    return _run


# --- Success -----------------------------------------------------------------

def test_zero_exit_with_valid_json_returns_dict_paired_with_no_failure(mod, monkeypatch):
    meta = {"id": "fl1DSmwQKKY", "title": "What is Claude Code?", "duration": 612}
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=json.dumps(meta)))
    result = mod.fetch_metadata("fl1DSmwQKKY")
    assert isinstance(result, tuple)
    assert result == (meta, None)
    assert isinstance(result[0], dict)


# --- The re-sign's reason: one return code, two opposite verdicts, on stderr alone

def test_same_nonzero_code_with_private_video_stderr_is_permanent(mod, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", _fake_run(_SAME_NONZERO_CODE, stderr=_PERMANENT_STDERR)
    )
    assert mod.fetch_metadata("someVideoId") == (None, "permanent")


def test_same_nonzero_code_with_rate_limit_stderr_is_transient(mod, monkeypatch):
    # Identical return code to the test above; only the captured stderr differs,
    # and it alone flips the verdict. Under the old bare-None contract these two
    # outcomes were the same value — this pair is what the re-sign exists for.
    monkeypatch.setattr(
        subprocess, "run", _fake_run(_SAME_NONZERO_CODE, stderr=_TRANSIENT_STDERR)
    )
    assert mod.fetch_metadata("someVideoId") == (None, "transient")


# --- Other failure modes ------------------------------------------------------

def test_nonzero_exit_with_empty_stderr_is_unknown(mod, monkeypatch):
    # Nothing was offered to recognize, so nothing was recognized.
    monkeypatch.setattr(subprocess, "run", _fake_run(2, stdout="", stderr=""))
    assert mod.fetch_metadata("anotherId00") == (None, "unknown")


def test_nonzero_exit_with_unrecognized_stderr_is_unknown_not_permanent(mod, monkeypatch):
    # The drift case, and the scenario the v2.5 revision exists for: a reworded
    # message matches no signal and must land in "unknown" rather than being
    # relabelled "permanent" — the same return code as the two tests above,
    # separated from both by stderr alone.
    monkeypatch.setattr(
        subprocess, "run", _fake_run(_SAME_NONZERO_CODE, stderr=_UNRECOGNIZED_STDERR)
    )
    assert mod.fetch_metadata("someVideoId") == (None, "unknown")


def test_zero_exit_with_unparseable_stdout_is_permanent(mod, monkeypatch):
    # A clean exit that emits garbage is not a throttle; re-running it is not
    # expected to produce different bytes.
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout="<html>not json at all</html>")
    )
    assert mod.fetch_metadata("fl1DSmwQKKY") == (None, "permanent")


def test_zero_exit_with_empty_stdout_is_permanent_like_unparseable_stdout(mod, monkeypatch):
    # Empty stdout is not a separate case from garbage stdout — a clean exit that
    # emits nothing parseable is one case, and it is permanent either way.
    monkeypatch.setattr(subprocess, "run", _fake_run(0, stdout=""))
    assert mod.fetch_metadata("fl1DSmwQKKY") == (None, "permanent")


def test_missing_ytdlp_executable_is_unknown_and_does_not_raise(mod, monkeypatch):
    # A missing tool produces text nothing recognizes, so it is "unknown" — and
    # usefully so. It is not retried either way (installing it is not something a
    # retry achieves); what the verdict buys is that the caller now prints the
    # text it did not recognize instead of throwing the message away.
    monkeypatch.setattr(
        subprocess,
        "run",
        _raising_run(FileNotFoundError(2, "No such file or directory: 'yt-dlp'")),
    )
    assert mod.fetch_metadata("someVideoId") == (None, "unknown")


def test_expired_timeout_is_transient_and_does_not_raise(mod, monkeypatch):
    # The raised error's class name and text are the evidence handed to the
    # classifier; a stalled call is worth another attempt.
    expired = subprocess.TimeoutExpired(
        cmd=["yt-dlp", "--skip-download", "--dump-json", "someVideoId"], timeout=120.0
    )
    monkeypatch.setattr(subprocess, "run", _raising_run(expired))
    assert mod.fetch_metadata("someVideoId", timeout=120.0) == (None, "transient")


def test_never_raises_on_any_failure_path(mod, monkeypatch):
    # Failure is always signalled by the return value — never by an exception and
    # never by sys.exit (a SystemExit would escape this call and fail here too).
    failing_runs = [
        _fake_run(_SAME_NONZERO_CODE, stderr=_PERMANENT_STDERR),
        _fake_run(_SAME_NONZERO_CODE, stderr=_TRANSIENT_STDERR),
        _fake_run(_SAME_NONZERO_CODE, stderr=_UNRECOGNIZED_STDERR),
        _fake_run(2, stderr=""),
        _fake_run(0, stdout="}{ garbage"),
        _raising_run(FileNotFoundError(2, "No such file or directory: 'yt-dlp'")),
        _raising_run(OSError("[Errno 12] Cannot allocate memory")),
        _raising_run(subprocess.TimeoutExpired(cmd=["yt-dlp"], timeout=1.0)),
    ]
    for run in failing_runs:
        monkeypatch.setattr(subprocess, "run", run)
        meta, failure = mod.fetch_metadata("someVideoId")
        assert meta is None
        assert failure in ("transient", "permanent", "unknown")


# --- Isolation ----------------------------------------------------------------

def test_failure_is_isolated_across_videos(mod, monkeypatch):
    """First video fails, second succeeds — the batch can continue."""
    meta_ok = {"id": "okvideoid000", "title": "Fine"}
    calls = {"n": 0}

    def _run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr=_PERMANENT_STDERR)
        return SimpleNamespace(returncode=0, stdout=json.dumps(meta_ok), stderr="")

    monkeypatch.setattr(subprocess, "run", _run)
    first = mod.fetch_metadata("badvideoid00")
    second = mod.fetch_metadata("okvideoid000")
    assert first == (None, "permanent")
    assert second == (meta_ok, None)


# --- The additive timeout parameter -------------------------------------------

def test_default_call_imposes_no_time_limit(mod, monkeypatch):
    # timeout is keyword-only and defaults to None, so an existing positional
    # call site keeps its old unbounded behavior.
    seen = []
    meta = {"id": "fl1DSmwQKKY", "title": "Fine"}
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(meta), record=seen)
    )
    mod.fetch_metadata("fl1DSmwQKKY")
    assert seen[0].get("timeout") is None


def test_timeout_bounds_the_subprocess_call(mod, monkeypatch):
    seen = []
    meta = {"id": "fl1DSmwQKKY", "title": "Fine"}
    monkeypatch.setattr(
        subprocess, "run", _fake_run(0, stdout=json.dumps(meta), record=seen)
    )
    mod.fetch_metadata("fl1DSmwQKKY", timeout=30.0)
    assert seen[0].get("timeout") == 30.0
