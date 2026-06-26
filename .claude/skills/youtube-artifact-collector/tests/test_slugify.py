"""T-S1-04 — slugify / collection_dir_name.
Spec: docs/specs/A1-T-S1-04-slugify_collection_dir_name.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "slugify.json")["cases"]
_EXPECTED = load_fixture("expected", "slugify.json")

_SLUG_CASES = [
    (case["title"], slug) for case, slug in zip(_CASES, _EXPECTED["slugs"])
]
_DIR_CASES = [
    (case["title"], case["playlist_id"], dir_name)
    for case, dir_name in zip(_CASES, _EXPECTED["dir_names"])
]


@pytest.mark.parametrize("title, expected_slug", _SLUG_CASES)
def test_slugify(mod, title, expected_slug):
    assert mod.slugify(title) == expected_slug


@pytest.mark.parametrize("title, playlist_id, expected_dir", _DIR_CASES)
def test_collection_dir_name(mod, title, playlist_id, expected_dir):
    assert mod.collection_dir_name(title, playlist_id) == expected_dir
