"""
Stage 5 — Emotion tagging via Sarvam LLM.

Sends each transcript to Sarvam's chat completions API for a first-pass
emotion label. Results are written back into transcripts.json.

Review and correct tags manually after running — LLM text-only inference
is unreliable; spot-listen and fix obvious wrong labels.

Usage:
    python scripts/05_tag_emotion.py
    python scripts/05_tag_emotion.py --id sp01_hi_01
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
SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_prompt(transcript: str, taxonomy: list[str]) -> str:
    labels = ", ".join(taxonomy)
    return (
        f"Classify the emotion/speaking style of this speech transcript.\n"
        f"Choose exactly one label from: {labels}\n"
        f"Reply with only the label, nothing else.\n\n"
        f"Transcript: {transcript}"
    )


def get_emotion(transcript: str, taxonomy: list[str], api_key: str) -> str | None:
    if not transcript.strip():
        return "neutral"

    payload = {
        "model": "sarvam-30b",
        "messages": [
            {
                "role": "system",
                "content": "You are a speech emotion classifier. Reply with exactly one emotion label.",
            },
            {"role": "user", "content": build_prompt(transcript, taxonomy)},
        ],
        "max_tokens": 2048,
        "temperature": 0,
    }

    resp = requests.post(
        SARVAM_CHAT_URL,
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code == 429:
        print("    Rate limited — waiting 10s …")
        time.sleep(10)
        return get_emotion(transcript, taxonomy, api_key)

    if resp.status_code != 200:
        print(f"    LLM error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return None

    msg = resp.json()["choices"][0]["message"]
    content = msg.get("content") or msg.get("reasoning_content") or ""
    content = content.strip().lower()

    # Map response to nearest valid label
    for label in taxonomy:
        if label in content:
            return label

    return "neutral"  # fallback if response doesn't match any label


def process_source(source: dict, taxonomy: list[str], api_key: str) -> None:
    src_id = source["id"]
    transcript_path = DATA_SEG / src_id / "transcripts.json"

    if not transcript_path.exists():
        print(f"[{src_id}] transcripts.json not found — run 03_asr.py first", file=sys.stderr)
        return

    transcripts = json.loads(transcript_path.read_text(encoding="utf-8"))
    already_tagged = sum(1 for t in transcripts if t.get("emotion"))
    to_tag = [t for t in transcripts if not t.get("emotion")]

    print(f"[{src_id}] {len(transcripts)} transcripts | {already_tagged} already tagged | {len(to_tag)} to tag")

    for i, entry in enumerate(to_tag, 1):
        print(f"  [{i}/{len(to_tag)}] {entry['segment_id']} …", end=" ", flush=True)
        emotion = get_emotion(entry["transcript"], taxonomy, api_key)
        if emotion:
            entry["emotion"] = emotion
            print(emotion)
        else:
            entry["emotion"] = "neutral"
            print("fallback → neutral")
        time.sleep(0.2)

    transcript_path.write_text(json.dumps(transcripts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{src_id}] Done — emotions written to {transcript_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="Process a single source by id")
    args = parser.parse_args()

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        sys.exit("SARVAM_API_KEY not set.")

    config = load_config()
    taxonomy = config["emotion_taxonomy"]
    sources = config["sources"]

    if args.id:
        sources = [s for s in sources if s["id"] == args.id]
        if not sources:
            sys.exit(f"No source with id '{args.id}' found in config.yaml")

    for source in sources:
        try:
            process_source(source, taxonomy, api_key)
        except Exception as e:
            print(f"[{source['id']}] ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
