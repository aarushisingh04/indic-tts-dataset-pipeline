# Indic TTS Dataset Pipeline

A pipeline for building a curated TTS training dataset from YouTube audio. Approximately 30 minutes of Hindi and 30 minutes of Indian English, sourced, transcribed, quality-checked, and published to HuggingFace.

**Dataset:** [27hues/indic-tts-en-hi-60min](https://huggingface.co/datasets/27hues/indic-tts-en-hi-60min)

---

## What's in the dataset

| Language | Speakers | Segments | Duration |
|---|---|---|---|
| Hindi (hi-IN) | 2 | 110 | 33.6 min |
| Indian English (en-IN) | 3 | 152 | 37.6 min |
| **Total** | **5** | **262** | **71.2 min** |

Started with 334 raw segments; 72 rejected (~21.6%), mostly all for sentence boundary cut-offs. No garbled audio or second-voice segments made it through.

## Pipeline

```
01_download.py   →  yt-dlp downloads, saves metadata.json per source
02_segment.py    →  silence-based chunking, 4–29s per segment
03_asr.py        →  Sarvam Saaras v3 STT transcription
04_normalize.py  →  24kHz mono, -23 LUFS, silence trimmed
05_tag_emotion.py →  Sarvam LLM (sarvam-30b) emotion tagging
06_push_to_hf.py →  builds and pushes HuggingFace dataset
```

All stages read from `config.yaml` and can run per-source with `--id`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys:
```
SARVAM_API_KEY=...
HF_TOKEN=...
HF_REPO=your-username/your-dataset-name
```

**ffmpeg** is required. On Windows via winget:
```
winget install ffmpeg
```
The download script auto-detects the winget install path if ffmpeg isn't in your PATH.

## Running the pipeline

```bash
python scripts/01_download.py
python scripts/02_segment.py
python scripts/03_asr.py
python scripts/04_normalize.py
python scripts/05_tag_emotion.py
python scripts/06_push_to_hf.py --dry-run   # preview
python scripts/06_push_to_hf.py             # push
```

## A few things learned along the way

**Segmentation boundary cuts were the biggest problem.** When silence-based chunking hits its max duration (29s), a naive hard cut lands mid-word. The fix: `soft_split()` scans back up to 8 seconds from the boundary to find the nearest quiet point before cutting. This eliminated almost all word-level clips; the remaining rejections were sentence-level context cuts which are a harder problem.

**Sarvam's sync STT API has a 30-second hard limit.** Should have checked the docs for this before. Initially set max segment duration to 60s and got 400 errors on longer chunks. Dropping max to 29s fixed it cleanly.

**ASR errors were mostly domain-specific.** On the English tech lecture source (Arpit Bhayani), Saaras v3 mis-transcribed SQL terminology like "age" written as "H", "row" as "rho". Hindi was cleaner overall, though English words spoken mid-Hindi sentence were sometimes transliterated inconsistently. All corrections are logged in `qc/stats.md`.

**Emotion distribution skews neutral/calm by design.** Motivational talks and tech lectures are mostly composed delivery, 54% neutral, 31% calm is accurate, not a tagging failure. The `sarvam-30b` model is a reasoning model that needs generous `max_tokens` (2048) to finish its chain-of-thought and output the label.

## QC artifacts

- `qc/listening_log.md` : per-source listening notes with sampled segment observations
- `qc/stats.md` : segment counts, rejection reasons, transcript corrections, emotion distribution
- `data/segments/*/reject.txt` : per-source rejection lists (4-digit segment numbers)

## Sources

All audio from YouTube under YouTube Standard License, used for research/educational purposes. Full attribution in the dataset card.
