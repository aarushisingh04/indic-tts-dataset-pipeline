# Dataset QC Stats

---

## Segment Counts

| Source | Language | Raw Segments | Rejected | Final Kept |
|---|---|---|---|---|
| sp01_hi_01 (BK Shivani) | hi-IN | 66 | 8 | 58 |
| sp02_hi_02 (Sadhana) | hi-IN | 63 | 11 | 52 |
| sp03_en_01 (Arpit Bhayani) | en-IN | 120 | 31 | 89 |
| sp04_en_02 (Priyanka Chopra) | en-IN | 29 | 9 | 20 |
| sp05_en_03 (Sundar Pichai) | en-IN | 56 | 13 | 43 |
| **TOTAL hi-IN** | | **129** | **19** | **110** |
| **TOTAL en-IN** | | **205** | **53** | **152** |

---

## Duration (after QC)

| Language | Segments | Duration (min) |
|---|---|---|
| hi-IN | 110 | 33.6 |
| en-IN | 152 | 37.5 |
| **Total** | **262** | **71.1** |

---

## Transcript Corrections

### sp01_hi_01 (BK Shivani)
- Corrections made: 4
- Common errors: accurate transliteration of minor english words spoken in a majorly indian-hindi script.

### sp02_hi_02 (Sadhana)
- Corrections made: 0
- Common errors: N/A

### sp03_en_01 (Arpit Bhayani)
- Corrections made: 2
- Common errors: incorrect transcription of terminologies (SQL), ("age" written as "H" and "row" written as "rho")

### sp04_en_02 (Priyanka Chopra)
- Corrections made: 1
- Common errors: writing 2020 as "2000 and 20"

### sp05_en_03 (Sundar Pichai)
- Corrections made: 1
- Common errors: incorrect spelling of a proper noun (should be "Fairchild" not "Fachile")

---

## Emotion Distribution (after tagging)

| Emotion | Count | % |
|---|---|---|
| neutral | 142 | 54.2% |
| calm | 80 | 30.5% |
| sad | 11 | 4.2% |
| excited | 11 | 4.2% |
| formal | 6 | 2.3% |
| happy | 8 | 3.1% |
| angry | 4 | 1.5% |
| whisper | 0 | 0% |

---

## Rejection Reasons Summary

| Reason | Count |
|---|---|
| Sentence/context cut-off at boundary (start or end) | 72 |
| Empty or garbled transcript | 0 |
| Audience noise / second voice | 0 |
| Too short after trim | 0 |

All rejections were manual — segments where the audio cuts mid-sentence at a segmentation boundary, making them unsuitable for TTS training. Sources with continuous fast-paced speech (sp03_en_01, sp04_en_02) and minimal natural pauses had the highest rejection rates.

---

## Notes

- ASR model: Sarvam Saaras v3 (`saaras:v3`), mode: `transcribe`
- Emotion tagging model: `sarvam-30b` via Sarvam chat completions API
- Target format: 24kHz mono WAV, -23 LUFS
- Rejection rate: ~21.6% overall (72 rejected out of 334 raw segments)
- All rejections due to sentence boundary cut-offs; no audience noise or garbled audio found
- Emotion taxonomy: neutral, calm, happy, sad, excited, angry, formal, whisper
