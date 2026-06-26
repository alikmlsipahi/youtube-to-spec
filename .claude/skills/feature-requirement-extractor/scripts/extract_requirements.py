#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["openai>=1.0.0", "python-dotenv>=1.0.0"]
# ///
"""
OpenAI engine for Skill 2 (feature-requirement-extractor): Skill 1 video
artifact JSON -> Module->Feature->Requirement document.

Phase 1 — pure helpers (T-S2-01, T-S2-02, T-S2-04, T-S2-05). The OpenAI call,
rendering, and CLI are added by later units.
"""

import re

# --- T-S2-01: config resolution (CLI > env > default) ----------------------

# canonical key -> (env-var name, coercion callable, default value)
_CONFIG_SPEC = {
    "model": ("OPENAI_MODEL", str, "gpt-4o-mini"),
    "temperature": ("OPENAI_TEMPERATURE", float, 0.2),
    "max_tokens": ("OPENAI_MAX_TOKENS", int, 4096),
    "response_format": ("OPENAI_RESPONSE_FORMAT", str, "json_schema"),
    "timeout": ("OPENAI_TIMEOUT", int, 60),
    "retries": ("OPENAI_RETRIES", int, 3),
    "concurrency": ("OPENAI_CONCURRENCY", int, 4),
}


def resolve_config(cli: dict, env: dict) -> dict:
    """Resolve the OpenAI engine's seven runtime parameters with the fixed
    precedence CLI > env > default, coercing each to its canonical type.

    Pure: reads only the passed ``cli`` and ``env`` dicts (no os.environ).
    """
    resolved = {}
    for key, (env_name, coerce, default) in _CONFIG_SPEC.items():
        cli_value = cli.get(key)
        if cli_value is not None:
            raw = cli_value
        else:
            env_value = env.get(env_name)
            if env_value is not None and env_value != "":
                raw = env_value
            else:
                raw = default
        resolved[key] = coerce(raw)
    return resolved


# --- T-S2-02: fill_prompt ---------------------------------------------------

# recognized placeholder -> dotted source path in the artifact (scalars only)
_SCALAR_PLACEHOLDERS = {
    "video_id": ("video", "id"),
    "video_url": ("video", "url"),
    "video_title": ("video", "title"),
    "channel": ("video", "channel"),
    "description": ("video", "description"),
    "collection_title": ("collection", "title"),
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w]+)\s*\}\}")

_NO_TRANSCRIPT = "(no transcript available)"


def _scalar(artifact: dict, path) -> str:
    """Defensive read of a nested scalar; missing/None -> empty string."""
    node = artifact
    for part in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(part)
        if node is None:
            return ""
    if node is None:
        return ""
    return str(node)


def _render_transcript(artifact: dict) -> str:
    transcript = artifact.get("transcript")
    if not isinstance(transcript, dict) or not transcript.get("available"):
        return _NO_TRANSCRIPT
    segments = transcript.get("segments")
    if not segments:
        return _NO_TRANSCRIPT
    lines = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        index = seg.get("index", "")
        start = seg.get("start", "")
        text = seg.get("text", "")
        if text is None:
            text = ""
        lines.append(f"[{index}] ({start}s) {text}")
    return "\n".join(lines)


def fill_prompt(template: str, artifact: dict) -> str:
    """Replace every recognized ``{{placeholder}}`` with a value derived
    defensively from the artifact. Raise ValueError on an unrecognized token.
    Never mutates the artifact.
    """
    recognized = set(_SCALAR_PLACEHOLDERS) | {"transcript"}

    def _resolve(name: str) -> str:
        if name == "transcript":
            return _render_transcript(artifact)
        return _scalar(artifact, _SCALAR_PLACEHOLDERS[name])

    def _sub(match):
        name = match.group(1)
        if name not in recognized:
            raise ValueError(f"Unrecognized placeholder: {{{{{name}}}}}")
        return _resolve(name)

    return _PLACEHOLDER_RE.sub(_sub, template)


# --- T-S2-04: validate_req_id ----------------------------------------------

_REQ_ID_RE = re.compile(r"^[A-Z0-9]{3,6}-[A-Z0-9-]{3,10}-\d{3}$")


def validate_req_id(req_id: str, video_id: str | None = None) -> bool:
    """True iff ``req_id`` matches the locked <MODULE>-<FEATURE>-<NNN> pattern,
    NNN is not '000', and (when given) ``video_id`` is not a substring of it.
    """
    if not isinstance(req_id, str):
        return False
    if not _REQ_ID_RE.match(req_id):
        return False
    if req_id.rsplit("-", 1)[-1] == "000":
        return False
    if video_id:
        if video_id in req_id:
            return False
    return True


# --- T-S2-05: composite-key uniqueness -------------------------------------

def dedupe_requirements(requirements: list[dict]) -> list[dict]:
    """De-duplicate on the composite key (id, source_video_id), keeping the
    first occurrence and preserving order. Does not mutate inputs.
    """
    seen = set()
    result = []
    for req in requirements:
        key = (req.get("id"), req.get("source_video_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(req)
    return result
