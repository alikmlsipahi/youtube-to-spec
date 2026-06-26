# Spec — `resolve_config` (config resolution, CLI > env > default) (T-S2-01)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 "OpenAI (built fully now)" — configurable model / temperature / max_tokens /
> response_format(json_schema) / timeout / retry / concurrency, **precedence CLI > env > default**;
> §CLI (OpenAI engine); catalog row T-S2-01; `02_PRODUCT_BRIEF.md` §LLM Entegrasyonu — these params
> must be **configurable and external, not hardcoded**). **No test code, no golden output tables here.**

## One-line purpose

Resolve the OpenAI engine's seven runtime parameters from the three configuration sources, applying the
fixed precedence **command-line argument > environment variable > built-in default**, and return a single
fully-populated, correctly-typed config object.

## Signature

```python
def resolve_config(cli: dict, env: dict) -> dict
```

Pure and deterministic; no I/O, no network, no reading of `os.environ` inside the function (the caller
passes `env`). This is the single place that encodes parameter precedence, so changing it is a one-edit
change.

## Inputs

- `cli: dict` — the parsed command-line options, keyed by **canonical parameter name**
  (`model, temperature, max_tokens, response_format, timeout, retries, concurrency`). A value of `None`
  means "the flag was not supplied on the command line" and must **not** override anything. Supplied
  values may already be correctly typed (argparse `type=`) or may be strings; the function coerces
  regardless.
- `env: dict` — a mapping of **environment-variable name → string value** (e.g. a snapshot of
  `os.environ`). Only the recognized names below participate; all others are ignored. Environment values
  are always strings and are coerced to the canonical type.

### Canonical parameters, env-var names, types, and defaults

| canonical key (in `cli` / result) | env-var name | type | default |
|---|---|---|---|
| `model` | `OPENAI_MODEL` | `str` | `"gpt-4o-mini"` |
| `temperature` | `OPENAI_TEMPERATURE` | `float` | `0.2` |
| `max_tokens` | `OPENAI_MAX_TOKENS` | `int` | `4096` |
| `response_format` | `OPENAI_RESPONSE_FORMAT` | `str` | `"json_schema"` |
| `timeout` | `OPENAI_TIMEOUT` | `int` (seconds) | `60` |
| `retries` | `OPENAI_RETRIES` | `int` | `3` |
| `concurrency` | `OPENAI_CONCURRENCY` | `int` | `4` |

## Expected behavior

For each of the seven parameters, independently:

1. **If `cli[key]` is present and not `None`** → use it.
2. **Else if the parameter's env-var name is present in `env`** (and its value is a non-empty string) →
   use the env value.
3. **Else** → use the built-in default from the table.

Then **coerce** the chosen raw value to the parameter's canonical type (so an env string `"0.7"` for
`temperature` becomes the float `0.7`, `"2048"` for `max_tokens` becomes the int `2048`, etc.). `model`
and `response_format` are kept as strings.

Return a `dict` whose keys are exactly the seven canonical names, each mapped to its resolved,
correctly-typed value. The result never contains `None` for any of the seven keys (every parameter always
resolves, falling through to its default in the worst case).

Precedence is per-parameter: it is normal for one parameter to come from the CLI, another from the
environment, and a third from the default, all in the same call.

## Edge cases

- **CLI value present, env also present** → CLI wins (env ignored for that parameter).
- **CLI value `None`, env present** → env value used and coerced from its string form.
- **Neither CLI nor env present** → default used.
- **Env value is an empty string** → treated as "not provided"; falls through to the default.
- **Env value supplies the wrong textual form for a numeric param** (e.g. non-numeric) → out of tested
  scope; see NEEDS CLARIFICATION.
- **`cli` missing a key entirely** (key absent vs. present-but-`None`) → both are treated as "not
  supplied" for that parameter.
- **Extra/unrelated keys** in `env` (other environment variables) → ignored.
- A numeric value supplied through the CLI as a string (e.g. `"0.5"`) is coerced the same way an env
  value would be, so the function is robust regardless of whether argparse pre-typed it.

## Acceptance scenarios (Given / When / Then)

- **Given** a `cli` that supplies all seven parameters, **when** `resolve_config` runs, **then** the
  result equals those CLI values (coerced to canonical types), regardless of `env`.
- **Given** an empty `cli` (all `None`) and an `env` that supplies all seven env vars, **when** resolved,
  **then** each result value equals the env value coerced to its canonical type.
- **Given** an empty `cli` and an empty `env`, **when** resolved, **then** the result equals the default
  table exactly.
- **Given** a parameter present in **both** `cli` and `env`, **when** resolved, **then** the CLI value is
  chosen and the env value is ignored.
- **Given** a mix (some CLI, some env, some neither), **when** resolved, **then** each parameter follows
  its own source per the precedence rule.
- **Given** an env-only `temperature` of `"0.7"`, **when** resolved, **then** the result holds the float
  `0.7` (not the string `"0.7"`).

## Assumptions

- [ASSUMPTION] The default **values** in the table (`gpt-4o-mini`, `0.2`, `4096`, `json_schema`, `60`,
  `3`, `4`) are not specified by the plan beyond "configurable"; sensible extraction-task defaults are
  chosen here and are the contract the implementer must reproduce. `response_format` defaults to
  `json_schema` because the plan mandates structured json_schema output.
- [ASSUMPTION] The **env-var names** (`OPENAI_MODEL`, `OPENAI_TEMPERATURE`, …) are not named by the plan
  (only `OPENAI_API_KEY` is); the `OPENAI_*` convention is adopted here.
- [ASSUMPTION] Signature is `resolve_config(cli, env)` taking already-collected dicts (not reading the
  process environment itself), keeping the unit pure and testable offline.
- [ASSUMPTION] `timeout` is an integer number of seconds; the plan's `--timeout S` does not pin int vs.
  float.
- [ASSUMPTION] An empty-string env value counts as "absent".

## Key entities (canonical schema excerpt)

The resolved config feeds the OpenAI call described in the plan: `model`, `temperature`, `max_tokens`,
`response_format` (`json_schema` for structured output), `timeout`, `retries`, and `concurrency`
(batch/parallelism). `OPENAI_API_KEY` itself is **not** part of this object — secret loading is a
separate unit (T-S2-06).

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Behavior when an env var holds a non-coercible value for a numeric parameter
  (e.g. `OPENAI_MAX_TOKENS=abc`): raise a clear config error vs. fall back to default. This spec leaves
  it out of tested scope; recommended behavior is a clear error at the acceptance gate.
- [NEEDS CLARIFICATION] Whether `response_format` should be validated against the allowed set
  (`json_schema` | `text`) inside `resolve_config` or downstream at call-build time. Assumed downstream.
- [NEEDS CLARIFICATION] Exact default values are provisional and meant for human confirmation at the
  acceptance gate; changing them changes only this table and the matching fixture.
