# Spec — `require_api_key` (env key loading) (T-S2-06)

> Behavioral contract for the blind implementer. Source of truth: `docs/IMPLEMENTATION_PLAN_v2.md`
> (§Skill 2 — OpenAI engine "key from `.env` loaded from the current working directory, then process
> env"; §Locked decisions — "Secrets via `.env` + `.env.example`"; catalog row T-S2-06 "missing
> `OPENAI_API_KEY` → clear error, no crash, no secret leak"; §Acceptance — "secrets only via `.env`");
> `02_PRODUCT_BRIEF.md` §LLM Entegrasyonu — "API key gibi gizli bilgileri **koda gömmemek**; bunları …
> env variable, `.env` dosyası vb. ele almak"). **No test code, no golden output tables here.**

## One-line purpose

Resolve the OpenAI API key from a supplied environment mapping, returning it when present and raising a
**clear, secret-safe** error when it is missing or blank — so the OpenAI engine fails fast with a helpful
message instead of crashing deep inside the SDK or leaking secrets.

## Signature

```python
def require_api_key(env: dict) -> str
```

Pure and deterministic: reads only the passed `env` mapping (no `os.environ`, no `.env` file I/O, no
network). The script's real entry point is responsible for building `env` (e.g. `load_dotenv()` from the
current working directory **then** overlaying `os.environ`); this unit only validates and extracts.
Keeping it pure makes the missing-key behavior testable offline.

## Inputs

- `env: dict` — a string→string mapping of resolved environment variables (the merge of `.env` and the
  process environment). The key of interest is `OPENAI_API_KEY`.

## Expected behavior

1. When `env["OPENAI_API_KEY"]` is present and **non-blank**, return it **unchanged** (no trimming that
   alters a valid key beyond stripping surrounding whitespace, no logging, no printing).
2. When `OPENAI_API_KEY` is **absent**, or present but an **empty string** or **whitespace-only**, raise a
   **clear** error (e.g. `RuntimeError`) whose message:
   - names the missing variable **`OPENAI_API_KEY`**, and
   - points the user at the remediation (set it in `.env` / the environment), and
   - **never** embeds any secret value — not the key, not any other value from `env`.
3. Does not crash with a bare `KeyError`/`TypeError`; the failure is the intentional, descriptive error
   above. Does not mutate `env`. Does not call the network or read files.

## Edge cases

- **`OPENAI_API_KEY` absent entirely** → clear error.
- **`OPENAI_API_KEY` is `""`** → treated as missing → clear error.
- **`OPENAI_API_KEY` is whitespace-only (`"   "`)** → treated as missing → clear error.
- **`OPENAI_API_KEY` present and valid, surrounded by stray whitespace** → returned (whitespace-trimmed);
  a real key is never rejected.
- **Other secret-looking variables present in `env` (e.g. a different token)** → never echoed in the
  error message on the missing-key path (no-leak guarantee).
- **`env` is an empty dict** → clear error (same as absent).

## Acceptance scenarios (Given / When / Then)

- **Given** an `env` containing a non-blank `OPENAI_API_KEY`, **when** `require_api_key` runs, **then** it
  returns that key value.
- **Given** an `env` with no `OPENAI_API_KEY`, **when** `require_api_key` runs, **then** it raises a clear
  error whose message mentions `OPENAI_API_KEY`.
- **Given** an `env` whose `OPENAI_API_KEY` is an empty string, **when** `require_api_key` runs, **then**
  it raises (empty is treated as missing).
- **Given** an `env` whose `OPENAI_API_KEY` is whitespace-only, **when** `require_api_key` runs, **then**
  it raises.
- **Given** an `env` that lacks `OPENAI_API_KEY` but contains other secret-looking values, **when**
  `require_api_key` raises, **then** the error message contains none of those other values.
- **Given** any input, **when** `require_api_key` runs, **then** `env` is not mutated and no network/file
  access occurs.

## Assumptions

- [ASSUMPTION] The variable name is exactly **`OPENAI_API_KEY`** (matches `.env.example` authored in Phase
  C2 and the §Skill 2 description).
- [ASSUMPTION] The unit is the **pure resolver** over a passed mapping; the actual `.env`-from-cwd +
  process-env merge (`load_dotenv` / `os.environ`) lives in the script's entry point and is exercised at
  the integration tier, not here. This mirrors the existing pure `resolve_config(cli, env)` design.
- [ASSUMPTION] Empty and whitespace-only values count as **missing** (a blank key would otherwise produce
  an opaque 401 deep inside the SDK).
- [ASSUMPTION] The raised type is a plain `Exception` subclass with a descriptive message (e.g.
  `RuntimeError`); the script's top-level `except Exception → stderr → sys.exit(1)` convention turns it
  into a clean non-zero exit. The exact subclass is not load-bearing.

## Key entities

```jsonc
// env mapping (illustrative)
{ "OPENAI_API_KEY": "sk-…", "OPENAI_MODEL": "gpt-4o-mini", … }
```

Only `OPENAI_API_KEY` is consulted by this unit. (Other `OPENAI_*` keys are consumed by
`resolve_config`, T-S2-01 — out of scope here.)

## NEEDS CLARIFICATION

- [NEEDS CLARIFICATION] Whether a real key should be returned **verbatim** or **stripped** of surrounding
  whitespace. This spec chooses "stripped" (defensive against trailing newlines from `.env`); confirm no
  real key relies on leading/trailing whitespace.
- [NEEDS CLARIFICATION] Whether the engine should additionally support an alternate variable name or a
  `--api-key` CLI flag. Out of scope for this unit (env-only); revisit if the CLI grows one.
