"""
build_clean_master.py
Generate content_lemma_frequency_clean.csv + report from source.
Source file is NOT modified.
"""
import csv
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date

SRC      = Path(r"E:\codex\PDF解析\output\content_lemma_frequency.csv")
OUT_CSV  = Path(r"E:\codex\PDF解析\output\content_lemma_frequency_clean.csv")
OUT_RPT  = Path(r"E:\codex\PDF解析\output\content_lemma_frequency_clean_report.txt")

# ── Constants ─────────────────────────────────────────────────────────────

FILLER_NOISE = frozenset({"いー", "んー", "うー", "まー", "あー", "えー", "おー", "あっ"})

INTERJECTION_WHITELIST = frozenset({"はい", "いいえ"})

NORMALIZE_MAP = {
    "直ぐ": "すぐ",
    "旨い": "うまい",
    "筈":   "はず",
    "其々": "それぞれ",
    "未だ": "まだ",
    "余り": "あまり",
    "全て": "すべて",
}

EXAM_TERMS = frozenset({
    "問題", "注", "選ぶ", "答え", "ページ", "以上", "以下",
    "説明", "試験", "確認", "番号", "解答", "開始",
})

RE_KATAKANA_ONLY = re.compile(r'^[ァ-ヴーｦ-ﾟ]+$')
RE_KANA_ONLY     = re.compile(r'^[ぁ-んァ-ヴーｦ-ﾟ]+$')

NEW_FIELDS = [
    "display_word", "frequency_tier", "quality_status",
    "import_status", "content_status", "review_reason",
    "original_form", "normalized_reason",
]

# ── Helpers ───────────────────────────────────────────────────────────────

def to_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")

def safe_int(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0

def freq_tier(count: int) -> str:
    if count >= 20: return "tier_1"
    if count >= 10: return "tier_2"
    if count >= 5:  return "tier_3"
    if count >= 2:  return "low_frequency"
    return "archive"

# ── Read source (unchanged) ───────────────────────────────────────────────

with open(SRC, encoding="utf-8-sig", newline="") as f:
    reader       = csv.DictReader(f)
    src_fields   = list(reader.fieldnames)
    src_rows     = list(reader)

total_src = len(src_rows)
print(f"Read {total_src} rows from source")

# ── Pass 1: initial status computation ───────────────────────────────────

work: list[dict] = []

for row in src_rows:
    display_term = row["display_term"].strip()
    reading      = row["reading"].strip()
    pos_group    = row["pos_group"].strip()
    count        = safe_int(row["count"])

    is_noise     = to_bool(row.get("is_noise_candidate",            "False"))
    is_exam_flag = to_bool(row.get("is_exam_boilerplate_candidate", "False"))
    is_proper    = to_bool(row.get("is_proper_name_candidate",      "False"))
    is_measure   = to_bool(row.get("is_measure_or_suffix_candidate","False"))

    display_word      = NORMALIZE_MAP.get(display_term, display_term)
    original_form     = display_term
    normalized_reason = "common_kana_display" if display_word != display_term else ""

    quality_status = "ok"
    content_status = "normal"
    reasons: list[str] = []

    # ── Reject: filler noise (exact list)
    if display_term in FILLER_NOISE or display_word in FILLER_NOISE:
        quality_status = "reject"
        content_status = "not_suitable"
        reasons.append("filler_noise")

    # ── Reject: short interjection noise
    elif (pos_group == "感動詞"
          and bool(RE_KANA_ONLY.match(display_word))
          and len(display_word) <= 3
          and display_word not in INTERJECTION_WHITELIST):
        quality_status = "reject"
        content_status = "not_suitable"
        reasons.append("short_interjection_noise")

    else:
        # ── Review: source noise flag
        if is_noise:
            quality_status = "review"
            reasons.append("noise_candidate")

        # ── Review: exam boilerplate (source flag + explicit list)
        if is_exam_flag or display_term in EXAM_TERMS or display_word in EXAM_TERMS:
            quality_status = "review"
            content_status = "not_suitable"
            if "exam_term" not in reasons:
                reasons.append("exam_term")

        # ── Review: proper name
        if is_proper:
            quality_status = "review"
            content_status = "not_suitable"
            if "proper_name_review" not in reasons:
                reasons.append("proper_name_review")

        # ── Not suitable: measure / suffix
        if is_measure:
            content_status = "not_suitable"

        # ── Review: katakana long-vowel reading anomaly
        #    katakana word contains ー but reading omits ー entirely
        if (bool(RE_KATAKANA_ONLY.match(display_word))
                and "ー" in display_word
                and "ー" not in reading):
            if quality_status == "ok":
                quality_status = "review"
            if "katakana_reading_review" not in reasons:
                reasons.append("katakana_reading_review")

        # ── Frequency-based reason (informational, applies to hold/archive)
        if count == 1:
            reasons.append("archive_count_1")
        elif count <= 4:
            reasons.append("low_frequency")

    # content_status: upgrade to good_topic when warranted
    if (content_status == "normal"
            and freq_tier(count) in ("tier_1", "tier_2")
            and quality_status == "ok"
            and not is_measure):
        content_status = "good_topic"

    work.append({
        **row,
        "display_word":      display_word,
        "original_form":     original_form,
        "normalized_reason": normalized_reason,
        "frequency_tier":    freq_tier(count),
        "quality_status":    quality_status,
        "import_status":     "",          # filled in pass 3
        "content_status":    content_status,
        "review_reason":     " | ".join(reasons),
        "_count":            count,
    })

# ── Pass 2: duplicate detection (by display_word) ────────────────────────

dw_index: dict[str, list[int]] = defaultdict(list)
for i, r in enumerate(work):
    dw_index[r["display_word"]].append(i)

for dw, idxs in dw_index.items():
    if len(idxs) < 2:
        continue
    # Highest count is primary; others are duplicates
    sorted_idxs = sorted(idxs, key=lambda i: work[i]["_count"], reverse=True)
    for idx in sorted_idxs[1:]:
        r = work[idx]
        if r["quality_status"] == "ok":
            r["quality_status"] = "review"
        existing = r["review_reason"]
        r["review_reason"] = (existing + " | duplicate_word") if existing else "duplicate_word"

# ── Pass 3: import_status ─────────────────────────────────────────────────

for r in work:
    qs    = r["quality_status"]
    count = r["_count"]
    if qs == "reject":
        r["import_status"] = "skip"
    elif qs == "review":
        r["import_status"] = "hold"
    elif count >= 5:
        r["import_status"] = "ready"
    else:
        r["import_status"] = "hold"

# ── Write clean CSV ───────────────────────────────────────────────────────

out_fields = src_fields + NEW_FIELDS

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
    writer.writeheader()
    for r in work:
        writer.writerow(r)

print(f"CSV written → {OUT_CSV}  ({len(work)} rows)")

# ── Generate report ───────────────────────────────────────────────────────

tier_counts = Counter(r["frequency_tier"] for r in work)
qs_counts   = Counter(r["quality_status"] for r in work)
is_counts   = Counter(r["import_status"]  for r in work)
cs_counts   = Counter(r["content_status"] for r in work)

rejects    = [r for r in work if r["quality_status"] == "reject"]
reviews    = [r for r in work if r["quality_status"] == "review"]
duplicates = [r for r in work if "duplicate_word" in r["review_reason"]]
kata_rev   = [r for r in work if "katakana_reading_review" in r["review_reason"]]
normalized = [r for r in work if r["normalized_reason"] == "common_kana_display"]
ready      = [r for r in work if r["import_status"] == "ready"]
good_topic = [r for r in work if r["content_status"] == "good_topic"]

top50 = sorted(
    [r for r in work if r["import_status"] == "ready"],
    key=lambda r: -r["_count"]
)[:50]

lines: list[str] = []
W = 74

def sep(ch="="):    lines.append(ch * W)
def ln(s=""):       lines.append(s)

sep()
ln("JLPT N2 源词表清洗报告")
ln(f"源文件 : content_lemma_frequency.csv")
ln(f"输出   : content_lemma_frequency_clean.csv")
ln(f"生成   : {date.today()}")
sep()
ln()
ln(f"[1]  原始总行数           : {total_src}")
ln(f"[2]  clean 表总行数       : {len(work)}  （行数不变，新增状态字段）")
ln()
ln("[3]  frequency_tier 分布")
for t in ["tier_1", "tier_2", "tier_3", "low_frequency", "archive"]:
    ln(f"     {t:<15}  {tier_counts.get(t, 0):>6}")
ln()
ln("[4]  quality_status 分布")
for k in ["ok", "review", "reject"]:
    ln(f"     {k:<10}  {qs_counts.get(k, 0):>6}")
ln()
ln("[5]  import_status 分布")
for k in ["ready", "hold", "skip"]:
    ln(f"     {k:<10}  {is_counts.get(k, 0):>6}")
ln()
ln("[6]  content_status 分布")
for k in ["good_topic", "normal", "not_suitable"]:
    ln(f"     {k:<15}  {cs_counts.get(k, 0):>6}")
ln()
ln(f"[12] import_status=ready 总数   : {len(ready)}")
ln(f"[13] content_status=good_topic  : {len(good_topic)}")
ln()

sep("-")
ln("[7]  reject 词列表（前100）")
sep("-")
for r in rejects[:100]:
    ln(f"  {r['display_word']:<18}  count={r['_count']:<5}  {r['review_reason']}")
ln()

sep("-")
ln("[8]  review 词列表（前100，按 count 降序）")
sep("-")
for r in sorted(reviews, key=lambda x: -x["_count"])[:100]:
    ln(f"  {r['display_word']:<18}  count={r['_count']:<5}  {r['review_reason']}")
ln()

sep("-")
ln("[9]  duplicate_word 列表（前100）")
sep("-")
for r in sorted(duplicates, key=lambda x: -x["_count"])[:100]:
    ln(f"  {r['display_word']:<18}  count={r['_count']:<5}  {r['review_reason']}")
ln()

sep("-")
ln("[10] katakana_reading_review 列表（前100）")
sep("-")
for r in sorted(kata_rev, key=lambda x: -x["_count"])[:100]:
    ln(f"  {r['display_word']:<18}  reading={r['reading']:<20}  count={r['_count']}")
ln()

sep("-")
ln("[11] common_kana_display 规范化列表（全部）")
sep("-")
for r in sorted(normalized, key=lambda x: -x["_count"]):
    ln(f"  {r['original_form']:<12}  ->  {r['display_word']:<12}  count={r['_count']}")
ln()

sep("-")
ln("[14] Top500 clean 候选前50（import_status=ready，按 count 排序）")
sep("-")
ln(f"  {'display_word':<18}  {'reading':<18}  {'pos_group':<10}  {'count':>6}  tier")
ln("  " + "-" * 66)
for r in top50:
    ln(f"  {r['display_word']:<18}  {r['reading']:<18}  {r['pos_group']:<10}  {r['_count']:>6}  {r['frequency_tier']}")
ln()

OUT_RPT.write_text("\n".join(lines), encoding="utf-8")
print(f"Report written → {OUT_RPT}")
print(f"  ready={len(ready)}  good_topic={len(good_topic)}  "
      f"reject={len(rejects)}  review={len(reviews)}  "
      f"duplicates={len(duplicates)}  normalized={len(normalized)}")
