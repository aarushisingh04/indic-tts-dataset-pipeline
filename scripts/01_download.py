"""
Stage 1 — Download sources defined in config.yaml.

For each source:
  - Downloads only the declared sections (time ranges) if specified,
    otherwise downloads the full audio.
  - Saves a WAV file + metadata.json in data/raw/<source_id>/

Usage:
    python scripts/01_download.py                   # all sources
    python scripts/01_download.py --id sp01_hi      # one source
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
import yt_dlp

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"

_WINGET_FFMPEG = Path(os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
))


def ffmpeg_dir() -> str:
    if shutil.which("ffmpeg"):
        return ""           # already in PATH; yt-dlp will find it
    if _WINGET_FFMPEG.is_file():
        return str(_WINGET_FFMPEG.parent)
    raise RuntimeError(
        "ffmpeg not found. Add it to PATH or install via: winget install ffmpeg"
    )


def ensure_ffmpeg_in_path() -> None:
    """Inject ffmpeg's directory into PATH so yt-dlp finds it for partial downloads."""
    if shutil.which("ffmpeg"):
        return
    if _WINGET_FFMPEG.is_file():
        os.environ["PATH"] = str(_WINGET_FFMPEG.parent) + os.pathsep + os.environ.get("PATH", "")
    else:
        raise RuntimeError(
            "ffmpeg not found. Add it to PATH or install via: winget install ffmpeg"
        )


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_ydl_opts(source: dict, out_template: str, ffmpeg_path: str) -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }
        ],
        "continuedl": True,   # resume partial downloads on network drop
        "retries": 5,
        "quiet": False,
        "no_warnings": False,
    }

    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path

    sections = source.get("sections")
    if sections:
        ranges = [(float(s), float(e)) for s, e in sections]
        opts["download_ranges"] = yt_dlp.utils.download_range_func(None, ranges)
        opts["force_keyframes_at_cuts"] = True

    return opts


def fetch_info(url: str, ffmpeg_path: str) -> dict:
    opts = {"quiet": True, "skip_download": True}
    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
    }


def download_source(source: dict, ffmpeg_path: str) -> None:
    src_id = source["id"]
    out_dir = DATA_RAW / src_id
    out_dir.mkdir(parents=True, exist_ok=True)

    wav_path = out_dir / "audio.wav"
    meta_path = out_dir / "metadata.json"

    if wav_path.exists():
        print(f"[{src_id}] already downloaded, skipping.")
        return

    print(f"[{src_id}] Fetching video info …")
    video_info = fetch_info(source["url"], ffmpeg_path)

    out_template = str(out_dir / "audio")
    opts = build_ydl_opts(source, out_template, ffmpeg_path)

    print(f"[{src_id}] Downloading{' sections ' + str(source['sections']) if source.get('sections') else ''} …")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([source["url"]])

    metadata = {
        "source_id": src_id,
        "url": source["url"],
        "language": source["language"],
        "speaker_id": source["speaker_id"],
        "sections": source.get("sections"),
        "license": source.get("license"),
        "credit": source.get("credit"),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        **video_info,
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{src_id}] Done → {wav_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Download a single source by its id")
    args = parser.parse_args()

    config = load_config()
    sources = config["sources"]

    if args.id:
        sources = [s for s in sources if s["id"] == args.id]
        if not sources:
            sys.exit(f"No source with id '{args.id}' found in config.yaml")

    try:
        ensure_ffmpeg_in_path()
        ffmpeg_path = ffmpeg_dir()
    except RuntimeError as e:
        sys.exit(str(e))

    for source in sources:
        try:
            download_source(source, ffmpeg_path)
        except Exception as e:
            print(f"[{source['id']}] ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
