"""T-S2-08 — write_outputs.
Spec: docs/specs/A7-T-S2-08-write_outputs.spec.md

Disk I/O and stdout I/O but no network I/O, so every case runs against ``tmp_path``
with a real Skill 1 artifact written into it. The load-bearing property is the naming
rule: ``<basename>`` mirrors the *source artifact's filename stem* and is never rebuilt
from ``video.id`` (or anything inside ``doc``), so the probes below hand in a stem and
a video id that bear no relation to each other.

Deliberately out of scope per the spec's NEEDS CLARIFICATION list: what a bare
``--out-dir NAME`` is relative to (only absolute dirs are passed here), whether a
non-existent ``out_dir`` is created or errors, the overwrite policy for pre-existing
outputs, exactly what print mode emits (asserted only as "the document reached
stdout"), the return value, JSON indent / non-ASCII escaping, and a source stem that
already ends in ``.requirements``.
"""

import json
import socket

import pytest

VIDEO_ID = "zzTopSecret"
SLUG = "01-tek-tek-ogrenci-yukleme"
MARKER = "Ogrenci yukleme akisinin ozeti"


def _artifact(video_id=VIDEO_ID, title="Tek Tek Öğrenci Yükleme"):
    """A canonical Skill 1 artifact. This unit reads its *path*, not its contents."""
    return {
        "schema_version": "2.1",
        "kind": "video_artifact",
        "video": {
            "id": video_id,
            "title": title,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        },
        "collection": None,
        "transcript": {"segments": []},
    }


def _write_artifact(directory, basename, video_id=VIDEO_ID):
    """Write ``<basename>.json`` holding a canonical artifact for ``video_id``."""
    path = directory / f"{basename}.json"
    path.write_text(json.dumps(_artifact(video_id)), encoding="utf-8")
    return path


def _doc(video_id=VIDEO_ID, summary=MARKER):
    """A finished requirement document, canonical shape."""
    return {
        "summary": summary,
        "modules": [
            {
                "name": "Öğrenci",
                "features": [
                    {
                        "name": "Yükleme",
                        "requirements": [
                            {
                                "id": "OGR-YUK-001",
                                "text": "Kullanıcı tek tek öğrenci ekleyebilmeli.",
                                "source_video_id": video_id,
                                "trace": {"timestamp": "00:01:12", "segment_index": 4},
                            }
                        ],
                    }
                ],
            }
        ],
        "assumptions": ["Okul kaydı önceden açılmıştır."],
        "open_questions": ["Toplu yükleme sınırı nedir?"],
    }


def _markdown(summary=MARKER):
    """Already-rendered document text; this unit renders nothing itself."""
    return f"# Gereksinimler\n\n{summary}\n\n## Öğrenci\n\n- OGR-YUK-001\n"


def _snapshot(directory):
    return sorted(p.name for p in directory.iterdir())


# --- The naming rule: mirror the stem, never rebuild from the id --------------


def test_basename_mirrors_source_stem_not_the_video_id(mod, tmp_path):
    """The decisive scenario: the stem and the video id bear no relation."""
    artifact = _write_artifact(tmp_path, SLUG, VIDEO_ID)

    mod.write_outputs(artifact, _doc(VIDEO_ID), _markdown(), None, False)

    assert (tmp_path / f"{SLUG}.requirements.json").exists()
    assert (tmp_path / f"{SLUG}.requirements.md").exists()


def test_video_id_appears_in_no_output_filename(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG, VIDEO_ID)

    mod.write_outputs(artifact, _doc(VIDEO_ID), _markdown(), None, False)

    assert all(VIDEO_ID not in name for name in _snapshot(tmp_path))


def test_doc_contradicting_the_filename_does_not_perturb_the_names(mod, tmp_path):
    """`doc` has no vote in naming: its ids may contradict the source stem."""
    artifact = _write_artifact(tmp_path, SLUG, VIDEO_ID)
    doc = _doc("CONTRADICTORY")
    doc["modules"][0]["name"] = "Bambaska Modul"

    mod.write_outputs(artifact, doc, _markdown(), None, False)

    assert _snapshot(tmp_path) == sorted(
        [f"{SLUG}.json", f"{SLUG}.requirements.json", f"{SLUG}.requirements.md"]
    )


def test_position_prefix_and_title_slug_survive_verbatim(mod, tmp_path):
    """Skill 1 owns naming policy; Skill 2 copies rather than recomputes."""
    artifact = _write_artifact(tmp_path, "07-kayit-modulu-nasil-kullanilir", "vidAAAAAAA1")

    mod.write_outputs(artifact, _doc("vidAAAAAAA1"), _markdown(), None, False)

    assert (tmp_path / "07-kayit-modulu-nasil-kullanilir.requirements.json").exists()
    assert (tmp_path / "07-kayit-modulu-nasil-kullanilir.requirements.md").exists()


def test_json_and_md_share_one_basename(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    written = [p.name for p in tmp_path.iterdir() if p.name.startswith(f"{SLUG}.requirements")]
    assert sorted(written) == [f"{SLUG}.requirements.json", f"{SLUG}.requirements.md"]


# --- Where the files land -----------------------------------------------------


def test_save_mode_writes_the_pair_beside_the_source(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert _snapshot(tmp_path) == sorted(
        [f"{SLUG}.json", f"{SLUG}.requirements.json", f"{SLUG}.requirements.md"]
    )


def test_both_files_are_written_no_format_selector(mod, tmp_path):
    """The `.json` mirror is not optional."""
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert (tmp_path / f"{SLUG}.requirements.json").is_file()
    assert (tmp_path / f"{SLUG}.requirements.md").is_file()


def test_two_artifacts_in_one_folder_yield_two_distinct_pairs(mod, tmp_path):
    first = _write_artifact(tmp_path, "01-sube-ekleme", "vidAAAAAAA1")
    second = _write_artifact(tmp_path, "02-personel-ekleme", "vidBBBBBBB2")

    mod.write_outputs(first, _doc("vidAAAAAAA1"), _markdown(), None, False)
    mod.write_outputs(second, _doc("vidBBBBBBB2"), _markdown(), None, False)

    assert _snapshot(tmp_path) == sorted(
        [
            "01-sube-ekleme.json",
            "01-sube-ekleme.requirements.json",
            "01-sube-ekleme.requirements.md",
            "02-personel-ekleme.json",
            "02-personel-ekleme.requirements.json",
            "02-personel-ekleme.requirements.md",
        ]
    )


def test_out_dir_redirects_both_files_keeping_the_basename(mod, tmp_path):
    source_dir = tmp_path / "collection"
    source_dir.mkdir()
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    artifact = _write_artifact(source_dir, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), out_dir, False)

    assert (out_dir / f"{SLUG}.requirements.json").exists()
    assert (out_dir / f"{SLUG}.requirements.md").exists()


def test_out_dir_leaves_nothing_beside_the_source(mod, tmp_path):
    source_dir = tmp_path / "collection"
    source_dir.mkdir()
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    artifact = _write_artifact(source_dir, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), out_dir, False)

    assert _snapshot(source_dir) == [f"{SLUG}.json"]


def test_out_dir_redirects_location_never_the_name(mod, tmp_path):
    source_dir = tmp_path / "collection"
    source_dir.mkdir()
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    artifact = _write_artifact(source_dir, SLUG, VIDEO_ID)

    mod.write_outputs(artifact, _doc(VIDEO_ID), _markdown(), out_dir, False)

    assert _snapshot(out_dir) == sorted(
        [f"{SLUG}.requirements.json", f"{SLUG}.requirements.md"]
    )


# --- Print mode ---------------------------------------------------------------


def test_no_save_writes_nothing_to_disk(mod, tmp_path, capsys):
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, True)

    assert _snapshot(tmp_path) == [f"{SLUG}.json"]


def test_no_save_emits_the_document_on_stdout(mod, tmp_path, capsys):
    """The spec pins *that* the document reaches stdout, not its exact framing."""
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, True)

    out = capsys.readouterr().out
    assert MARKER in out


def test_no_save_wins_over_out_dir(mod, tmp_path, capsys):
    source_dir = tmp_path / "collection"
    source_dir.mkdir()
    out_dir = tmp_path / "elsewhere"
    out_dir.mkdir()
    artifact = _write_artifact(source_dir, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), out_dir, True)

    assert _snapshot(source_dir) == [f"{SLUG}.json"]
    assert _snapshot(out_dir) == []


# --- File contents mirror what was handed in ----------------------------------


def test_md_carries_the_rendered_markdown_handed_in(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)
    markdown = _markdown()

    mod.write_outputs(artifact, _doc(), markdown, None, False)

    assert (tmp_path / f"{SLUG}.requirements.md").read_text(encoding="utf-8") == markdown


def test_json_carries_the_documents_structure(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)
    doc = _doc()

    mod.write_outputs(artifact, doc, _markdown(), None, False)

    written = json.loads((tmp_path / f"{SLUG}.requirements.json").read_text(encoding="utf-8"))
    assert written == doc


def test_json_keeps_the_requirement_trace_and_source_video_id(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    written = json.loads((tmp_path / f"{SLUG}.requirements.json").read_text(encoding="utf-8"))
    requirement = written["modules"][0]["features"][0]["requirements"][0]
    assert requirement["id"] == "OGR-YUK-001"
    assert requirement["source_video_id"] == VIDEO_ID
    assert requirement["trace"] == {"timestamp": "00:01:12", "segment_index": 4}


def test_json_carries_assumptions_and_open_questions(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)
    doc = _doc()

    mod.write_outputs(artifact, doc, _markdown(), None, False)

    written = json.loads((tmp_path / f"{SLUG}.requirements.json").read_text(encoding="utf-8"))
    assert written["assumptions"] == doc["assumptions"]
    assert written["open_questions"] == doc["open_questions"]


def test_outputs_are_utf8_and_mirror_each_other(mod, tmp_path):
    """[ASSUMPTION] Files are written UTF-8; artifact titles are routinely Turkish."""
    artifact = _write_artifact(tmp_path, SLUG)
    doc = _doc()

    mod.write_outputs(artifact, doc, _markdown(), None, False)

    written = json.loads((tmp_path / f"{SLUG}.requirements.json").read_text(encoding="utf-8"))
    md_text = (tmp_path / f"{SLUG}.requirements.md").read_text(encoding="utf-8")
    assert written["summary"] == doc["summary"]
    assert "Öğrenci" in md_text


# --- Edge cases on the source filename ----------------------------------------


def test_only_the_final_extension_is_dropped_from_the_stem(mod, tmp_path):
    """[ASSUMPTION] "Filename without its extension" means the path stem."""
    stem = "01-surum-1.2-ogrenci-yukleme"
    artifact = _write_artifact(tmp_path, stem)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert (tmp_path / f"{stem}.requirements.json").exists()
    assert (tmp_path / f"{stem}.requirements.md").exists()


def test_non_ascii_filename_is_mirrored_as_is(mod, tmp_path):
    """This unit does not slugify a name Skill 1 already decided."""
    stem = "01-öğrenci-yükleme-şubesi"
    artifact = _write_artifact(tmp_path, stem)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert (tmp_path / f"{stem}.requirements.json").exists()
    assert (tmp_path / f"{stem}.requirements.md").exists()


# --- Invariants ---------------------------------------------------------------


def test_source_artifact_is_left_unmodified(mod, tmp_path):
    artifact = _write_artifact(tmp_path, SLUG)
    before = artifact.read_text(encoding="utf-8")

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == before


def test_output_paths_do_not_depend_on_cwd(mod, tmp_path, monkeypatch):
    source_dir = tmp_path / "collection"
    source_dir.mkdir()
    other_cwd = tmp_path / "somewhere-else"
    other_cwd.mkdir()
    artifact = _write_artifact(source_dir, SLUG)

    monkeypatch.chdir(other_cwd)
    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert _snapshot(source_dir) == sorted(
        [f"{SLUG}.json", f"{SLUG}.requirements.json", f"{SLUG}.requirements.md"]
    )
    assert _snapshot(other_cwd) == []


def test_write_makes_no_network_call(mod, tmp_path, monkeypatch):
    """The OpenAI call happened upstream; this step is disk and stdout only."""
    artifact = _write_artifact(tmp_path, SLUG)

    def _no_network(*args, **kwargs):
        raise AssertionError("write_outputs must not open a network socket")

    monkeypatch.setattr(socket, "socket", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)

    mod.write_outputs(artifact, _doc(), _markdown(), None, False)

    assert (tmp_path / f"{SLUG}.requirements.json").exists()
