"""细看各频率段的词，判断噪音边界"""
import csv, json, re
from pathlib import Path
from collections import defaultdict

SRC = Path(r"E:\codex\PDF解析\output\content_lemma_import_cards.csv")
OUT = Path(__file__).parent.parent / "data" / "_audit_detail.json"

rows = []
with open(SRC, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

def freq(r):
    try: return int(r["frequency"])
    except: return 0

# ── 各频率段抽样（取前30个）────────────────────────────────
def sample_band(rows, lo, hi, n=40):
    band = [r for r in rows if lo <= freq(r) < hi]
    band.sort(key=freq, reverse=True)
    return [{"word": r["word"], "reading": r["reading"],
             "pos": r["part_of_speech"], "freq": freq(r)} for r in band[:n]]

# ── 感動詞全部列出 ────────────────────────────────────────
kandoushi = sorted(
    [{"word": r["word"], "reading": r["reading"], "freq": freq(r)}
     for r in rows if r["part_of_speech"].strip() == "感动词"],
    key=lambda x: -x["freq"]
)

# ── 接続詞・連体詞・代名詞 全部列出 ───────────────────────
other_pos = {}
for pos in ["接续词", "连体词", "代名词"]:
    other_pos[pos] = sorted(
        [{"word": r["word"], "reading": r["reading"], "freq": freq(r)}
         for r in rows if r["part_of_speech"].strip() == pos],
        key=lambda x: -x["freq"]
    )

# ── 异体字：检查现代形是否也在数据集里 ──────────────────────
variant_map = {
    "直ぐ": "すぐ", "未だ": "まだ", "余り": "あまり", "全て": "すべて",
    "其々": "それぞれ", "筈": "はず", "旨い": "うまい", "早い": "はやい",
    "暫く": "しばらく", "漸く": "ようやく", "頗る": "すこぶる",
    "然も": "しかも", "可成": "かなり", "幾ら": "いくら",
    "色々": "いろいろ", "沢山": "たくさん", "一方": "いっぽう",
    "大変": "たいへん", "更に": "さらに", "当然": "とうぜん",
}
all_words = {r["word"].strip(): freq(r) for r in rows}
variant_check = []
for old, modern in variant_map.items():
    old_freq = all_words.get(old)
    modern_freq = all_words.get(modern)
    if old_freq is not None:
        variant_check.append({
            "old_form": old, "old_freq": old_freq,
            "modern_form": modern, "modern_freq": modern_freq,
            "both_exist": modern_freq is not None,
        })

# ── count=1 的词按词性细分 ────────────────────────────────
count1_by_pos = defaultdict(list)
for r in rows:
    if freq(r) == 1:
        count1_by_pos[r["part_of_speech"].strip()].append(r["word"])

count1_summary = {
    pos: {"count": len(words), "samples": words[:15]}
    for pos, words in sorted(count1_by_pos.items(), key=lambda x: -len(x[1]))
}

# ── count 2-4 动词副词形状词（可能有价值的低频词）──────────
low_freq_valuable = [
    {"word": r["word"], "reading": r["reading"], "pos": r["part_of_speech"], "freq": freq(r)}
    for r in rows
    if 2 <= freq(r) <= 4
    and r["part_of_speech"].strip() in ("动词", "副词", "形状词", "形容词")
]
low_freq_valuable.sort(key=lambda x: -x["freq"])

result = {
    "band_freq1": sample_band(rows, 1, 2, 40),
    "band_freq2_4": sample_band(rows, 2, 5, 40),
    "band_freq5_9": sample_band(rows, 5, 10, 30),
    "kandoushi_all": kandoushi,
    "other_pos": other_pos,
    "variant_check": variant_check,
    "count1_by_pos_summary": count1_summary,
    "low_freq_valuable_verbs_adv": low_freq_valuable[:50],
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Written to {OUT}")
