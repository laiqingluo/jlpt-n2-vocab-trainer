"""把 COLLOCATIONS 前20个键和 CSV 的16个词写到文件对比"""
import csv, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from task1_collocation import COLLOCATIONS

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"
OUT = Path(__file__).parent.parent / "data" / "_debug_keys.json"

TARGET_POS = {
    '動詞','他五','自五','他下一','自下一','他上一','自上一',
    '自·他五','自他五','名·他サ','名·自サ','名·自他サ',
    '副詞','副','形状詞','ナ形','名·ナ形'
}

csv_words = []
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        try:
            cnt = int(row.get('count', 0) or 0)
        except Exception:
            cnt = 0
        pm = any(p in row.get('pos', '') for p in TARGET_POS)
        ec = not row.get('collocation', '').strip()
        if pm and ec and cnt >= 10:
            w = row['word']
            csv_words.append({
                'word': w,
                'word_bytes': list(w.encode('utf-8')),
                'in_collocations': w in COLLOCATIONS,
            })

dict_sample = []
for k in list(COLLOCATIONS.keys())[:20]:
    dict_sample.append({'key': k, 'key_bytes': list(k.encode('utf-8'))})

result = {
    'csv_words': csv_words,
    'dict_sample': dict_sample,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Written to {OUT}")
