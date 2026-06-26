#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp>=2024.0.0", "youtube-transcript-api>=1.0.0"]
# ///
"""
Collect YouTube artifacts (metadata + timestamped transcript) into lossless
per-video JSON + readable Markdown, with per-collection manifests.

Phase 1 — pure helpers (T-S1-01..04). Remaining functions are added by later units.
"""

import re


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from various YouTube URL formats or return as-is if already an ID."""
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def classify_input(args) -> str:
    """Decide whether a run is a single video, multiple videos, or a playlist.

    A `watch?v=…&list=…` URL is treated as a single video unless `--playlist`
    is passed. A bare playlist-collection page is always a playlist.
    """
    inputs = args.urls
    flag = args.playlist

    if len(inputs) > 1:
        return "multiple"

    s = inputs[0]
    has_video = bool(re.search(r'[?&]v=', s)) or "watch?v=" in s
    has_list = bool(re.search(r'[?&]list=', s)) or "list=" in s

    if has_list and not has_video:
        return "playlist"
    if has_video and has_list:
        return "playlist" if flag else "single"
    return "single"


# Turkish letter → ASCII transliteration (applied before lowercasing).
_TURKISH_MAP = {
    "ı": "i", "I": "i", "İ": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
}


def slugify(title: str) -> str:
    """Turn a free-text title into a filesystem-safe, ASCII, hyphenated slug."""
    # 1. Transliterate Turkish letters to ASCII (both cases).
    text = "".join(_TURKISH_MAP.get(ch, ch) for ch in title)
    # 2. Lowercase.
    text = text.lower()
    # 3. Replace every run of whitespace with a single hyphen.
    text = re.sub(r"\s+", "-", text)
    # 4. Remove every character that is not a-z, 0-9, or a hyphen.
    text = re.sub(r"[^a-z0-9-]", "", text)
    # 5. Collapse runs of hyphens.
    text = re.sub(r"-+", "-", text)
    # 6. Strip leading/trailing hyphens.
    return text.strip("-")


def collection_dir_name(title: str, playlist_id: str) -> str:
    """Compose the canonical per-collection directory name `<slug>-<playlist_id>`.

    The playlist id is appended verbatim (its own casing preserved); only the
    title portion is slugified.
    """
    return f"{slugify(title)}-{playlist_id}"


# Canonical `video{}` keys that map straight across from the yt-dlp source
# under `dict.get` semantics (absent → None, present-but-falsy preserved).
_VIDEO_PASSTHROUGH_KEYS = (
    "id", "title", "channel", "channel_id", "uploader", "upload_date",
    "description", "tags", "categories", "chapters", "availability",
)


def build_video_block(meta: dict) -> dict:
    """Project a yt-dlp `--dump-json` metadata dict to the canonical `video{}` block.

    Maps/renames the relevant yt-dlp fields into the fixed canonical key set,
    tolerates any missing optional field (`get`-semantics → ``None``), and
    guarantees a usable ``url``. Values pass through untransformed; extra
    yt-dlp keys are dropped.
    """
    block = {key: meta.get(key) for key in _VIDEO_PASSTHROUGH_KEYS}

    # Renamed fields.
    block["duration_seconds"] = meta.get("duration")
    block["default_language"] = meta.get("language")

    # Guaranteed non-null url: prefer webpage_url, else construct from id.
    webpage_url = meta.get("webpage_url")
    if webpage_url:
        block["url"] = webpage_url
    else:
        block["url"] = f"https://www.youtube.com/watch?v={meta.get('id')}"

    return block


def select_transcript_track(tracks, langs):
    """Pick the best transcript track per a language-preference list.

    Within a matched language, a manually-created track beats an auto-generated
    one; languages are tried in `langs` order. Falls back to the first available
    track when no preferred language matches. Returns ``(selected_track, info)``
    where ``info`` carries the ``selected`` descriptor and the full
    ``available_tracks`` inventory.
    """
    available_tracks = [
        {
            "language": t.language_code,
            "name": t.language,
            "is_generated": t.is_generated,
            "is_translatable": t.is_translatable,
        }
        for t in tracks
    ]

    selected_track = None
    for lang in langs:
        # Prefer manual, then auto, within this language.
        manual = next(
            (t for t in tracks if t.language_code == lang and not t.is_generated),
            None,
        )
        if manual is not None:
            selected_track = manual
            break
        auto = next(
            (t for t in tracks if t.language_code == lang and t.is_generated),
            None,
        )
        if auto is not None:
            selected_track = auto
            break

    if selected_track is None and tracks:
        selected_track = tracks[0]

    if selected_track is None:
        selected = None
    else:
        selected = {
            "language": selected_track.language_code,
            "language_name": selected_track.language,
            "type": "auto" if selected_track.is_generated else "manual",
            "is_generated": selected_track.is_generated,
        }

    info = {"selected": selected, "available_tracks": available_tracks}
    return selected_track, info


def build_segments(snippets) -> list[dict]:
    """Convert raw fetched transcript snippets into canonical addressable segments.

    Each snippet gets a stable zero-based ``index``, a computed
    ``end = start + duration``, and its ``text`` carried through byte-for-byte
    unchanged.
    """
    return [
        {
            "index": i,
            "start": snippet.start,
            "duration": snippet.duration,
            "end": snippet.start + snippet.duration,
            "text": snippet.text,
        }
        for i, snippet in enumerate(snippets)
    ]
