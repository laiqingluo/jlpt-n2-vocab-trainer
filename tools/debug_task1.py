"""调试任务一条件"""
import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}

COLLOCATIONS_SAMPLE = {
    '言う': '意見を言う / 名前を言う',
    '見る': 'テレビを見る / 夢を見る',
}

def pos_match(pos_str):
    for p in TARGET_POS:
        if p in pos_str:
            return True
    return False

matched_pos = matched_empty = matched_count = matched_all = 0
sample_rows = []

with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        try:
            cnt = int(row.get('count', 0) or 0)
        except Exception:
            cnt = 0
        pm  = pos_match(row.get('pos', ''))
        ec  = not row.get('collocation', '').strip()
        c10 = cnt >= 10
        if pm: matched_pos += 1
        if pm and ec: matched_empty += 1
        if pm and ec and c10:
            matched_count += 1
            if len(sample_rows) < 5:
                sample_rows.append((row['word'], row['pos'], row['count'], repr(row['collocation'])))

print(f"pos match:         {matched_pos}")
print(f"pos + empty col:   {matched_empty}")
print(f"pos + empty + >=10:{matched_count}")
print()
print("Sample rows:")
for w, p, c, col in sample_rows:
    in_dict = w in COLLOCATIONS_SAMPLE
    print(f"  word={repr(w)} pos={p} count={c} collocation={col} in_sample_dict={in_dict}")
