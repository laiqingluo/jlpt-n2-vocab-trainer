import csv
from pathlib import Path

SRC = Path(__file__).parent.parent / "data" / "n2_vocab.csv"
DST = Path(__file__).parent.parent / "data" / "memory_hints_todo.csv"
FIELDS = ["word", "reading", "pos", "meaning", "collocation", "quadrant", "count"]

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        q = row.get("quadrant", "").strip()
        try:
            cnt = int(row.get("count", 0) or 0)
        except Exception:
            cnt = 0
        if q in ("黄金词", "隐藏考点") and cnt >= 20:
            rows.append({k: row[k] for k in FIELDS})

rows.sort(key=lambda x: -int(x["count"]))

with open(DST, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print(len(rows))
