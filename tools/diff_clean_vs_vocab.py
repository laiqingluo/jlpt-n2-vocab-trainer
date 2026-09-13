"""
diff_clean_vs_vocab.py
Compare content_lemma_frequency_clean.csv  vs  n2_vocab.csv
Print a breakdown without modifying either file.
"""
import csv
from pathlib import Path
from collections import Counter

CLEAN = Path(r"E:\codex\PDF解析\output\content_lemma_frequency_clean.csv")
VOCAB = Path(r"E:\codex\jlpt背单词\data\n2_vocab.csv")

# ── Load clean table ──────────────────────────────────────────────────────

clean_rows = []
with open(CLEAN, encoding="utf-8-sig", newline="") as f:
    clean_rows = list(csv.DictReader(f))

# Build lookup: display_word → row  AND  original_form → row
clean_by_display  = {r["display_word"].strip(): r  for r in clean_rows}
clean_by_original = {r["original_form"].strip(): r  for r in clean_rows
                     if r["original_form"].strip() != r["display_word"].strip()}

def find_in_clean(word: str):
    return clean_by_display.get(word) or clean_by_original.get(word)

# ── Load vocab table ──────────────────────────────────────────────────────

vocab_rows = []
with open(VOCAB, encoding="utf-8-sig", newline="") as f:
    vocab_rows = list(csv.DictReader(f))

vocab_words = {r["word"].strip() for r in vocab_rows}

# ── Diff: clean → vocab ───────────────────────────────────────────────────

# For each tier in clean, how many are already in vocab vs missing
tiers = ["tier_1", "tier_2", "tier_3", "low_frequency", "archive"]

in_vocab   = []   # clean rows whose display_word is in vocab
not_in_vocab = [] # clean rows NOT in vocab

for r in clean_rows:
    dw = r["display_word"].strip()
    of = r["original_form"].strip()
    if dw in vocab_words or of in vocab_words:
        in_vocab.append(r)
    else:
        not_in_vocab.append(r)

# Break down not_in_vocab by tier + import_status
missing_by_tier   = Counter(r["frequency_tier"]  for r in not_in_vocab)
missing_by_status = Counter(r["import_status"]   for r in not_in_vocab)
missing_by_qs     = Counter(r["quality_status"]  for r in not_in_vocab)

# ready words missing from vocab
missing_ready = [r for r in not_in_vocab if r["import_status"] == "ready"]
missing_ready_t1 = [r for r in missing_ready if r["frequency_tier"] == "tier_1"]
missing_ready_t2 = [r for r in missing_ready if r["frequency_tier"] == "tier_2"]
missing_ready_t3 = [r for r in missing_ready if r["frequency_tier"] == "tier_3"]

# ── Diff: vocab → clean (orphan words) ───────────────────────────────────

orphan_vocab = []  # in vocab but not traceable to clean source
for r in vocab_rows:
    w = r["word"].strip()
    if find_in_clean(w) is None:
        orphan_vocab.append(r)

# ── Print report ──────────────────────────────────────────────────────────

W = 68
SEP = "=" * W
sep2 = "-" * W

print(SEP)
print("Diff: content_lemma_frequency_clean  vs  n2_vocab")
print(SEP)
print()
print(f"  clean 表总行数          : {len(clean_rows)}")
print(f"  n2_vocab 总行数         : {len(vocab_rows)}")
print()
print(sep2)
print("  clean → vocab 匹配情况")
print(sep2)
print(f"  已在 vocab 中           : {len(in_vocab)}")
print(f"  不在 vocab（缺失）       : {len(not_in_vocab)}")
print()
print("  缺失词按 frequency_tier 细分：")
for t in tiers:
    n = missing_by_tier.get(t, 0)
    print(f"    {t:<15}  {n:>5}")
print()
print("  缺失词按 import_status 细分：")
for k in ["ready", "hold", "skip"]:
    n = missing_by_status.get(k, 0)
    print(f"    {k:<10}  {n:>5}")
print()
print("  缺失词按 quality_status 细分：")
for k in ["ok", "review", "reject"]:
    n = missing_by_qs.get(k, 0)
    print(f"    {k:<10}  {n:>5}")
print()
print(sep2)
print("  import_status=ready 缺失词细分（最值得补充的部分）")
print(sep2)
print(f"  ready 合计              : {len(missing_ready)}")
print(f"    tier_1 (count≥20)     : {len(missing_ready_t1)}")
print(f"    tier_2 (count 10-19)  : {len(missing_ready_t2)}")
print(f"    tier_3 (count 5-9)    : {len(missing_ready_t3)}")
print()
print("  tier_1 缺失 ready 词（前30，按 count 降序）：")
for r in sorted(missing_ready_t1, key=lambda x: -int(x["count"]))[:30]:
    print(f"    {r['display_word']:<18} {r['reading']:<16} count={r['count']:<5} {r['pos_group']}")
print()
print("  tier_2 缺失 ready 词（前20）：")
for r in sorted(missing_ready_t2, key=lambda x: -int(x["count"]))[:20]:
    print(f"    {r['display_word']:<18} {r['reading']:<16} count={r['count']:<5} {r['pos_group']}")
print()
print(sep2)
print(f"  vocab → clean 孤儿词（在 vocab 但追溯不到 clean 源）")
print(sep2)
print(f"  孤儿词数量              : {len(orphan_vocab)}")
if orphan_vocab:
    print("  前20个样本：")
    for r in orphan_vocab[:20]:
        src = r.get("source", "")
        qs  = r.get("quadrant", "")
        print(f"    {r['word']:<18} {r.get('reading',''):<14} {src:<20} {qs}")
print()
print(SEP)
