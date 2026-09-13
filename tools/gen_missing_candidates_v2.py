"""
gen_missing_candidates_v2.py
Refine import decisions from vocab_missing_ready_candidates.csv (v1).
- Adds skip_proper_name
- Splits skip_basic → skip_basic_function_word + basic_review
No source files are modified.
"""
import csv
from pathlib import Path
from collections import Counter

SRC_V1  = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates.csv")
OUT_CSV = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates_v2.csv")
OUT_RPT = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates_v2_report.txt")

# ── Constants ─────────────────────────────────────────────────────────────

FILLER_NOISE = frozenset({
    "いー", "んー", "うー", "まー", "あー", "えー", "おー", "あっ",
})

PROPER_NAME_LIST = frozenset({
    "ヤマダ", "モリ", "カゲヤマ", "アサダ", "イケダ", "サトウ",
    "ナカムラ", "ヤマカワ", "ヤマモト", "エンリケ",
})

EXAM_TERMS = frozenset({
    "問題", "注", "選ぶ", "答え", "ページ", "以上", "以下",
    "説明", "試験", "確認", "番号", "解答", "開始",
})

# Strict list: only obvious grammar/function words that carry no study value
BASIC_FUNCTION_WORDS = frozenset({
    "する", "いる", "なる", "いい", "もの", "ない", "こと", "ある",
    "人", "一", "この", "その", "それ", "これ", "行く", "来る", "思う",
    "ため", "中", "前", "後", "ところ", "どう", "そう", "こう", "もう",
    "どの", "何",
})

# Priority order for sorting the output
DECISION_ORDER = {
    "import_candidate_high":      0,
    "import_candidate_normal":    1,
    "basic_review":               2,
    "review":                     3,
    "skip_proper_name":           4,
    "skip_basic_function_word":   5,
    "skip_exam_term":             6,
    "skip_noise":                 7,
}

# ── Helper ────────────────────────────────────────────────────────────────

def safe_int(s):
    try: return int(str(s).strip())
    except: return 0

def decide_v2(row: dict) -> tuple[str, str]:
    """Return (import_decision, decision_reason) in priority order."""
    dw            = row["display_word"].strip()
    tier          = row["frequency_tier"].strip()
    layer         = row.get("learning_layer", "").strip()
    review_reason = row.get("review_reason", "").strip()
    v1_decision   = row.get("import_decision", "").strip()

    # 1. Filler noise
    if dw in FILLER_NOISE:
        return "skip_noise", "filler_noise"

    # 2. Proper name
    if (dw in PROPER_NAME_LIST
            or "proper_name" in layer.lower()
            or "proper_name" in review_reason.lower()):
        return "skip_proper_name", "proper_name_candidate"

    # 3. Exam / boilerplate
    if (dw in EXAM_TERMS
            or layer == "exam_boilerplate"
            or "exam_term" in review_reason):
        return "skip_exam_term", "exam_boilerplate_term"

    # 4. Basic function word (strict list only)
    if dw in BASIC_FUNCTION_WORDS:
        return "skip_basic_function_word", "basic_function_word"

    # 5. Was skip_basic in v1 but NOT a function word → needs human review
    if v1_decision == "skip_basic":
        return "basic_review", "basic_flag_but_content_word"

    # 6. Import candidates
    if tier in ("tier_1", "tier_2"):
        return "import_candidate_high", "count≥10_not_in_vocab"
    if tier == "tier_3":
        return "import_candidate_normal", "count5-9_not_in_vocab"

    return "review", "needs_manual_check"

# ── Load v1 ───────────────────────────────────────────────────────────────

with open(SRC_V1, encoding="utf-8-sig", newline="") as f:
    reader   = csv.DictReader(f)
    v1_fields = list(reader.fieldnames)
    v1_rows   = list(reader)

# ── Apply new decisions ───────────────────────────────────────────────────

for row in v1_rows:
    row["import_decision"], row["decision_reason"] = decide_v2(row)

# ── Sort ──────────────────────────────────────────────────────────────────

v1_rows.sort(key=lambda r: (
    DECISION_ORDER.get(r["import_decision"], 9),
    -safe_int(r["count"])
))

# Re-number rank
for i, row in enumerate(v1_rows, 1):
    row["rank"] = i

# ── Write CSV ─────────────────────────────────────────────────────────────

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=v1_fields, extrasaction="ignore")
    writer.writeheader()
    for row in v1_rows:
        writer.writerow(row)

# ── Counts ────────────────────────────────────────────────────────────────

dec = Counter(r["import_decision"] for r in v1_rows)

high      = [r for r in v1_rows if r["import_decision"] == "import_candidate_high"]
normal    = [r for r in v1_rows if r["import_decision"] == "import_candidate_normal"]
br        = [r for r in v1_rows if r["import_decision"] == "basic_review"]
rev       = [r for r in v1_rows if r["import_decision"] == "review"]
s_proper  = [r for r in v1_rows if r["import_decision"] == "skip_proper_name"]
s_noise   = [r for r in v1_rows if r["import_decision"] == "skip_noise"]
s_exam    = [r for r in v1_rows if r["import_decision"] == "skip_exam_term"]
s_func    = [r for r in v1_rows if r["import_decision"] == "skip_basic_function_word"]

# ── Report ────────────────────────────────────────────────────────────────

W   = 72
SEP = "=" * W
s2  = "-" * W
lines: list[str] = []
ln = lines.append

ln(SEP)
ln("缺失 ready 词补充候选表 v2  vocab_missing_ready_candidates_v2.csv")
ln("生成日期：2026-05-13")
ln(SEP)
ln("")
ln(f"[1]  总候选数                    : {len(v1_rows)}")
ln("")
ln(f"[2]  import_candidate_high       : {dec.get('import_candidate_high',0)}")
ln(f"[3]  import_candidate_normal     : {dec.get('import_candidate_normal',0)}")
ln(f"[4]  skip_proper_name            : {dec.get('skip_proper_name',0)}")
ln(f"[5]  skip_noise                  : {dec.get('skip_noise',0)}")
ln(f"[6]  skip_exam_term              : {dec.get('skip_exam_term',0)}")
ln(f"[7]  skip_basic_function_word    : {dec.get('skip_basic_function_word',0)}")
ln(f"[8]  basic_review                : {dec.get('basic_review',0)}")
ln(f"[9]  review                      : {dec.get('review',0)}")
ln("")

actionable = dec.get("import_candidate_high",0) + dec.get("import_candidate_normal",0)
after_basic_review = actionable + dec.get("basic_review",0)
ln(f"  → 可直接导入（high+normal）    : {actionable}")
ln(f"  → 加上 basic_review 上限       : {after_basic_review}")
ln("")

def section(num, title, rows, n=100):
    ln(s2)
    ln(f"[{num}] {title}（前{n}，按 count 降序）")
    ln(s2)
    if not rows:
        ln("  （无）")
        ln("")
        return
    for r in sorted(rows, key=lambda x: -safe_int(x["count"]))[:n]:
        ln(f"  {r['display_word']:<18} {r['reading']:<16} "
           f"count={r['count']:<5} {r['pos_group']:<10} "
           f"{r.get('decision_reason','')}")
    ln("")

section(10, "basic_review（需人工确认）",          br,       100)
section(11, "skip_proper_name",                   s_proper, 100)
section(12, "import_candidate_high（前100）",      high,     100)
section(13, "import_candidate_normal（前100）",    normal,   100)

OUT_RPT.write_text("\n".join(lines), encoding="utf-8")

print(f"CSV    → {OUT_CSV}  ({len(v1_rows)} rows)")
print(f"Report → {OUT_RPT}")
print(f"  high={len(high)}  normal={len(normal)}  basic_review={len(br)}  "
      f"skip_proper={len(s_proper)}  skip_func={len(s_func)}  "
      f"skip_exam={len(s_exam)}  skip_noise={len(s_noise)}  review={len(rev)}")
