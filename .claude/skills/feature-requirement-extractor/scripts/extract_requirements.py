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

import json
import pathlib
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


# --- T-S2-03: parse_response / render_markdown -----------------------------

def parse_response(response) -> dict:
    """Turn a captured OpenAI ``json_schema`` chat-completion response into the
    canonical structured requirements document (the "mirrored JSON").

    Reads ``response.choices[0].message.content`` (a JSON string) and parses it.
    Raises a clear, secret-safe ``ValueError`` when the response cannot yield a
    document (no choices, refusal/empty content, or invalid JSON). Pure: no I/O,
    no network, never mutates ``response``.
    """
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("OpenAI response has no choices to parse")

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if content is None or (isinstance(content, str) and content.strip() == ""):
        raise ValueError(
            "OpenAI response has empty/no content (possible refusal); "
            "cannot parse a requirements document"
        )

    try:
        doc = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"OpenAI response content is not valid JSON: {exc}"
        ) from None

    if not isinstance(doc, dict):
        raise ValueError(
            "OpenAI response content did not decode to a JSON object"
        )
    return doc


def _header_fields(doc: dict, artifact: dict | None) -> dict:
    """Resolve source-header fields from the artifact when supplied, else from
    ``doc['source']``. Missing values degrade to empty strings."""
    title = url = channel = collection = ""
    if isinstance(artifact, dict):
        video = artifact.get("video")
        if isinstance(video, dict):
            title = video.get("title") or ""
            url = video.get("url") or ""
            channel = video.get("channel") or ""
        coll = artifact.get("collection")
        if isinstance(coll, dict):
            collection = coll.get("title") or ""
    else:
        source = doc.get("source") if isinstance(doc, dict) else None
        if isinstance(source, dict):
            title = source.get("title") or source.get("video_title") or ""
            url = source.get("url") or source.get("video_url") or ""
            channel = source.get("channel") or ""
            collection = (
                source.get("collection")
                or source.get("collection_title")
                or ""
            )
    return {
        "title": str(title),
        "url": str(url),
        "channel": str(channel),
        "collection": str(collection),
    }


def render_markdown(doc: dict, artifact: dict | None = None) -> str:
    """Render the structured requirements document as Markdown — source header,
    mini-summary, Module->Feature->Requirements (ids, text, trace), Assumptions,
    Open Questions. Pure; never mutates ``doc`` or ``artifact``. Missing optional
    fields degrade gracefully (no literal ``None`` text)."""
    header = _header_fields(doc, artifact)
    lines = []

    title = header["title"] or "(untitled)"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- **URL:** {header['url']}")
    lines.append(f"- **Channel:** {header['channel']}")
    lines.append(f"- **Collection:** {header['collection']}")
    lines.append("")

    summary = doc.get("summary") if isinstance(doc, dict) else None
    lines.append("## Summary")
    lines.append("")
    lines.append(str(summary) if summary else "")
    lines.append("")

    lines.append("## Requirements")
    lines.append("")
    modules = doc.get("modules") if isinstance(doc, dict) else None
    for module in modules or []:
        if not isinstance(module, dict):
            continue
        code = module.get("code") or ""
        m_title = module.get("title")
        heading = f"### {code}" + (f" — {m_title}" if m_title else "")
        lines.append(heading)
        lines.append("")
        for feature in module.get("features") or []:
            if not isinstance(feature, dict):
                continue
            f_code = feature.get("code") or ""
            f_title = feature.get("title")
            f_heading = f"#### {f_code}" + (f" — {f_title}" if f_title else "")
            lines.append(f_heading)
            lines.append("")
            for req in feature.get("requirements") or []:
                if not isinstance(req, dict):
                    continue
                rid = req.get("id") or ""
                text = req.get("text") or ""
                trace = req.get("trace")
                trace_parts = []
                if isinstance(trace, dict):
                    ts = trace.get("timestamp")
                    seg = trace.get("segment_index")
                    if ts is not None:
                        trace_parts.append(f"timestamp {ts}")
                    if seg is not None:
                        trace_parts.append(f"segment {seg}")
                trace_str = f" _(trace: {', '.join(trace_parts)})_" if trace_parts else ""
                lines.append(f"- **{rid}**: {text}{trace_str}")
            lines.append("")

    lines.append("## Assumptions")
    lines.append("")
    assumptions = doc.get("assumptions") if isinstance(doc, dict) else None
    for item in assumptions or []:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Open Questions")
    lines.append("")
    open_questions = doc.get("open_questions") if isinstance(doc, dict) else None
    for item in open_questions or []:
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines)


# --- T-S2-06: require_api_key ----------------------------------------------

def require_api_key(env: dict) -> str:
    """Return ``OPENAI_API_KEY`` from ``env`` (whitespace-trimmed) when present
    and non-blank; otherwise raise a clear, secret-safe ``RuntimeError`` naming
    the variable and the remediation. Pure: reads only ``env``, never mutates it,
    no os.environ / file / network access."""
    value = env.get("OPENAI_API_KEY") if isinstance(env, dict) else None
    if value is not None and str(value).strip() != "":
        return str(value).strip()
    raise RuntimeError(
        "OPENAI_API_KEY is not set. Add it to your .env file or the environment "
        "before running the OpenAI engine."
    )


# --- T-S2-07: resolve_inputs / load_artifact -------------------------------

def resolve_inputs(path) -> list:
    """Decide whether ``path`` is a single artifact file or a collection folder
    and return the ordered list of artifact JSON paths to process.

    Single file -> ``[path]``. Directory -> read ``_manifest.json`` and keep
    members with ``status == 'ok'`` that carry a usable ``files.json``, in member
    order. Raises a clear error for a non-existent path or a directory without a
    usable manifest. Read-only."""
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input path does not exist: {p}")

    if p.is_file():
        return [p]

    manifest_path = p / "_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"No _manifest.json found in collection directory: {p}"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ValueError(
            f"Could not read _manifest.json in {p}: {exc}"
        ) from None

    results = []
    members = manifest.get("members") if isinstance(manifest, dict) else None
    for member in members or []:
        if not isinstance(member, dict):
            continue
        if member.get("status") != "ok":
            continue
        files = member.get("files")
        if not isinstance(files, dict):
            continue
        json_name = files.get("json")
        if not json_name:
            continue
        results.append(p / json_name)
    return results


def load_artifact(path) -> dict:
    """Read one ``<video_id>.json`` artifact (UTF-8) and return it as a dict.

    Defensive ``schema_version`` read: a missing or unknown version does not
    raise. A genuinely unreadable/non-JSON file raises a clear error. Read-only;
    never mutates; never hits the network."""
    p = pathlib.Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read artifact file {p}: {exc}") from None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ValueError(
            f"Artifact file {p} is not valid JSON: {exc}"
        ) from None
    if not isinstance(data, dict):
        raise ValueError(f"Artifact file {p} did not decode to a JSON object")
    return data
