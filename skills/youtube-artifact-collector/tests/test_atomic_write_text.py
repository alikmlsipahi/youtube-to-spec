"""T-S1-19 — atomic_write_text.
Spec: docs/specs/A8-T-S1-19-atomic_write_text.spec.md

Local disk I/O only — every case runs against ``tmp_path`` and never touches the
network. The temp file's naming scheme is explicitly *not* contractual, so the
"no debris" cases assert that the directory holds only what it should rather than
naming any particular temp file.
"""

import os

import pytest


def _seed(path, text):
    """Put pre-existing content at ``path`` the way an earlier run would have."""
    path.write_text(text, encoding="utf-8")
    return path


def _listing(directory):
    """Every name in ``directory`` — the whole surface a later reader could see."""
    return sorted(p.name for p in directory.iterdir())


def _boom(*args, **kwargs):
    """Stand-in that fails the way a full disk would, mid-operation."""
    raise OSError(28, "No space left on device")


# A lone surrogate: a legitimate `str` that cannot be encoded as UTF-8, so the
# write fails partway without any monkeypatching.
UNENCODABLE = "gecerli metin \ud800 bozuk kuyruk"

LONG_TEXT = "eski içerik satırı\n" * 200
SHORT_TEXT = "kısa\n"


# --- Basic write --------------------------------------------------------------

def test_writing_to_a_new_path_creates_it_with_exactly_the_given_text(mod, tmp_path):
    dest = tmp_path / "01-sube-ekleme.json"
    mod.atomic_write_text(dest, '{"schema_version": "2.1"}')
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'


def test_the_written_file_holds_utf8_encoded_bytes(mod, tmp_path):
    """[plan] "write UTF-8 everywhere" — the encoding is fixed, not locale-dependent."""
    dest = tmp_path / "01-sube-ekleme.md"
    text = "# Şube Ekleme\n"
    mod.atomic_write_text(dest, text)
    assert dest.read_bytes() == text.encode("utf-8")


def test_the_write_returns_nothing(mod, tmp_path):
    dest = tmp_path / "_manifest.json"
    assert mod.atomic_write_text(dest, '{"members": []}') is None


# --- Overwrite ----------------------------------------------------------------

def test_existing_file_with_different_content_is_replaced_wholesale(mod, tmp_path):
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.0"}')
    mod.atomic_write_text(dest, '{"schema_version": "2.1"}')
    assert dest.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'


def test_overwriting_long_content_with_much_shorter_text_leaves_no_remnant(mod, tmp_path):
    """The failure mode of truncate-then-write: an old tail surviving the new write."""
    dest = _seed(tmp_path / "01-sube-ekleme.json", LONG_TEXT)
    mod.atomic_write_text(dest, SHORT_TEXT)
    assert dest.read_text(encoding="utf-8") == SHORT_TEXT


def test_a_shorter_overwrite_leaves_a_file_no_longer_than_the_new_text(mod, tmp_path):
    dest = _seed(tmp_path / "01-sube-ekleme.json", LONG_TEXT)
    mod.atomic_write_text(dest, SHORT_TEXT)
    assert dest.stat().st_size == len(SHORT_TEXT.encode("utf-8"))


def test_the_same_path_written_twice_holds_the_second_content_exactly(mod, tmp_path):
    """No interleaving: the second write wins completely."""
    dest = tmp_path / "01-sube-ekleme.md"
    mod.atomic_write_text(dest, "# Birinci Sürüm\n\nuzun uzun eski gövde metni\n")
    mod.atomic_write_text(dest, "# İkinci Sürüm\n")
    assert dest.read_text(encoding="utf-8") == "# İkinci Sürüm\n"


# --- No debris ----------------------------------------------------------------

def test_a_successful_write_leaves_only_the_destination_file_in_the_directory(mod, tmp_path):
    dest = tmp_path / "01-sube-ekleme.json"
    mod.atomic_write_text(dest, '{"schema_version": "2.1"}')
    assert _listing(tmp_path) == ["01-sube-ekleme.json"]


def test_an_overwrite_leaves_only_the_destination_file_in_the_directory(mod, tmp_path):
    dest = _seed(tmp_path / "01-sube-ekleme.json", LONG_TEXT)
    mod.atomic_write_text(dest, SHORT_TEXT)
    assert _listing(tmp_path) == ["01-sube-ekleme.json"]


def test_repeated_writes_to_the_same_path_never_accumulate_extra_files(mod, tmp_path):
    dest = tmp_path / "01-sube-ekleme.json"
    for i in range(5):
        mod.atomic_write_text(dest, f'{{"pass": {i}}}')
        assert _listing(tmp_path) == ["01-sube-ekleme.json"]
    assert dest.read_text(encoding="utf-8") == '{"pass": 4}'


def test_a_json_glob_of_the_directory_sees_only_the_written_artifact(mod, tmp_path):
    """[ASSUMPTION] The directory scan globs `*.json`; nothing of this unit's may match."""
    dest = tmp_path / "01-sube-ekleme.json"
    mod.atomic_write_text(dest, '{"schema_version": "2.1"}')
    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["01-sube-ekleme.json"]


def test_two_different_paths_in_the_same_directory_do_not_interfere(mod, tmp_path):
    json_path = tmp_path / "01-sube-ekleme.json"
    md_path = tmp_path / "01-sube-ekleme.md"
    mod.atomic_write_text(md_path, "# Şube Ekleme\n")
    mod.atomic_write_text(json_path, '{"schema_version": "2.1"}')
    assert md_path.read_text(encoding="utf-8") == "# Şube Ekleme\n"
    assert json_path.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'
    assert _listing(tmp_path) == ["01-sube-ekleme.json", "01-sube-ekleme.md"]


def test_writing_one_file_leaves_pre_existing_siblings_untouched(mod, tmp_path):
    sibling = _seed(tmp_path / "02-personel-ekleme.json", '{"schema_version": "2.1"}')
    mod.atomic_write_text(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    assert sibling.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'
    assert _listing(tmp_path) == ["01-sube-ekleme.json", "02-personel-ekleme.json"]


# --- Encoding -----------------------------------------------------------------

def test_turkish_characters_round_trip_exactly(mod, tmp_path):
    """The artifacts are Turkish transcripts; a mangled encoding is silent corruption."""
    dest = tmp_path / "01-kayit-modulu.md"
    text = "Şube ekleme işlemi çoğu kullanıcı için ığüşöç ĞÜŞİÖÇ gerektirir.\n"
    mod.atomic_write_text(dest, text)
    assert dest.read_text(encoding="utf-8") == text


def test_emoji_round_trip_exactly(mod, tmp_path):
    dest = tmp_path / "01-notlar.md"
    text = "Tamamlandı 🎉 — dikkat ⚠️ ve bitiş 🚀\n"
    mod.atomic_write_text(dest, text)
    assert dest.read_text(encoding="utf-8") == text


def test_cjk_characters_round_trip_exactly(mod, tmp_path):
    dest = tmp_path / "01-cjk.md"
    text = "字幕テスト 中文测试 한국어 시험\n"
    mod.atomic_write_text(dest, text)
    assert dest.read_text(encoding="utf-8") == text


def test_non_ascii_text_is_stored_as_utf8_bytes(mod, tmp_path):
    dest = tmp_path / "01-kayit-modulu.md"
    text = "Şube 🎉 中文\n"
    mod.atomic_write_text(dest, text)
    assert dest.read_bytes() == text.encode("utf-8")


def test_newlines_are_written_verbatim_with_no_translation(mod, tmp_path):
    """No newline translation: what goes in is byte-for-byte what lands."""
    dest = tmp_path / "01-sube-ekleme.md"
    text = "birinci satır\nikinci satır\n\ndördüncü satır"
    mod.atomic_write_text(dest, text)
    assert dest.read_bytes() == text.encode("utf-8")
    assert b"\r\n" not in dest.read_bytes()


# --- Empty text ---------------------------------------------------------------

def test_empty_text_produces_an_existing_zero_length_file(mod, tmp_path):
    """An explicit empty write is legitimate — not the crash-induced empty file."""
    dest = tmp_path / "01-bos.md"
    mod.atomic_write_text(dest, "")
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == ""
    assert dest.stat().st_size == 0


def test_empty_text_write_leaves_only_the_destination_in_the_directory(mod, tmp_path):
    mod.atomic_write_text(tmp_path / "01-bos.md", "")
    assert _listing(tmp_path) == ["01-bos.md"]


def test_empty_text_over_existing_content_truncates_to_zero_length(mod, tmp_path):
    dest = _seed(tmp_path / "01-sube-ekleme.md", LONG_TEXT)
    mod.atomic_write_text(dest, "")
    assert dest.read_bytes() == b""


# --- Failure propagation ------------------------------------------------------

def test_missing_parent_directory_propagates_the_error(mod, tmp_path):
    """[ASSUMPTION] Callers mkdir; this unit does not, and it does not swallow the error."""
    dest = tmp_path / "never-created" / "01-sube-ekleme.json"
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"schema_version": "2.1"}')


def test_missing_parent_directory_is_not_created_as_a_side_effect(mod, tmp_path):
    parent = tmp_path / "never-created"
    with pytest.raises(OSError):
        mod.atomic_write_text(parent / "01-sube-ekleme.json", "x")
    assert not parent.exists()


def test_text_that_cannot_be_encoded_propagates_the_error(mod, tmp_path):
    dest = tmp_path / "01-sube-ekleme.json"
    with pytest.raises(UnicodeEncodeError):
        mod.atomic_write_text(dest, UNENCODABLE)


def test_a_failed_encode_leaves_the_previous_content_intact(mod, tmp_path):
    """[ASSUMPTION] The temp file absorbs every partial state; the destination never sees one."""
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    with pytest.raises(UnicodeEncodeError):
        mod.atomic_write_text(dest, UNENCODABLE)
    assert dest.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'


def test_a_failed_encode_leaves_nothing_extra_in_the_directory(mod, tmp_path):
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    with pytest.raises(UnicodeEncodeError):
        mod.atomic_write_text(dest, UNENCODABLE)
    assert _listing(tmp_path) == ["01-sube-ekleme.json"]


def test_a_failure_at_the_replace_step_propagates(mod, tmp_path, monkeypatch):
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"schema_version": "2.2"}')


def test_a_failure_at_the_replace_step_leaves_the_previous_content_intact(mod, tmp_path, monkeypatch):
    dest = _seed(tmp_path / "_manifest.json", '{"members": ["eski"]}')
    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"members": ["yeni"]}')
    assert dest.read_text(encoding="utf-8") == '{"members": ["eski"]}'


def test_a_failure_at_the_replace_step_leaves_nothing_extra_in_the_directory(mod, tmp_path, monkeypatch):
    """A failed write must not strand anything next to the artifacts."""
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"schema_version": "2.2"}')
    assert _listing(tmp_path) == ["01-sube-ekleme.json"]


def test_a_failure_at_the_replace_step_does_not_create_a_destination_that_did_not_exist(
    mod, tmp_path, monkeypatch
):
    dest = tmp_path / "01-sube-ekleme.json"
    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"schema_version": "2.1"}')
    assert not dest.exists()
    assert _listing(tmp_path) == []


def test_a_failure_while_syncing_the_written_data_propagates_and_leaves_nothing_extra(
    mod, tmp_path, monkeypatch
):
    """The data must reach the disk before the rename, and that step's failure is loud."""
    dest = _seed(tmp_path / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    monkeypatch.setattr(os, "fsync", _boom)
    with pytest.raises(OSError):
        mod.atomic_write_text(dest, '{"schema_version": "2.2"}')
    assert dest.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'
    assert _listing(tmp_path) == ["01-sube-ekleme.json"]


def test_an_unwritable_directory_propagates_the_error_and_leaves_no_debris(mod, tmp_path):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores directory write permissions")
    out_dir = tmp_path / "kayit-modulu"
    out_dir.mkdir()
    dest = _seed(out_dir / "01-sube-ekleme.json", '{"schema_version": "2.1"}')
    out_dir.chmod(0o500)
    try:
        with pytest.raises(OSError):
            mod.atomic_write_text(dest, '{"schema_version": "2.2"}')
        assert dest.read_text(encoding="utf-8") == '{"schema_version": "2.1"}'
        assert _listing(out_dir) == ["01-sube-ekleme.json"]
    finally:
        out_dir.chmod(0o700)
