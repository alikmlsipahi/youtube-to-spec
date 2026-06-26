#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["yt-dlp>=2024.0.0", "youtube-transcript-api>=1.0.0"]
# ///
"""
youtube-artifact-collector — extract rich metadata + timestamped segment
transcripts from YouTube videos/playlists into lossless JSON + readable Markdown.

This module currently implements the pure, offline, deterministic helpers
(A1: T-S1-01 … T-S1-04). The fetch/render/write functions are added in later
build steps.
"""

import re
from dataclasses import dataclass, field


# --- T-S1-01: extract_video_id (copied verbatim from
#     .claude/skills/youtube-transcript/scripts/get_transcript.py lines 19-29) ---
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


# --- T-S1-02: format_timestamp (copied verbatim from
#     .claude/skills/youtube-transcript/scripts/get_transcript.py lines 32-39) ---
def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


# --- T-S1-03: classify_input ---

# A `list=` query parameter (playlist context) on any YouTube URL.
_LIST_RE = re.compile(r'[?&]list=([A-Za-z0-9_-]+)')

# A watchable video component in any of the recognized URL shapes, or a bare id.
_VIDEO_RE = re.compile(
    r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)[a-zA-Z0-9_-]{11}'
)
_BARE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')


@dataclass
class ClassifiedInput:
    """Result of classify_input: how a run should be routed.

    mode      -- one of "single", "multiple", "playlist".
    targets   -- the positional url_or_id values the user supplied (verbatim).
    playlist  -- for mode == "playlist", the playlist id to enumerate; else None.
    """
    mode: str
    targets: list = field(default_factory=list)
    playlist: str = None


def _list_id(value: str) -> str:
    """Return the playlist id from a `list=` parameter, or None if absent."""
    match = _LIST_RE.search(value)
    return match.group(1) if match else None


def _has_video(value: str) -> bool:
    """True if the value carries a watchable video component or is a bare 11-char id."""
    return bool(_VIDEO_RE.search(value)) or bool(_BARE_ID_RE.match(value))


def classify_input(args) -> ClassifiedInput:
    """Decide how a run is routed: single | multiple | playlist.

    `args` is the parsed CLI input — an argparse namespace (or equivalent) with
    a positionals list `url_or_id` and a boolean `playlist` flag.

    Precedence:
      1. More than one positional input        -> multiple.
      2. A single pure-playlist URL            -> playlist.
      3. A single watch?v=...&list=... URL     -> playlist iff --playlist, else single.
      4. A single plain video URL or bare id   -> single.

    No I/O; purely string-shape + flag based.
    """
    targets = list(getattr(args, 'url_or_id', None) or [])
    playlist_flag = bool(getattr(args, 'playlist', False))

    # Rule 1: more than one input -> multiple (per-input playlist expansion is
    # out of scope; each positional is its own target).
    if len(targets) > 1:
        return ClassifiedInput(mode='multiple', targets=targets, playlist=None)

    if len(targets) == 1:
        single = targets[0]
        pid = _list_id(single)
        is_video = _has_video(single)

        if pid and not is_video:
            # Rule 2: pure playlist URL -> playlist (flag redundant but harmless).
            return ClassifiedInput(mode='playlist', targets=targets, playlist=pid)
        if pid and is_video:
            # Rule 3: watch?v=...&list=... -> playlist only when promoted by --playlist.
            if playlist_flag:
                return ClassifiedInput(mode='playlist', targets=targets, playlist=pid)
            return ClassifiedInput(mode='single', targets=targets, playlist=None)
        # Rule 4: plain video URL or bare id. --playlist with no playlist id to
        # expand falls back to single (nothing to enumerate).
        return ClassifiedInput(mode='single', targets=targets, playlist=None)

    # No inputs: nothing to route. Treat as single (empty) — callers validate.
    return ClassifiedInput(mode='single', targets=targets, playlist=None)


# --- T-S1-04: slugify / collection_dir_name ---

# Turkish-specific letters -> closest plain-ASCII equivalents (both cases).
# Applied BEFORE lowercasing so the dotted-capital-I pitfall (İ.lower() -> "i̇")
# never leaks through.
_TR_TRANSLIT = str.maketrans({
    'ı': 'i', 'İ': 'i',
    'ş': 's', 'Ş': 's',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ö': 'o', 'Ö': 'o',
    'ç': 'c', 'Ç': 'c',
})

# Stable, filesystem-safe fallback for degenerate titles that slugify to nothing.
_SLUG_FALLBACK = 'untitled'


def slugify(text: str) -> str:
    """Turn arbitrary title text into a safe lowercase ASCII directory slug.

    Steps, in order: Turkish transliteration -> lowercase -> whitespace to
    hyphen -> drop chars outside [a-z0-9-] -> collapse repeated hyphens and trim
    edge hyphens. Degenerate input yields a stable safe fallback.
    """
    s = text.translate(_TR_TRANSLIT)
    s = s.lower()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    s = re.sub(r'-+', '-', s)
    s = s.strip('-')
    return s or _SLUG_FALLBACK


def collection_dir_name(title: str, playlist_id: str) -> str:
    """Per-collection directory name: <slug-of-title>-<playlist_id>.

    The playlist id is appended VERBATIM (not slugified) so it round-trips back
    to the playlist and guarantees uniqueness even when titles collide.
    """
    return f"{slugify(title)}-{playlist_id}"
