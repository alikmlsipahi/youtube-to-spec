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

import argparse
import json
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from youtube_transcript_api import YouTubeTranscriptApi


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


def request_delay(base: float, rng: Callable[[], float] = random.random) -> float:
    """Compute a jittered request delay for the ``--sleep-requests`` flag.

    Pure computation only — never sleeps. ``base <= 0`` means "no delay" and
    returns ``0.0`` without invoking ``rng``. Otherwise returns a value drawn
    uniformly from ``[base, 2*base)`` via ``base + base * rng()``, so repeated
    calls do not sleep for an identical, bot-like interval.
    """
    if base <= 0:
        return 0.0
    return base + base * rng()


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


def render_markdown(artifact: dict) -> str:
    """Render one canonical per-video artifact dict into the readable Markdown view.

    A metadata header (title/url/channel/collection) followed by a transcript
    section: one ``[<ts>] <text>`` line per segment, where ``<ts>`` comes from
    ``format_timestamp(segment["start"])``. Segment text is reproduced verbatim;
    a missing/empty transcript yields a short note instead of segment lines. The
    collection line is always emitted (placeholder when standalone) to preserve
    video↔collection relational integrity in the readable view.
    """
    video = artifact.get("video") or {}
    collection = artifact.get("collection")
    transcript = artifact.get("transcript") or {}

    title = video.get("title")
    url = video.get("url")
    channel = video.get("channel")

    placeholder = "—"
    if collection:
        collection_title = collection.get("title") or placeholder
    else:
        collection_title = placeholder

    lines = [
        f"# {title if title is not None else placeholder}",
        "",
        f"- **URL:** {url if url is not None else placeholder}",
        f"- **Channel:** {channel if channel is not None else placeholder}",
        f"- **Collection:** {collection_title}",
        "",
        "## Transcript",
        "",
    ]

    segments = transcript.get("segments") or []
    if transcript.get("available") and segments:
        for segment in segments:
            ts = format_timestamp(segment["start"])
            lines.append(f"[{ts}] {segment['text']}")
    else:
        lines.append("_No transcript available._")

    return "\n".join(lines)


def build_manifest(collection: dict, members: list[dict]) -> dict:
    """Assemble the in-memory `_manifest.json` object for one collection.

    Pairs the collection descriptor with an order-preserving member list (each
    member carrying status and, on failure, a reason) plus a computed summary of
    counts. Failed/skipped members are always listed — never dropped — and their
    ``files`` is forced to ``null``. ``no_transcript`` counts only succeeded
    members whose transcript is unavailable.
    """
    emitted_members = []
    ok_count = 0
    failed_count = 0
    no_transcript_count = 0

    for record in members:
        status = record.get("status")
        is_ok = status == "ok"

        files = record.get("files") if is_ok else None

        emitted_members.append(
            {
                "position": record.get("position"),
                "video_id": record.get("video_id"),
                "title": record.get("title"),
                "status": status,
                "reason": record.get("reason"),
                "files": files,
                "transcript": record.get("transcript"),
            }
        )

        if is_ok:
            ok_count += 1
            transcript = record.get("transcript")
            if not transcript or transcript.get("available") is not True:
                no_transcript_count += 1
        else:
            failed_count += 1

    summary = {
        "total": len(members),
        "ok": ok_count,
        "failed": failed_count,
        "no_transcript": no_transcript_count,
    }

    return {
        "collection": collection,
        "members": emitted_members,
        "summary": summary,
    }


def parse_hidden_unavailable(stderr: str) -> int:
    """Parse yt-dlp's stderr for the count of hidden unavailable playlist videos.

    Extracts the integer that immediately precedes the phrase
    ``unavailable videos`` in yt-dlp's WARNING line; returns the first
    occurrence's count, or ``0`` when no such warning is present. Never raises.
    """
    if not stderr:
        return 0
    match = re.search(r"(\d+)\s+unavailable videos", stderr)
    if match:
        return int(match.group(1))
    return 0


def fetch_metadata(video_id: str) -> dict | None:
    """Fetch one video's metadata via yt-dlp subprocess; ``None`` on any failure.

    Shells out to ``yt-dlp --skip-download --dump-json <video_id>`` (subprocess
    for stable JSON + per-video isolation). Returns the parsed dict on a clean
    (return code 0, parseable JSON) run, otherwise ``None`` — never raises and
    never calls ``sys.exit`` so a single bad video degrades gracefully and the
    batch continues.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--dump-json", video_id],
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Orchestration layer (additive glue; wires the pure helpers above into an
# end-to-end CLI). No existing function above is modified.
# ---------------------------------------------------------------------------

_TOOL_VERSIONS_CACHE = None


def _tool_versions() -> dict:
    """Best-effort capture of the tool versions used, cached for the run."""
    global _TOOL_VERSIONS_CACHE
    if _TOOL_VERSIONS_CACHE is not None:
        return _TOOL_VERSIONS_CACHE
    versions = {"yt_dlp": None, "youtube_transcript_api": None}
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            versions["yt_dlp"] = result.stdout.strip()
    except Exception:
        pass
    try:
        from importlib.metadata import version

        versions["youtube_transcript_api"] = version("youtube-transcript-api")
    except Exception:
        pass
    _TOOL_VERSIONS_CACHE = versions
    return versions


def _empty_transcript_block() -> dict:
    """A canonical transcript block for the no-transcript / skipped case."""
    return {
        "available": False,
        "selected": None,
        "available_tracks": [],
        "segment_count": 0,
        "segments": [],
    }


def enumerate_playlist(url: str) -> dict | None:
    """List a playlist's ordered members via yt-dlp `--flat-playlist`.

    Returns ``{id, title, uploader, entries[], hidden_unavailable_count}`` (entries
    are ``{id, title}`` in playlist order), or ``None`` on failure. Unavailable
    members still appear in the flat list — carrying a null title — and yt-dlp
    *additionally* reports their count on stderr; that count is recovered via
    :func:`parse_hidden_unavailable`. They enumerate fine and fail later, at the
    per-video metadata fetch, which is what makes them `metadata_failed` members
    rather than missing ones. Uses subprocess for per-run isolation and stable
    JSON, consistent with :func:`fetch_metadata`.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-single-json", url],
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except Exception:
        return None

    entries = []
    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        entries.append({"id": entry.get("id"), "title": entry.get("title")})

    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "uploader": data.get("uploader") or data.get("channel"),
        "entries": entries,
        "hidden_unavailable_count": parse_hidden_unavailable(result.stderr or ""),
    }


def fetch_transcript(video_id: str, langs) -> dict:
    """Fetch and assemble the canonical ``transcript{}`` block for one video.

    Lists the available tracks, picks one via :func:`select_transcript_track`,
    fetches its snippets, and builds addressable segments via
    :func:`build_segments`. Never raises — any failure (transcripts disabled, none
    found, network error) degrades to an ``available: False`` block so the batch
    continues.
    """
    try:
        track_list = list(YouTubeTranscriptApi().list(video_id))
    except Exception:
        return _empty_transcript_block()

    selected_track, info = select_transcript_track(track_list, langs)
    if selected_track is None:
        block = _empty_transcript_block()
        block["available_tracks"] = info["available_tracks"]
        return block

    try:
        snippets = selected_track.fetch()
        segments = build_segments(snippets)
    except Exception:
        block = _empty_transcript_block()
        block["available_tracks"] = info["available_tracks"]
        return block

    return {
        "available": True,
        "selected": info["selected"],
        "available_tracks": info["available_tracks"],
        "segment_count": len(segments),
        "segments": segments,
    }


def common_title_prefix(titles) -> str:
    """Longest slug-token run shared by every usable title in a collection.

    Collection members routinely repeat a channel/series boilerplate on every
    title, which would otherwise dominate each basename. Returns ``""`` rather
    than a prefix that is meaningless (fewer than three titles to compare) or
    destructive (stripping it would leave some member with nothing).
    """
    token_lists = [slugify(t).split("-") for t in titles if t]
    token_lists = [tokens for tokens in token_lists if tokens != [""]]
    if len(token_lists) < 3:
        return ""

    shared = 0
    while (
        all(len(tokens) > shared for tokens in token_lists)
        and len({tokens[shared] for tokens in token_lists}) == 1
    ):
        shared += 1

    if not shared or any(len(tokens) == shared for tokens in token_lists):
        return ""
    return "-".join(token_lists[0][:shared])


def scan_existing(out_dir: Path) -> dict:
    """Map ``{video_id: basename}`` over artifacts already written to ``out_dir``.

    A basename is no longer derivable from a video id alone, so ``--skip-existing``
    resolves the other way round: read the ids back off disk. Local I/O only, which
    preserves the flag's guarantee of making no network request. Skips the manifest
    and Skill 2's requirement docs; unreadable files are ignored.
    """
    index = {}
    if not out_dir.is_dir():
        return index

    for path in sorted(out_dir.glob("*.json")):
        if path.name == "_manifest.json" or path.name.endswith(".requirements.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        video = data.get("video")
        video_id = video.get("id") if isinstance(video, dict) else None
        if video_id:
            index[video_id] = path.stem
    return index


def artifact_basename(
    video_id: str,
    title: str | None = None,
    position: int | None = None,
    total: int | None = None,
    strip_prefix: str = "",
) -> str:
    """Centralized per-video artifact basename (one edit point for layout changes).

    ``<position>-<slug>`` inside a collection, bare ``<slug>`` standalone. The video
    id is the fallback for any title that yields no usable slug — absent, emoji-only,
    or written in a script `slugify` transliterates away. Position width follows the
    member count so lexical order matches playlist order past nine members.
    """
    slug = slugify(title) if title else ""
    if strip_prefix and slug.startswith(f"{strip_prefix}-"):
        slug = slug[len(strip_prefix) + 1:]
    if not slug:
        slug = video_id

    if position is None:
        return slug
    width = max(2, len(str(total))) if total else 2
    return f"{position:0{width}d}-{slug}"


def build_artifact(meta: dict, transcript_block: dict, collection_block) -> dict:
    """Assemble one canonical per-video artifact dict from its parts."""
    return {
        "schema_version": "1.0",
        "kind": "video_artifact",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "video": build_video_block(meta),
        "collection": collection_block,
        "transcript": transcript_block,
        "extraction": {
            "metadata_ok": meta is not None,
            "transcript_ok": bool(transcript_block.get("available")),
            "warnings": [],
            "tool_versions": _tool_versions(),
        },
    }


def write_artifacts(
    artifact: dict, out_dir: Path, fmt: str, basename: str | None = None
) -> dict:
    """Write the per-video ``.json`` and/or ``.md`` files; return the manifest
    ``files{json,md}`` descriptor (each name or ``None``)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base = basename or artifact_basename(artifact["video"]["id"])
    files = {"json": None, "md": None}
    if fmt in ("json", "both"):
        path = out_dir / f"{base}.json"
        path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        files["json"] = path.name
    if fmt in ("md", "both"):
        path = out_dir / f"{base}.md"
        path.write_text(render_markdown(artifact), encoding="utf-8")
        files["md"] = path.name
    return files


def write_manifest(collection: dict, members: list[dict], out_dir: Path) -> None:
    """Write ``_manifest.json`` for a collection via :func:`build_manifest`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(collection, members)
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_artifacts.py",
        description=(
            "Collect metadata AND timestamped transcripts for one or more videos "
            "or a playlist into lossless JSON + Markdown artifacts."
        ),
    )
    parser.add_argument("urls", nargs="+", help="Video URLs/IDs or a playlist URL.")
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Treat a watch?v=…&list=… URL as the whole playlist.",
    )
    parser.add_argument(
        "--langs",
        default="tr,en",
        help="Transcript language preference list (comma-separated).",
    )
    parser.add_argument("--out-dir", dest="out_dir", default=None,
                        help="Override the collection directory name.")
    parser.add_argument("--root", default="data", help="Output root directory.")
    save_group = parser.add_mutually_exclusive_group()
    save_group.add_argument("--no-save", action="store_true",
                            help="Print artifacts instead of writing files.")
    save_group.add_argument("--print", dest="print_", action="store_true",
                            help="Print artifacts instead of writing files.")
    parser.add_argument("--format", choices=["json", "md", "both"], default="both",
                        help="Which per-video files to write.")
    parser.add_argument("--metadata-only", dest="metadata_only", action="store_true",
                        help="Skip transcript fetching.")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true",
                        help="Skip videos whose JSON already exists.")
    parser.add_argument("--sleep-requests", dest="sleep_requests", type=float,
                        default=0.0, help="Seconds to sleep between videos.")
    return parser


def main(argv=None) -> int:
    args = _build_arg_parser().parse_args(argv)
    langs = [s.strip() for s in args.langs.split(",") if s.strip()]
    print_mode = args.print_ or args.no_save
    mode = classify_input(args)

    # Build the work list of (video_id, title, position, collection_block).
    collection_info = None
    work = []
    if mode == "playlist":
        playlist = enumerate_playlist(args.urls[0])
        if playlist is None:
            print("Failed to enumerate playlist.", file=sys.stderr)
            return 1
        collection_info = {
            "type": "playlist",
            "id": playlist["id"],
            "title": playlist["title"],
            "uploader": playlist.get("uploader"),
            "source_url": args.urls[0],
            "hidden_unavailable_count": playlist.get("hidden_unavailable_count", 0),
        }
        total = len(playlist["entries"])
        for position, entry in enumerate(playlist["entries"], start=1):
            block = {
                "type": "playlist",
                "id": playlist["id"],
                "title": playlist["title"],
                "uploader": playlist.get("uploader"),
                "position": position,
                "total_members": total,
            }
            work.append((entry["id"], entry.get("title"), position, block))
    else:
        for raw in args.urls:
            try:
                video_id = extract_video_id(raw)
            except ValueError:
                print(f"Skipping unrecognized input: {raw}", file=sys.stderr)
                continue
            work.append((video_id, None, None, None))

    # Resolve the output directory once.
    out_dir = Path(args.root)
    if args.out_dir:
        out_dir = out_dir / args.out_dir
    elif collection_info:
        out_dir = out_dir / collection_dir_name(
            collection_info["title"] or "", collection_info["id"] or ""
        )
    else:
        out_dir = out_dir / "_singles"

    # Collection titles tend to repeat a series boilerplate on every member; drop
    # it once so each basename leads with what distinguishes it. The flat-playlist
    # titles gathered above match the per-video metadata titles, so the prefix can
    # be settled before the fetch loop rather than buffering every artifact.
    strip_prefix = common_title_prefix([title for _, title, _, _ in work])
    total_members = len(work) if collection_info else None

    # A basename now depends on the title, so `--skip-existing` can no longer build
    # one from the video id up front. Resolve it the other way: index the ids already
    # on disk. Doubles as the collision guard for standalone videos sharing a title.
    index = {} if print_mode else scan_existing(out_dir)
    taken = {base: vid for vid, base in index.items()}

    members = []
    hit_network = False
    for video_id, title, position, collection_block in work:
        if args.skip_existing and not print_mode and video_id in index:
            members.append({
                "position": position, "video_id": video_id, "title": title,
                "status": "ok", "reason": "skipped (already exists)",
                "files": {"json": f"{index[video_id]}.json", "md": None},
                "transcript": None,
            })
            continue

        if hit_network:
            time.sleep(request_delay(args.sleep_requests))
        hit_network = True

        meta = fetch_metadata(video_id)
        if meta is None:
            members.append({
                "position": position, "video_id": video_id, "title": title,
                "status": "metadata_failed", "reason": "metadata fetch failed",
                "files": None, "transcript": None,
            })
            continue

        if args.metadata_only:
            transcript_block = _empty_transcript_block()
        else:
            transcript_block = fetch_transcript(video_id, langs)

        artifact = build_artifact(meta, transcript_block, collection_block)

        if print_mode:
            if args.format in ("json", "both"):
                print(json.dumps(artifact, ensure_ascii=False, indent=2))
            if args.format in ("md", "both"):
                print(render_markdown(artifact))
            files = None
        else:
            base = artifact_basename(
                video_id,
                meta.get("title") or title,
                position,
                total_members,
                strip_prefix,
            )
            owner = taken.get(base)
            if owner is not None and owner != video_id:
                base = f"{base}-{video_id}"
            taken[base] = video_id
            files = write_artifacts(artifact, out_dir, args.format, base)

        selected = transcript_block.get("selected") or {}
        members.append({
            "position": position, "video_id": video_id,
            "title": meta.get("title") or title,
            "status": "ok", "reason": None, "files": files,
            "transcript": {
                "available": transcript_block.get("available", False),
                "language": selected.get("language"),
                "type": selected.get("type"),
            },
        })

    if collection_info and not print_mode:
        write_manifest(collection_info, members, out_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
