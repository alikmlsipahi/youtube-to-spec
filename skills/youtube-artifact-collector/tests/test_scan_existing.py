"""T-S1-14 — scan_existing.
Spec: docs/specs/A6-T-S1-14-scan_existing.spec.md

Disk I/O but no network I/O, so every case runs against ``tmp_path`` with real
artifact JSON written into it. Ids are recovered from each artifact's canonical
``video.id``, never parsed out of the filename. Deliberately out of scope per the
spec's NEEDS CLARIFICATION list: duplicate video ids in one directory, whether an
entry requires both `.json` and `.md`, and unexpected non-artifact files.
"""

import json
import socket

import pytest


def _artifact(video_id, title="Örnek Başlık"):
    """A canonical per-video artifact, trimmed to what this unit reads."""
    return {
        "schema_version": "2.1",
        "video": {
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        },
        "collection": None,
        "transcript": {"segments": []},
    }


def _write_artifact(directory, basename, video_id, title="Örnek Başlık"):
    """Write ``<basename>.json`` holding the canonical artifact for ``video_id``."""
    path = directory / f"{basename}.json"
    path.write_text(json.dumps(_artifact(video_id, title)), encoding="utf-8")
    return path


def _snapshot(directory):
    return sorted(p.name for p in directory.iterdir())


# --- Empty / missing directories ---------------------------------------------

def test_missing_directory_returns_empty_mapping(mod, tmp_path):
    """[ASSUMPTION] --skip-existing must be safe on a first-ever run."""
    missing = tmp_path / "never-created"
    assert mod.scan_existing(missing) == {}


def test_missing_directory_does_not_raise_or_create_it(mod, tmp_path):
    missing = tmp_path / "never-created"
    mod.scan_existing(missing)
    assert not missing.exists()


def test_empty_directory_returns_empty_mapping(mod, tmp_path):
    assert mod.scan_existing(tmp_path) == {}


# --- Indexing artifacts -------------------------------------------------------

def test_single_artifact_is_indexed_by_its_video_id(mod, tmp_path):
    _write_artifact(tmp_path, "what-is-claude-code", "fl1DSmwQKKY")
    assert mod.scan_existing(tmp_path) == {"fl1DSmwQKKY": "what-is-claude-code"}


def test_several_artifacts_yield_one_entry_each(mod, tmp_path):
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    _write_artifact(tmp_path, "02-personel-ekleme", "vidBBBBBBB2")
    _write_artifact(tmp_path, "03-rapor-alma", "vidCCCCCCC3")
    result = mod.scan_existing(tmp_path)
    assert result == {
        "vidAAAAAAA1": "01-sube-ekleme",
        "vidBBBBBBB2": "02-personel-ekleme",
        "vidCCCCCCC3": "03-rapor-alma",
    }


def test_basenames_are_read_off_disk_not_reconstructed_from_the_id(mod, tmp_path):
    """[v2.1] names are title-derived, so they cannot be predicted from an id."""
    _write_artifact(tmp_path, "07-kayit-modulu-nasil-kullanilir", "zzTopSecret")
    result = mod.scan_existing(tmp_path)
    assert result == {"zzTopSecret": "07-kayit-modulu-nasil-kullanilir"}


def test_basename_carries_no_directory_and_no_extension(mod, tmp_path):
    _write_artifact(tmp_path, "05-sube-ekleme", "vidAAAAAAA1")
    basename = mod.scan_existing(tmp_path)["vidAAAAAAA1"]
    assert basename == "05-sube-ekleme"
    assert not basename.endswith(".json")
    assert "/" not in basename


def test_id_comes_from_artifact_contents_not_the_filename(mod, tmp_path):
    """The filename says one thing; `video.id` is authoritative."""
    _write_artifact(tmp_path, "01-misleading-name", "trueVideoId")
    assert mod.scan_existing(tmp_path) == {"trueVideoId": "01-misleading-name"}


# --- The .md companion --------------------------------------------------------

def test_md_companion_contributes_no_separate_entry(mod, tmp_path):
    """[ASSUMPTION] A video appears exactly once, keyed by its id."""
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    (tmp_path / "01-sube-ekleme.md").write_text("# Şube Ekleme\n", encoding="utf-8")
    result = mod.scan_existing(tmp_path)
    assert result == {"vidAAAAAAA1": "01-sube-ekleme"}
    assert len(result) == 1


# --- Exclusions ---------------------------------------------------------------

def test_manifest_only_directory_returns_empty_mapping(mod, tmp_path):
    manifest = {
        "collection": {"id": "PLabcdEFGH123", "title": "Kayıt Modülü"},
        "members": [{"video_id": "vidAAAAAAA1", "files": {"json": "01-x.json", "md": "01-x.md"}}],
        "summary": {"total": 1},
    }
    (tmp_path / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {}


def test_manifest_contributes_no_entry_alongside_artifacts(mod, tmp_path):
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    manifest = {
        "collection": {"id": "PLabcdEFGH123", "title": "Kayıt Modülü"},
        "members": [
            {
                "video_id": "vidAAAAAAA1",
                "files": {"json": "01-sube-ekleme.json", "md": "01-sube-ekleme.md"},
            }
        ],
        "summary": {"total": 1},
    }
    (tmp_path / "_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = mod.scan_existing(tmp_path)
    assert result == {"vidAAAAAAA1": "01-sube-ekleme"}
    assert "_manifest" not in result.values()


def test_skill2_requirement_docs_are_excluded(mod, tmp_path):
    _write_artifact(tmp_path, "01-kurulum", "vidAAAAAAA1")
    (tmp_path / "01-kurulum.md").write_text("# Kurulum\n", encoding="utf-8")
    # Probe: the requirement doc is given artifact-shaped content carrying its own
    # id. Exclusion is by filename, so this id must never reach the index.
    (tmp_path / "01-kurulum.requirements.json").write_text(
        json.dumps({"video": {"id": "REQPROBE001"}, "modules": []}), encoding="utf-8"
    )
    (tmp_path / "01-kurulum.requirements.md").write_text("# Requirements\n", encoding="utf-8")
    result = mod.scan_existing(tmp_path)
    assert result == {"vidAAAAAAA1": "01-kurulum"}


def test_requirement_doc_basename_never_appears_as_a_value(mod, tmp_path):
    _write_artifact(tmp_path, "02-raporlama", "vidBBBBBBB2")
    (tmp_path / "02-raporlama.requirements.json").write_text(
        json.dumps({"video": {"id": "vidBBBBBBB2"}, "modules": []}), encoding="utf-8"
    )
    result = mod.scan_existing(tmp_path)
    assert all(not v.endswith(".requirements") for v in result.values())
    assert result == {"vidBBBBBBB2": "02-raporlama"}


# --- Unreadable / malformed files degrade to "no entry" -----------------------

def test_malformed_json_is_ignored_without_raising(mod, tmp_path):
    (tmp_path / "01-broken.json").write_text("{ this is not valid json", encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {}


def test_malformed_file_does_not_prevent_other_artifacts_being_indexed(mod, tmp_path):
    _write_artifact(tmp_path, "01-good", "vidAAAAAAA1")
    (tmp_path / "02-broken.json").write_text("{ truncated", encoding="utf-8")
    _write_artifact(tmp_path, "03-also-good", "vidCCCCCCC3")
    result = mod.scan_existing(tmp_path)
    assert result == {"vidAAAAAAA1": "01-good", "vidCCCCCCC3": "03-also-good"}


def test_truncated_artifact_is_ignored(mod, tmp_path):
    full = json.dumps(_artifact("vidAAAAAAA1"))
    (tmp_path / "01-truncated.json").write_text(full[: len(full) // 2], encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {}


def test_valid_json_of_unexpected_shape_is_ignored(mod, tmp_path):
    (tmp_path / "01-odd.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {}


def test_artifact_missing_video_id_is_ignored(mod, tmp_path):
    (tmp_path / "01-noid.json").write_text(
        json.dumps({"schema_version": "2.1", "video": {"title": "No id here"}}), encoding="utf-8"
    )
    assert mod.scan_existing(tmp_path) == {}


def test_artifact_with_no_video_block_is_ignored(mod, tmp_path):
    (tmp_path / "01-novideo.json").write_text(
        json.dumps({"schema_version": "2.1", "transcript": {"segments": []}}), encoding="utf-8"
    )
    assert mod.scan_existing(tmp_path) == {}


def test_empty_json_file_is_ignored(mod, tmp_path):
    (tmp_path / "01-empty.json").write_text("", encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {}


def test_unrecoverable_id_does_not_block_the_rest(mod, tmp_path):
    _write_artifact(tmp_path, "01-good", "vidAAAAAAA1")
    (tmp_path / "02-noid.json").write_text(json.dumps({"video": {}}), encoding="utf-8")
    assert mod.scan_existing(tmp_path) == {"vidAAAAAAA1": "01-good"}


# --- Read-only, network-free --------------------------------------------------

def test_directory_contents_are_left_unmodified(mod, tmp_path):
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    (tmp_path / "01-sube-ekleme.md").write_text("# Şube Ekleme\n", encoding="utf-8")
    (tmp_path / "_manifest.json").write_text(json.dumps({"members": []}), encoding="utf-8")
    before = _snapshot(tmp_path)
    payload_before = (tmp_path / "01-sube-ekleme.json").read_text(encoding="utf-8")

    mod.scan_existing(tmp_path)

    assert _snapshot(tmp_path) == before
    assert (tmp_path / "01-sube-ekleme.json").read_text(encoding="utf-8") == payload_before


def test_scan_makes_no_network_call(mod, tmp_path, monkeypatch):
    """--skip-existing's defining property: a skipped video costs disk reads only."""
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")

    def _no_network(*args, **kwargs):
        raise AssertionError("scan_existing must not open a network socket")

    monkeypatch.setattr(socket, "socket", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)

    assert mod.scan_existing(tmp_path) == {"vidAAAAAAA1": "01-sube-ekleme"}


def test_returns_a_mapping(mod, tmp_path):
    _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    result = mod.scan_existing(tmp_path)
    assert isinstance(result, dict)
