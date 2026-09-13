"""比对源文件(7088) vs 词表(6007)，找出差异原因"""
import csv, json
from pathlib import Path

SRC = Path(r"E:\codex\PDF解析\output\content_lemma_import_cards.csv")
DST = Path(__file__).parent.parent / "data" / "n2_vocab.csv"
OUT = Path(__file__).parent.parent / "data" / "_diff_report.json"

src_rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    src_rows = list(csv.DictReader(f))

dst_words = set()
with open(DST, encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        w = row.get("word", "").strip()
        if w:
            dst_words.add(w)

SOURCE_FIELDS = ["word","reading","part_of_speech","frequency",
                 "first_seen_pdf","first_seen_page","example","lemma","tags"]

conflicts      = []  # 源词已在词表里
empty_fields   = []  # 有空字段
non_numeric    = []  # frequency 非数字
dup_in_src     = []  # 源文件内重复
not_imported   = []  # 上述都不是，但没被导入（[:100]截断）

seen_src = set()
for i, row in enumerate(src_rows, start=2):
    word = row.get("word", "").strip()
    missing = [f for f in SOURCE_FIELDS if not row.get(f, "").strip()]
    freq = row.get("frequency", "").strip()

    if missing:
        empty_fields.append({"row": i, "word": word, "missing": missing})
        continue
    if not freq.isdigit():
        non_numeric.append({"row": i, "word": word, "frequency": freq})
        continue
    if word in dst_words:
        conflicts.append(word)
        continue
    if word in seen_src:
        dup_in_src.append({"row": i, "word": word})
        continue
    seen_src.add(word)
    not_imported.append({"row": i, "word": word, "frequency": int(freq)})

not_imported.sort(key=lambda x: -x["frequency"])

report = {
    "source_total": len(src_rows),
    "vocab_total": len(dst_words),
    "already_in_vocab_conflicts": len(conflicts),
    "skipped_empty_fields": len(empty_fields),
    "skipped_non_numeric_freq": len(non_numeric),
    "skipped_dup_in_source": len(dup_in_src),
    "not_imported_remaining": len(not_imported),
    "not_imported_top30": not_imported[:30],
    "empty_field_samples": empty_fields[:5],
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"Written to {OUT}")
