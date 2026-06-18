"""
Stage 4 — Normalize audio segments.

For each transcribed segment:
  - Resample to 24kHz mono
  - Loudness-normalize to -23 LUFS
  - Trim leading/trailing silence (keep 100ms padding)

Inputs:  data/segments/<source_id>/transcripts.json
Outputs: data/normalized/<source_id>/<seg_id>.wav

Usage:
    python scripts/04_normalize.py
    python scripts/04_normalize.py --id sp01_hi_01
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
import yaml
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

ROOT = Path(__file__).resolve().parent.parent
DATA_SEG = ROOT / "data" / "segments"
DATA_NORM = ROOT / "data" / "normalized"

TARGET_SR = 24000
TARGET_LUFS = -23.0
SILENCE_THRESH_DB = -50
SILENCE_PADDING_MS = 100


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def trim_silence(audio: AudioSegment) -> AudioSegment:
    start_trim = detect_leading_silence(audio, silence_threshold=SILENCE_THRESH_DB)
    end_trim = detect_leading_silence(audio.reverse(), silence_threshold=SILENCE_THRESH_DB)
    duration = len(audio)
    start = max(0, start_trim - SILENCE_PADDING_MS)
    end = max(0, end_trim - SILENCE_PADDING_MS)
    return audio[start : duration - end]


def normalize_lufs(samples: np.ndarray, sr: int) -> np.ndarray:
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(samples)
    if np.isinf(loudness) or np.isnan(loudness):
        return samples  # silent or near-silent segment — leave as-is
    return pyln.normalize.loudness(samples, loudness, TARGET_LUFS)


def load_rejects(src_id: str) -> set[str]:
    reject_path = DATA_SEG / src_id / "reject.txt"
    if not reject_path.exists():
        return set()
    return {
        ln.strip()
        for ln in reject_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    }


def process_source(source: dict) -> None:
    src_id = source["id"]
    transcript_path = DATA_SEG / src_id / "transcripts.json"

    if not transcript_path.exists():
        print(f"[{src_id}] transcripts.json not found — run 03_asr.py first", file=sys.stderr)
        return

    rejects = load_rejects(src_id)
    transcripts = json.loads(transcript_path.read_text(encoding="utf-8"))
    transcripts = [e for e in transcripts if e["segment_id"].split("_seg_")[-1] not in rejects]
    out_dir = DATA_NORM / src_id
    out_dir.mkdir(parents=True, exist_ok=True)

    updated = []
    for entry in transcripts:
        seg_id = entry["segment_id"]
        src_wav = ROOT / entry["audio_path"]
        out_wav = out_dir / f"{seg_id}.wav"

        if out_wav.exists():
            entry["normalized_path"] = str(out_wav.relative_to(ROOT))
            updated.append(entry)
            continue

        print(f"  {seg_id} …", end=" ", flush=True)

        # Load, convert to mono 24kHz
        audio = AudioSegment.from_wav(str(src_wav))
        audio = audio.set_channels(1).set_frame_rate(TARGET_SR)

        # Trim silence
        audio = trim_silence(audio)

        if len(audio) < 1000:  # under 1 second after trimming — skip
            print("too short after trim, skipped")
            continue

        # Export to temp numpy array for LUFS normalization
        samples = np.array(audio.get_array_of_samples()).astype(np.float32)
        samples /= float(2 ** (audio.sample_width * 8 - 1))  # normalize to [-1, 1]

        samples = normalize_lufs(samples, TARGET_SR)

        # Clip and write
        samples = np.clip(samples, -1.0, 1.0)
        sf.write(str(out_wav), samples, TARGET_SR, subtype="PCM_16")

        entry["normalized_path"] = str(out_wav.relative_to(ROOT))
        updated.append(entry)
        print("ok")

    # Write updated transcripts with normalized_path field
    transcript_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{src_id}] Done — {len(updated)} normalized → {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Process a single source by id")
    args = parser.parse_args()

    config = load_config()
    sources = config["sources"]

    if args.id:
        sources = [s for s in sources if s["id"] == args.id]
        if not sources:
            sys.exit(f"No source with id '{args.id}' found in config.yaml")

    for source in sources:
        try:
            process_source(source)
        except Exception as e:
            print(f"[{source['id']}] ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
