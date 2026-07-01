"""T-S2-03 — parse_response / render_markdown.
Spec: docs/specs/A5-T-S2-03-parse_response_render.spec.md

Offline/deterministic. The OpenAI response object is emulated with SimpleNamespace
(attribute access response.choices[0].message.content); no network, no SDK.
Structural assertions only — exact Markdown layout is intentionally not pinned, to
keep the blind barrier robust.
"""

import copy
import json
from types import SimpleNamespace

import pytest

from conftest import load_fixture

_FIX = load_fixture("inputs", "parse_response.json")
_DOC = _FIX["valid_doc"]
_ARTIFACT = _FIX["artifact"]


def _response(content):
    """Build an OpenAI-style chat-completion response whose assistant message
    carries ``content`` (a JSON string, or None for a refusal)."""
    msg = SimpleNamespace(role="assistant", content=content, refusal=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(choices=[choice])


def _all_requirements(doc):
    for module in doc.get("modules", []):
        for feature in module.get("features", []):
            for req in feature.get("requirements", []):
                yield req


# --- parse_response --------------------------------------------------------


def test_parse_valid_round_trips(mod):
    resp = _response(json.dumps(_DOC))
    assert mod.parse_response(resp) == _DOC


def test_parse_returns_dict_with_modules(mod):
    resp = _response(json.dumps(_DOC))
    out = mod.parse_response(resp)
    assert isinstance(out, dict)
    assert isinstance(out["modules"], list)
    assert out["modules"]


def test_parse_empty_choices_raises(mod):
    resp = SimpleNamespace(choices=[])
    with pytest.raises(Exception):
        mod.parse_response(resp)


def test_parse_none_content_refusal_raises(mod):
    resp = _response(None)
    with pytest.raises(Exception):
        mod.parse_response(resp)


def test_parse_malformed_json_raises(mod):
    resp = _response(_FIX["malformed_content"])
    with pytest.raises(Exception):
        mod.parse_response(resp)


@pytest.mark.parametrize("bad", _FIX["invalid_json_variants"])
def test_parse_invalid_content_variants_raise(mod, bad):
    resp = _response(bad)
    with pytest.raises(Exception):
        mod.parse_response(resp)


def test_parse_does_not_mutate_response(mod):
    resp = _response(json.dumps(_DOC))
    mod.parse_response(resp)
    assert resp.choices[0].message.content == json.dumps(_DOC)


# --- render_markdown -------------------------------------------------------


def test_render_returns_string(mod):
    assert isinstance(mod.render_markdown(_DOC, _ARTIFACT), str)


def test_render_source_header_from_artifact(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    assert _ARTIFACT["video"]["title"] in out
    assert _ARTIFACT["video"]["url"] in out
    assert _ARTIFACT["video"]["channel"] in out
    assert _ARTIFACT["collection"]["title"] in out


def test_render_all_requirement_ids_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for req in _all_requirements(_DOC):
        assert req["id"] in out


def test_render_all_requirement_texts_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for req in _all_requirements(_DOC):
        assert req["text"] in out


def test_render_traces_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for req in _all_requirements(_DOC):
        assert req["trace"]["timestamp"] in out
        assert str(req["trace"]["segment_index"]) in out


def test_render_summary_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    assert _DOC["summary"] in out


def test_render_module_and_feature_codes_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for module in _DOC["modules"]:
        assert module["code"] in out
        for feature in module["features"]:
            assert feature["code"] in out


def test_render_assumptions_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for assumption in _DOC["assumptions"]:
        assert assumption in out


def test_render_open_questions_present(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    for question in _DOC["open_questions"]:
        assert question in out


def test_render_fallback_to_doc_source_when_no_artifact(mod):
    doc = copy.deepcopy(_DOC)
    doc["source"] = _FIX["doc_source_block"]
    out = mod.render_markdown(doc, None)
    assert isinstance(out, str)
    assert _FIX["doc_source_block"]["video_title"] in out
    assert _FIX["doc_source_block"]["channel"] in out


def test_render_does_not_mutate_inputs(mod):
    doc_before = copy.deepcopy(_DOC)
    art_before = copy.deepcopy(_ARTIFACT)
    mod.render_markdown(_DOC, _ARTIFACT)
    assert _DOC == doc_before
    assert _ARTIFACT == art_before


def test_render_no_literal_none_for_present_doc(mod):
    out = mod.render_markdown(_DOC, _ARTIFACT)
    assert "None" not in out
