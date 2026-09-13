"""检查 count 字段的真实值分布"""
import csv
from pathlib import Path
from collections import Counter

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}

def pos_match(pos_str):
    return any(p in pos_str for p in TARGET_POS)

count_vals = []
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        pm = pos_match(row.get('pos', ''))
        ec = not row.get('collocation', '').strip()
        if pm and ec:
            cv = row.get('count', '')
            count_vals.append(cv)

print(f"Total pos+empty_col: {len(count_vals)}")
# show distribution
counter = Counter(count_vals)
print("count field value samples (first 20 distinct):")
for v, n in sorted(counter.items(), key=lambda x: -x[1])[:20]:
    print(f"  repr={repr(v)}  occurrences={n}")
