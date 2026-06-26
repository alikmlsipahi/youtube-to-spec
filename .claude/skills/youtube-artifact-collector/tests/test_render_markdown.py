"""T-S1-08 — render_markdown.
Spec: docs/specs/A3-T-S1-08-render_markdown.spec.md

Structural assertions only (field presence + transcript-line shape + timestamp
formatting); exact Markdown layout/whitespace is intentionally not pinned, to keep
the blind barrier robust.
"""

from conftest import load_fixture

_CASES = {c["name"]: c["artifact"] for c in load_fixture("inputs", "render_markdown.json")["cases"]}


def _transcript_lines(text):
    """Lines that look like a transcript segment line: `[<ts>] <text>`."""
    return [ln for ln in text.splitlines() if ln.lstrip().startswith("[")]


def test_header_contains_title_url_channel_and_collection(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    assert artifact["video"]["title"] in out
    assert artifact["video"]["url"] in out
    assert artifact["video"]["channel"] in out
    assert artifact["collection"]["title"] in out


def test_title_is_top_level_heading(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    assert f"# {artifact['video']['title']}" in out


def test_first_transcript_line_starts_at_zero(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    lines = _transcript_lines(out)
    assert lines, "expected at least one transcript line"
    assert lines[0].lstrip().startswith("[00:00]")
    assert artifact["transcript"]["segments"][0]["text"] in lines[0]


def test_minute_second_format_under_one_hour(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    # segment starting at 75.0s -> [01:15]
    assert any(ln.lstrip().startswith("[01:15]") for ln in _transcript_lines(out))


def test_hour_format_at_and_over_one_hour(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    lines = _transcript_lines(out)
    # 3600.0s -> [01:00:00] ; 3665.0s -> [01:01:05]
    assert any(ln.lstrip().startswith("[01:00:00]") for ln in lines)
    assert any(ln.lstrip().startswith("[01:01:05]") for ln in lines)


def test_one_transcript_line_per_segment(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    assert len(_transcript_lines(out)) == len(artifact["transcript"]["segments"])


def test_segment_text_is_preserved_verbatim(mod):
    artifact = _CASES["full_collection_available_transcript"]
    out = mod.render_markdown(artifact)
    for seg in artifact["transcript"]["segments"]:
        assert seg["text"] in out


def test_null_collection_does_not_raise_and_renders_header(mod):
    artifact = _CASES["true_single_null_collection"]
    out = mod.render_markdown(artifact)
    assert artifact["video"]["title"] in out
    assert artifact["video"]["url"] in out
    assert artifact["video"]["channel"] in out
    # first line still anchored at zero
    assert _transcript_lines(out)[0].lstrip().startswith("[00:00]")


def test_unavailable_transcript_has_no_timestamp_lines(mod):
    artifact = _CASES["no_transcript_available"]
    out = mod.render_markdown(artifact)
    # header still present
    assert artifact["video"]["title"] in out
    # no segment timestamp lines emitted
    assert _transcript_lines(out) == []


def test_returns_string(mod):
    for artifact in _CASES.values():
        assert isinstance(mod.render_markdown(artifact), str)
