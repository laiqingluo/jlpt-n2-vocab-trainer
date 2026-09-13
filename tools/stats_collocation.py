import csv, json
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}
EXCLUDE_POS = {'感動詞', '接続詞', '連体詞', '接頭詞', '接尾詞'}

def pos_match(pos_str):
    if pos_str in EXCLUDE_POS:
        return False
    return any(p in pos_str for p in TARGET_POS)

total = has_col = no_col = 0
missing_ge10 = []

with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        if not pos_match(row.get('pos', '')):
            continue
        total += 1
        col = row.get('collocation', '').strip()
        if col:
            has_col += 1
        else:
            no_col += 1
            try:
                cnt = int(row.get('count', 0) or 0)
            except Exception:
                cnt = 0
            if cnt >= 10:
                missing_ge10.append({
                    'word': row['word'],
                    'reading': row['reading'],
                    'pos': row['pos'],
                    'count': cnt,
                    'meaning': row['meaning'],
                })

missing_ge10.sort(key=lambda x: -x['count'])

out = Path(__file__).parent.parent / "data" / "_stats_collocation.json"
with open(out, 'w', encoding='utf-8') as f:
    json.dump({
        'total': total,
        'has_collocation': has_col,
        'no_collocation': no_col,
        'missing_ge10_count': len(missing_ge10),
        'missing_ge10': missing_ge10,
    }, f, ensure_ascii=False, indent=2)

print(f"Written to {out}")
