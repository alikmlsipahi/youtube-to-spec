"""T-S2-01 — config resolution (precedence CLI > env > default).
Spec: docs/specs/A4-T-S2-01-config_resolution.spec.md
"""

import pytest

from conftest import load_fixture

_CASES = load_fixture("inputs", "config_resolution.json")["cases"]
_EXPECTED = load_fixture("expected", "config_resolution.json")["resolved"]

_PARAMS = [
    pytest.param(case["cli"], case["env"], resolved, id=case["name"])
    for case, resolved in zip(_CASES, _EXPECTED)
]

_BY_NAME = {c["name"]: c for c in _CASES}
_EXPECTED_BY_NAME = {c["name"]: r for c, r in zip(_CASES, _EXPECTED)}

_KEYS = {
    "model",
    "temperature",
    "max_tokens",
    "response_format",
    "timeout",
    "retries",
    "concurrency",
}


@pytest.mark.parametrize("cli, env, expected", _PARAMS)
def test_resolve_config_matches_expected(mod, cli, env, expected):
    assert mod.resolve_config(cli, env) == expected


@pytest.mark.parametrize("cli, env, expected", _PARAMS)
def test_result_has_exactly_the_seven_keys(mod, cli, env, expected):
    assert set(mod.resolve_config(cli, env).keys()) == _KEYS


@pytest.mark.parametrize("cli, env, expected", _PARAMS)
def test_no_value_is_none(mod, cli, env, expected):
    result = mod.resolve_config(cli, env)
    for key in _KEYS:
        assert result[key] is not None


def test_cli_wins_over_env(mod):
    case = _BY_NAME["all_cli_overrides_env"]
    expected = _EXPECTED_BY_NAME["all_cli_overrides_env"]
    assert mod.resolve_config(case["cli"], case["env"]) == expected


def test_env_used_when_cli_absent(mod):
    case = _BY_NAME["all_env"]
    expected = _EXPECTED_BY_NAME["all_env"]
    assert mod.resolve_config(case["cli"], case["env"]) == expected


def test_defaults_when_nothing_supplied(mod):
    case = _BY_NAME["all_default"]
    expected = _EXPECTED_BY_NAME["all_default"]
    assert mod.resolve_config(case["cli"], case["env"]) == expected


def test_empty_cli_dict_uses_defaults(mod):
    # A wholly-absent set of CLI keys behaves the same as present-but-None.
    expected = _EXPECTED_BY_NAME["all_default"]
    assert mod.resolve_config({}, {}) == expected


def test_env_string_values_are_coerced_to_canonical_types(mod):
    case = _BY_NAME["all_env"]
    result = mod.resolve_config(case["cli"], case["env"])
    assert isinstance(result["model"], str)
    assert isinstance(result["temperature"], float)
    assert isinstance(result["max_tokens"], int)
    assert isinstance(result["response_format"], str)
    assert isinstance(result["timeout"], int)
    assert isinstance(result["retries"], int)
    assert isinstance(result["concurrency"], int)
    assert result["temperature"] == 0.7


def test_cli_string_values_are_coerced(mod):
    case = _BY_NAME["cli_string_values_coerced"]
    result = mod.resolve_config(case["cli"], case["env"])
    assert isinstance(result["temperature"], float)
    assert isinstance(result["max_tokens"], int)
    assert result["temperature"] == 0.33
    assert result["max_tokens"] == 512


def test_empty_env_string_falls_through_to_default(mod):
    case = _BY_NAME["empty_env_strings_fall_through_to_default"]
    expected = _EXPECTED_BY_NAME["empty_env_strings_fall_through_to_default"]
    assert mod.resolve_config(case["cli"], case["env"]) == expected


def test_per_parameter_source_mix(mod):
    case = _BY_NAME["cli_env_default_mixed"]
    result = mod.resolve_config(case["cli"], case["env"])
    assert result["model"] == "cli-model"        # from CLI
    assert result["max_tokens"] == 1234           # from CLI
    assert result["temperature"] == 0.5           # from env
    assert result["response_format"] == "text"    # from env
    assert result["concurrency"] == 2             # from env
    assert result["timeout"] == 60                # default
    assert result["retries"] == 3                 # default
