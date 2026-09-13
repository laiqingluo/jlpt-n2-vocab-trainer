"""把16个词写到文件"""
import csv, json
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"
OUT = Path(__file__).parent.parent / "data" / "_debug_16words.json"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}

results = []
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        try:
            cnt = int(row.get('count', 0) or 0)
        except Exception:
            cnt = 0
        pm = any(p in row.get('pos', '') for p in TARGET_POS)
        ec = not row.get('collocation', '').strip()
        if pm and ec and cnt >= 10:
            results.append({
                'word': row['word'],
                'reading': row['reading'],
                'pos': row['pos'],
                'count': cnt,
                'meaning': row['meaning'],
            })

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Written {len(results)} entries to {OUT}")
