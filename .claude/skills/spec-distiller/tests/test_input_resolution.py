"""T-S2-07 — resolve_inputs / load_artifact (input resolution).
Spec: docs/specs/A5-T-S2-07-input_resolution.spec.md

Filesystem-backed (read-only); no network. Uses an on-disk collection fixture
(tests/fixtures/inputs/collection_sample/) plus tmp_path for negative/edge cases.
"""

import json
from pathlib import Path

import pytest

from conftest import FIXTURES_DIR

COLLECTION = FIXTURES_DIR / "inputs" / "collection_sample"


def _names(paths):
    return [Path(p).name for p in paths]


# --- resolve_inputs: collection directory ----------------------------------


def test_directory_returns_ok_members_in_order(mod):
    result = mod.resolve_inputs(COLLECTION)
    assert _names(result) == ["VIDAAAAAAAA.json", "VIDBBBBBBBB.json"]


def test_failed_and_skipped_members_excluded(mod):
    names = _names(mod.resolve_inputs(COLLECTION))
    assert "VIDFAILED00.json" not in names
    assert "VIDSKIP0000.json" not in names


def test_ok_member_without_files_skipped(mod):
    names = _names(mod.resolve_inputs(COLLECTION))
    assert "VIDNOFILE00.json" not in names


def test_resolved_paths_point_into_collection_dir(mod):
    for p in mod.resolve_inputs(COLLECTION):
        assert Path(p).parent == COLLECTION


# --- resolve_inputs: single artifact file ----------------------------------


def test_single_artifact_file_returns_itself(mod):
    target = COLLECTION / "VIDAAAAAAAA.json"
    result = mod.resolve_inputs(target)
    assert _names(result) == ["VIDAAAAAAAA.json"]


# --- resolve_inputs: error / edge cases ------------------------------------


def test_nonexistent_path_raises(mod, tmp_path):
    with pytest.raises(Exception):
        mod.resolve_inputs(tmp_path / "does_not_exist")


def test_directory_without_manifest_raises(mod, tmp_path):
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    with pytest.raises(Exception):
        mod.resolve_inputs(empty)


def test_empty_members_returns_empty_list(mod, tmp_path):
    coll = tmp_path / "coll"
    coll.mkdir()
    (coll / "_manifest.json").write_text(
        json.dumps({"collection": {}, "members": [], "summary": {}}),
        encoding="utf-8",
    )
    assert mod.resolve_inputs(coll) == []


# --- load_artifact ---------------------------------------------------------


def test_load_artifact_returns_dict(mod):
    art = mod.load_artifact(COLLECTION / "VIDAAAAAAAA.json")
    assert isinstance(art, dict)
    assert art["video"]["id"] == "VIDAAAAAAAA"


def test_load_artifact_missing_schema_version_ok(mod, tmp_path):
    path = tmp_path / "no_version.json"
    path.write_text(
        json.dumps({"kind": "video_artifact", "video": {"id": "X"}}),
        encoding="utf-8",
    )
    art = mod.load_artifact(path)
    assert isinstance(art, dict)
    assert art["video"]["id"] == "X"


def test_load_artifact_unknown_schema_version_ok(mod, tmp_path):
    path = tmp_path / "weird_version.json"
    path.write_text(
        json.dumps({"schema_version": "9.9", "video": {"id": "Y"}}),
        encoding="utf-8",
    )
    art = mod.load_artifact(path)
    assert isinstance(art, dict)
    assert art["video"]["id"] == "Y"


def test_load_artifact_corrupt_file_raises(mod, tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises(Exception):
        mod.load_artifact(path)
