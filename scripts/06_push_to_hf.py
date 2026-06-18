"""
Stage 6 — Build and push the final dataset to HuggingFace.

Assembles all normalized, transcribed, and emotion-tagged segments into
a HuggingFace dataset and pushes it public.

Requires:
  - HF_TOKEN in .env (get from huggingface.co/settings/tokens)
  - HF_REPO in .env, e.g. "your-username/indic-tts-en-hi"

Usage:
    python scripts/06_push_to_hf.py --dry-run   # preview without pushing
    python scripts/06_push_to_hf.py             # build and push
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv(override=True)

ROOT = Path(__file__).resolve().parent.parent
DATA_SEG = ROOT / "data" / "segments"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all_transcripts(sources: list[dict]) -> list[dict]:
    rows = []
    source_map = {s["id"]: s for s in sources}

    for source in sources:
        src_id = source["id"]
        transcript_path = DATA_SEG / src_id / "transcripts.json"

        if not transcript_path.exists():
            print(f"  [{src_id}] no transcripts.json — skipping", file=sys.stderr)
            continue

        entries = json.loads(transcript_path.read_text(encoding="utf-8"))
        for entry in entries:
            norm_path = entry.get("normalized_path")
            if not norm_path:
                continue  # not normalized yet

            wav_abs = str(ROOT / norm_path)
            if not Path(wav_abs).exists():
                continue

            rows.append({
                "audio": wav_abs,
                "text": entry.get("transcript", "").strip(),
                "emotion": entry.get("emotion", "neutral"),
                "language": entry["language"],
                "speaker_id": entry["speaker_id"],
                "duration": entry["duration_sec"],
                "source_url": source_map[src_id]["url"],
                "license": source_map[src_id].get("license", "youtube-standard"),
                "credit": source_map[src_id].get("credit", ""),
            })

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print stats without pushing to HuggingFace")
    args = parser.parse_args()

    hf_token = os.getenv("HF_TOKEN")
    hf_repo = os.getenv("HF_REPO")

    if not args.dry_run:
        if not hf_token:
            sys.exit("HF_TOKEN not set in .env. Get one from huggingface.co/settings/tokens")
        if not hf_repo:
            sys.exit("HF_REPO not set in .env. Set it to e.g. 'your-username/indic-tts-en-hi'")

    config = load_config()
    rows = load_all_transcripts(config["sources"])

    if not rows:
        sys.exit("No rows found. Run 04_normalize.py first.")

    en_rows = [r for r in rows if r["language"] == "en-IN"]
    hi_rows = [r for r in rows if r["language"] == "hi-IN"]
    total_min = sum(r["duration"] for r in rows) / 60

    print(f"\nDataset summary:")
    print(f"  Total:   {len(rows)} segments, {total_min:.1f} min")
    print(f"  en-IN:   {len(en_rows)} segments, {sum(r['duration'] for r in en_rows)/60:.1f} min")
    print(f"  hi-IN:   {len(hi_rows)} segments, {sum(r['duration'] for r in hi_rows)/60:.1f} min")

    from collections import Counter
    emotion_dist = Counter(r["emotion"] for r in rows)
    print(f"  Emotions: {dict(emotion_dist)}")

    if args.dry_run:
        print("\nDry run — not pushing.")
        return

    # Build and push
    from datasets import Dataset, Audio
    from huggingface_hub import login

    login(token=hf_token)

    dataset = Dataset.from_list(rows).cast_column("audio", Audio(sampling_rate=24000))

    print(f"\nPushing to {hf_repo} …")
    dataset.push_to_hub(hf_repo, private=False)
    print(f"Done — https://huggingface.co/datasets/{hf_repo}")


if __name__ == "__main__":
    main()
