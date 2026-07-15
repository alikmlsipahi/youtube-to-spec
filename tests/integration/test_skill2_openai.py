"""Opt-in integration: Skill 2 OpenAI engine round-trip.

Mirrors gate I-03. Runs only with RUN_INTEGRATION=1 and a real OPENAI_API_KEY
(see conftest). Uses a tiny self-contained artifact — no YouTube dependency — so
it exercises the real API + parse + the segment_index guard + render without
relying on upstream video state.
"""

import importlib.util
import json
import os

import pytest

from conftest import SKILL2_SCRIPT


def _load_skill2():
    spec = importlib.util.spec_from_file_location("extract_requirements", SKILL2_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # real openai/dotenv (installed for this tier)
    return module


TINY_ARTIFACT = {
    "schema_version": "1.0",
    "video": {
        "id": "itest0001",
        "title": "Registration Module — Add a Single Student",
        "url": "https://www.youtube.com/watch?v=itest0001",
        "channel": "demo",
        "description": "A short walkthrough of adding one student.",
    },
    "collection": None,
    "transcript": {
        "available": True,
        "segments": [
            {"index": 0, "start": 0.0, "duration": 3.0, "end": 3.0,
             "text": "Open the registration module and click the students tab."},
            {"index": 1, "start": 3.0, "duration": 3.0, "end": 6.0,
             "text": "Click the new student button at the top right."},
            {"index": 2, "start": 6.0, "duration": 4.0, "end": 10.0,
             "text": "Fields marked with a star are required; fill them in."},
            {"index": 3, "start": 10.0, "duration": 3.0, "end": 13.0,
             "text": "Click save to complete the registration."},
        ],
    },
}


@pytest.mark.integration
def test_skill2_openai_roundtrip(openai_key, tmp_path):
    from openai import OpenAI

    mod = _load_skill2()
    artifact_path = tmp_path / "itest0001.json"
    artifact_path.write_text(json.dumps(TINY_ARTIFACT), encoding="utf-8")

    env = dict(os.environ)
    env["OPENAI_API_KEY"] = openai_key
    config = mod.resolve_config({"engine": "openai"}, env)
    system_prompt, template = mod.load_prompt_files()
    client = OpenAI(api_key=openai_key)

    artifact, doc, markdown = mod.process_artifact(
        artifact_path, config, system_prompt, template, client
    )

    # same shape as the Claude-native contract
    assert {"summary", "modules", "assumptions", "open_questions"} <= set(doc)
    requirements = [
        r
        for m in doc.get("modules", [])
        for f in m.get("features", [])
        for r in f.get("requirements", [])
    ]
    assert requirements, "expected at least one requirement"

    valid_indexes = {s["index"] for s in TINY_ARTIFACT["transcript"]["segments"]}
    for req in requirements:
        assert mod.validate_req_id(req.get("id", ""), artifact["video"]["id"])
        seg_index = (req.get("trace") or {}).get("segment_index")
        # the guard guarantees a resolved index (or an intentional null)
        assert seg_index is None or seg_index in valid_indexes

    assert markdown.startswith("# ")
