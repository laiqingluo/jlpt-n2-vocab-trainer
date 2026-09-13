"""验证任务一结果"""
import csv, json
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"
OUT = Path(__file__).parent.parent / "data" / "_verify_task1.json"

check_words = [
    "好き","とても","そんな","必ず","少し","立つ","学ぶ",
    "なくなる","やめる","かまう","取れる","歌える","きれい","決して",
]

results = []
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        if row['word'] in check_words:
            results.append({
                'word': row['word'],
                'pos': row['pos'],
                'count': row['count'],
                'collocation': row['collocation'],
            })

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Written {len(results)} rows")
