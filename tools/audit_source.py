"""全面审计 PDF 解析原始数据质量"""
import csv, json, re
from pathlib import Path
from collections import Counter, defaultdict

SRC = Path(r"E:\codex\PDF解析\output\content_lemma_import_cards.csv")
OUT = Path(__file__).parent.parent / "data" / "_audit_source.json"

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

# ── 1. 词性分布 ───────────────────────────────────────────
pos_counter = Counter(r["part_of_speech"].strip() for r in rows)

# ── 2. 频率分布 ───────────────────────────────────────────
freq_dist = Counter()
for r in rows:
    try:
        f = int(r["frequency"])
        if f >= 100: bucket = ">=100"
        elif f >= 50: bucket = "50-99"
        elif f >= 20: bucket = "20-49"
        elif f >= 10: bucket = "10-19"
        elif f >= 5:  bucket = "5-9"
        elif f >= 2:  bucket = "2-4"
        else:         bucket = "1"
    except: bucket = "非数字"
    freq_dist[bucket] += 1

# ── 3. 噪音词检测 ──────────────────────────────────────────
noise = []
for r in rows:
    w = r["word"].strip()
    reasons = []
    # 纯假名拟声/语气（2字以内且含长音符）
    if re.fullmatch(r'[ぁ-ヿーっ]{1,3}', w) and (len(w) <= 3):
        reasons.append("疑似语气词/短假名")
    # 含非日文字符（数字/符号/字母）
    if re.search(r'[A-Za-z0-9①-⑳㎡㎞％℃]', w):
        reasons.append("含字母数字符号")
    # 汉字异体字（旧字体用Unicode私用区或非常用汉字）
    if re.search(r'[龥-￿]', w):
        reasons.append("含生僻/异体汉字")
    # 极短词（1字且非汉字）
    if len(w) == 1 and not re.match(r'[一-鿿]', w):
        reasons.append("单假名字符")
    if reasons:
        noise.append({"word": w, "freq": r["frequency"], "pos": r["part_of_speech"], "reasons": reasons})

# ── 4. 重复词 ──────────────────────────────────────────────
word_rows = defaultdict(list)
for i, r in enumerate(rows):
    word_rows[r["word"].strip()].append({"row": i+2, "freq": r["frequency"]})
duplicates = {w: v for w, v in word_rows.items() if len(v) > 1}

# ── 5. 异体字/同形词（和现代常用形对比）──────────────────────
# 常见异体字对照表（旧字体→现代标准形）
variant_map = {
    "直ぐ": "すぐ", "未だ": "まだ", "余り": "あまり", "全て": "すべて",
    "其々": "それぞれ", "筈": "はず", "旨い": "うまい", "早い": "はやい",
    "暫く": "しばらく", "漸く": "ようやく", "況して": "まして",
    "拘る": "こだわる", "謂わば": "いわば", "些か": "いささか",
    "頗る": "すこぶる", "屡": "しばしば", "亦": "また",
}
variant_found = []
for r in rows:
    w = r["word"].strip()
    if w in variant_map:
        variant_found.append({"old": w, "modern": variant_map[w], "freq": r["frequency"]})

# ── 6. frequency 非数字 ────────────────────────────────────
non_numeric = [{"word": r["word"], "freq": r["frequency"]}
               for r in rows if not r["frequency"].strip().isdigit()]

# ── 7. 空字段 ─────────────────────────────────────────────
empty_word = [r for r in rows if not r["word"].strip()]

report = {
    "total": len(rows),
    "pos_distribution": dict(pos_counter.most_common()),
    "frequency_distribution": dict(freq_dist),
    "noise_count": len(noise),
    "noise_samples": noise[:40],
    "duplicate_count": len(duplicates),
    "duplicates": dict(list(duplicates.items())[:20]),
    "variant_count": len(variant_found),
    "variants": variant_found,
    "non_numeric_freq_count": len(non_numeric),
    "non_numeric_samples": non_numeric[:10],
    "empty_word_count": len(empty_word),
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"Written to {OUT}")
