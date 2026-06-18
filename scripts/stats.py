"""Quick stats across all segmented sources."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

totals = {}   # lang -> {min, count}

for f in sorted((ROOT / "data" / "segments").rglob("segments.json")):
    segs = json.loads(f.read_text(encoding="utf-8"))
    src_id = f.parent.name
    src_min = sum(s["duration_sec"] for s in segs) / 60
    print(f"  {src_id}: {len(segs)} segments, {src_min:.1f} min")
    for s in segs:
        lang = s["language"]
        if lang not in totals:
            totals[lang] = {"min": 0, "count": 0}
        totals[lang]["min"] += s["duration_sec"] / 60
        totals[lang]["count"] += 1

print()
for lang, t in sorted(totals.items()):
    print(f"TOTAL {lang}: {t['count']} segments, {t['min']:.1f} min")
