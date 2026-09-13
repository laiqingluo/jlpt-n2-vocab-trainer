"""列出 16 个待填充词"""
import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}

def pos_match(pos_str):
    return any(p in pos_str for p in TARGET_POS)

with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        try:
            cnt = int(row.get('count', 0) or 0)
        except Exception:
            cnt = 0
        if pos_match(row.get('pos','')) and not row.get('collocation','').strip() and cnt >= 10:
            print(f"word={row['word']}  reading={row['reading']}  pos={row['pos']}  count={cnt}  meaning={row['meaning']}")
