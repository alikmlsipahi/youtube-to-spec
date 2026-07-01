"""Post-parse hardening: ``normalize_trace_indexes`` must guarantee every
requirement's ``trace.segment_index`` addresses a real transcript segment,
remapping an LLM's start-second value only when unambiguous and otherwise
failing loudly. Offline/deterministic — no network, no OpenAI.
"""

import pytest


def _artifact(segments):
    return {"video": {"id": "vid123"}, "transcript": {"segments": segments}}


def _doc(segment_index):
    """A minimal doc with a single requirement carrying the given trace index."""
    return {
        "modules": [
            {
                "code": "REG",
                "features": [
                    {
                        "code": "ADD",
                        "requirements": [
                            {
                                "id": "REG-ADD-001",
                                "text": "x",
                                "source_video_id": "vid123",
                                "trace": {"timestamp": "00:10", "segment_index": segment_index},
                            }
                        ],
                    }
                ],
            }
        ],
    }


# Segments: index 0@0.5s, 1@10.2s, 2@20.9s, plus 3@30.1s & 4@30.7s (same whole second)
SEGMENTS = [
    {"index": 0, "start": 0.5},
    {"index": 1, "start": 10.2},
    {"index": 2, "start": 20.9},
    {"index": 3, "start": 30.1},
    {"index": 4, "start": 30.7},
]


def test_valid_index_is_kept(mod):
    doc = _doc(2)
    mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))
    assert _first_trace(doc)["segment_index"] == 2


def test_start_second_unambiguously_remapped(mod):
    # 10 is not a valid index; exactly one segment starts in second 10 (index 1)
    doc = _doc(10)
    mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))
    assert _first_trace(doc)["segment_index"] == 1


def test_ambiguous_start_second_raises(mod):
    # 30 matches two segments (indexes 3 and 4) -> ambiguous
    doc = _doc(30)
    with pytest.raises(ValueError):
        mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))


def test_unresolvable_value_raises(mod):
    doc = _doc(999)
    with pytest.raises(ValueError):
        mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))


def test_none_segment_index_is_left_untouched(mod):
    doc = _doc(None)
    mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))
    assert _first_trace(doc)["segment_index"] is None


def test_non_integer_index_raises(mod):
    doc = _doc("5")
    with pytest.raises(ValueError):
        mod.normalize_trace_indexes(doc, _artifact(SEGMENTS))


def test_empty_transcript_disables_validation(mod):
    # No segments to resolve against -> leave the (otherwise invalid) index as-is
    doc = _doc(104)
    mod.normalize_trace_indexes(doc, _artifact([]))
    assert _first_trace(doc)["segment_index"] == 104


def test_returns_same_doc_object(mod):
    doc = _doc(1)
    assert mod.normalize_trace_indexes(doc, _artifact(SEGMENTS)) is doc


def _first_trace(doc):
    return doc["modules"][0]["features"][0]["requirements"][0]["trace"]
