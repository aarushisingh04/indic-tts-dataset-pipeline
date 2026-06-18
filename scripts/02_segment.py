"""
Stage 2 — Segment each downloaded audio into chunks using silence detection.

Reads segmentation settings from config.yaml.
Inputs:  data/raw/<source_id>/audio.wav
Outputs: data/segments/<source_id>/seg_XXXX.wav
         data/segments/<source_id>/segments.json  (manifest)

Usage:
    python scripts/02_segment.py                  # all sources
    python scripts/02_segment.py --id sp01_hi_01  # one source
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from pydub import AudioSegment
from pydub.silence import split_on_silence

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_SEG = ROOT / "data" / "segments"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_silence_boundary(chunk: AudioSegment, target_ms: int, silence_thresh: int,
                           lookback_ms: int = 8000) -> int:
    """
    Find the best cut point near target_ms by scanning backwards for silence.
    Returns the cut position in ms. Falls back to target_ms if no silence found.
    """
    scan_start = max(0, target_ms - lookback_ms)
    step = 50  # ms
    best_pos = target_ms
    best_db = chunk[target_ms:target_ms + step].dBFS  # baseline at hard cut

    for pos in range(target_ms, scan_start, -step):
        window = chunk[pos - step:pos]
        if len(window) < step:
            continue
        if window.dBFS < silence_thresh:
            return pos  # found a silent point, use it
        if window.dBFS < best_db:
            best_db = window.dBFS
            best_pos = pos

    return best_pos


def soft_split(chunk: AudioSegment, max_ms: int, silence_thresh: int) -> list[AudioSegment]:
    """Split long chunks at the nearest silence to max_ms, not at a hard boundary."""
    if len(chunk) <= max_ms:
        return [chunk]
    parts = []
    start = 0
    while start < len(chunk):
        remaining = len(chunk) - start
        if remaining <= max_ms:
            parts.append(chunk[start:])
            break
        cut = find_silence_boundary(chunk, start + max_ms, silence_thresh)
        parts.append(chunk[start:cut])
        start = cut
    return parts


def segment_source(source: dict, cfg: dict) -> None:
    src_id = source["id"]
    wav_in = DATA_RAW / src_id / "audio.wav"

    if not wav_in.exists():
        print(f"[{src_id}] audio.wav not found — run 01_download.py first", file=sys.stderr)
        return

    out_dir = DATA_SEG / src_id
    manifest_path = out_dir / "segments.json"

    if manifest_path.exists():
        print(f"[{src_id}] already segmented, skipping.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    seg_cfg = cfg["segmentation"]
    min_ms = int(seg_cfg["min_duration"]) * 1000
    max_ms = int(seg_cfg["max_duration"]) * 1000
    silence_thresh = int(seg_cfg["silence_thresh_db"])
    min_silence_ms = int(seg_cfg["min_silence_ms"])

    print(f"[{src_id}] Loading audio …")
    audio = AudioSegment.from_wav(str(wav_in))

    print(f"[{src_id}] Splitting on silence (thresh={silence_thresh}dB, min_silence={min_silence_ms}ms) …")
    raw_chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh,
        keep_silence=200,   # 200ms padding at each boundary — avoids clipped words
        seek_step=50,
    )

    # Enforce min/max duration
    chunks = []
    for chunk in raw_chunks:
        if len(chunk) < min_ms:
            continue
        chunks.extend(soft_split(chunk, max_ms, silence_thresh))

    print(f"[{src_id}] {len(raw_chunks)} raw chunks → {len(chunks)} kept after duration filter")

    manifest = []
    for i, chunk in enumerate(chunks):
        seg_id = f"{src_id}_seg_{i:04d}"
        seg_path = out_dir / f"seg_{i:04d}.wav"
        chunk.export(str(seg_path), format="wav")

        manifest.append({
            "segment_id": seg_id,
            "source_id": src_id,
            "speaker_id": source["speaker_id"],
            "language": source["language"],
            "duration_sec": round(len(chunk) / 1000, 2),
            "audio_path": str(seg_path.relative_to(ROOT)),
        })

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total_min = sum(s["duration_sec"] for s in manifest) / 60
    print(f"[{src_id}] Done — {len(manifest)} segments, {total_min:.1f} min total → {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Process a single source by its id")
    args = parser.parse_args()

    config = load_config()
    sources = config["sources"]

    if args.id:
        sources = [s for s in sources if s["id"] == args.id]
        if not sources:
            sys.exit(f"No source with id '{args.id}' found in config.yaml")

    for source in sources:
        try:
            segment_source(source, config)
        except Exception as e:
            print(f"[{source['id']}] ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
