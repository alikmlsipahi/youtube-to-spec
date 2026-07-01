"""T-S2-06 — require_api_key (env key loading).
Spec: docs/specs/A5-T-S2-06-env_key_loading.spec.md

Pure resolver over a passed env mapping; offline, no os.environ, no .env file.
"""

import copy

import pytest


def test_returns_present_key(mod):
    assert mod.require_api_key({"OPENAI_API_KEY": "sk-present-123"}) == "sk-present-123"


def test_missing_key_raises_and_names_var(mod):
    with pytest.raises(Exception) as excinfo:
        mod.require_api_key({})
    assert "OPENAI_API_KEY" in str(excinfo.value)


def test_empty_string_treated_as_missing(mod):
    with pytest.raises(Exception):
        mod.require_api_key({"OPENAI_API_KEY": ""})


def test_whitespace_only_treated_as_missing(mod):
    with pytest.raises(Exception):
        mod.require_api_key({"OPENAI_API_KEY": "   "})


def test_surrounding_whitespace_trimmed(mod):
    assert mod.require_api_key({"OPENAI_API_KEY": "  sk-trim-me  "}) == "sk-trim-me"


def test_no_secret_leak_on_missing(mod):
    other_secret = "ZZZ-other-secret-value-987"
    env = {"SOME_OTHER_TOKEN": other_secret, "OPENAI_MODEL": "gpt-4o-mini"}
    with pytest.raises(Exception) as excinfo:
        mod.require_api_key(env)
    assert other_secret not in str(excinfo.value)


def test_does_not_mutate_env(mod):
    env = {"OPENAI_API_KEY": "sk-present-123", "OPENAI_MODEL": "gpt-4o-mini"}
    before = copy.deepcopy(env)
    mod.require_api_key(env)
    assert env == before
