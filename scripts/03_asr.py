"""
Stage 3 — Transcribe segments using Sarvam Saaras v3 STT API.

Reads reject.txt from each segment folder (one segment number per line)
and skips those segments.

Inputs:  data/segments/<source_id>/seg_XXXX.wav
         data/segments/<source_id>/reject.txt  (optional)
Outputs: data/segments/<source_id>/transcripts.json

Usage:
    python scripts/03_asr.py                   # all sources
    python scripts/03_asr.py --id sp03_en_01   # one source
    python scripts/03_asr.py --mode verbatim   # override transcription mode
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_SEG = ROOT / "data" / "segments"
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_rejects(seg_dir: Path) -> set[str]:
    reject_file = seg_dir / "reject.txt"
    if not reject_file.exists():
        return set()
    lines = reject_file.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def transcribe_segment(wav_path: Path, language: str, mode: str, api_key: str) -> dict | None:
    with open(wav_path, "rb") as f:
        resp = requests.post(
            SARVAM_STT_URL,
            headers={"api-subscription-key": api_key},
            data={"model": "saaras:v3", "mode": mode, "language_code": language},
            files={"file": (wav_path.name, f, "audio/wav")},
            timeout=60,
        )

    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 429:
        print("    Rate limited — waiting 10s …")
        time.sleep(10)
        return transcribe_segment(wav_path, language, mode, api_key)  # retry once
    print(f"    API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
    return None


def process_source(source: dict, mode: str, api_key: str) -> None:
    src_id = source["id"]
    seg_dir = DATA_SEG / src_id
    manifest_path = seg_dir / "segments.json"
    out_path = seg_dir / "transcripts.json"

    if not manifest_path.exists():
        print(f"[{src_id}] segments.json not found — run 02_segment.py first", file=sys.stderr)
        return

    segments = json.loads(manifest_path.read_text(encoding="utf-8"))
    rejects = load_rejects(seg_dir)

    # Load existing transcripts so we can resume interrupted runs
    existing = {}
    if out_path.exists():
        existing = {r["segment_id"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))}

    results = list(existing.values())
    done_ids = set(existing.keys())

    to_process = [
        s for s in segments
        if s["segment_id"] not in done_ids
        and _seg_num(s["segment_id"]) not in rejects
    ]

    print(f"[{src_id}] {len(segments)} segments | {len(rejects)} rejected | "
          f"{len(done_ids)} already done | {len(to_process)} to transcribe")

    for i, seg in enumerate(to_process, 1):
        wav_path = ROOT / seg["audio_path"]
        print(f"  [{i}/{len(to_process)}] {seg['segment_id']} ({seg['duration_sec']}s) …", end=" ", flush=True)

        result = transcribe_segment(wav_path, source["language"], mode, api_key)

        if result is None:
            print("FAILED — skipped")
            continue

        transcript = result.get("transcript", "").strip()
        print(f"ok — {len(transcript)} chars")

        results.append({
            "segment_id": seg["segment_id"],
            "source_id": src_id,
            "speaker_id": seg["speaker_id"],
            "language": seg["language"],
            "duration_sec": seg["duration_sec"],
            "audio_path": seg["audio_path"],
            "transcript": transcript,
            "language_detected": result.get("language_code"),
            "asr_mode": mode,
        })

        # Save after every segment so a crash doesn't lose progress
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        time.sleep(0.3)  # gentle rate limiting

    print(f"[{src_id}] Done — {len(results)} transcripts saved to {out_path}")


def _seg_num(segment_id: str) -> str:
    """Extract the 4-digit segment number from a segment_id like sp01_hi_01_seg_0003."""
    return segment_id.split("_seg_")[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Process a single source by id")
    parser.add_argument("--mode", default="transcribe",
                        choices=["transcribe", "verbatim"],
                        help="Saaras v3 transcription mode (default: transcribe)")
    args = parser.parse_args()

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        sys.exit("SARVAM_API_KEY not set. Copy .env.example to .env and add your key.")

    config = load_config()
    sources = config["sources"]

    if args.id:
        sources = [s for s in sources if s["id"] == args.id]
        if not sources:
            sys.exit(f"No source with id '{args.id}' found in config.yaml")

    for source in sources:
        try:
            process_source(source, args.mode, api_key)
        except Exception as e:
            print(f"[{source['id']}] ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
