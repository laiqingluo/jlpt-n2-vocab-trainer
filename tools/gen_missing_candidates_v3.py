"""
gen_missing_candidates_v3.py
Refine from vocab_missing_ready_candidates.csv (v1, the raw candidate list).
Changes vs v2:
  - Expanded proper_name list (covers katakana names missed in v2)
  - basic_review split: clear N4/N5 words → skip_basic_function_word
                        genuine N2/N3 content words → basic_review (~20 words)
No source files are modified.
"""
import csv
from pathlib import Path
from collections import Counter

SRC_V1  = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates.csv")
OUT_CSV = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates_v3.csv")
OUT_RPT = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates_v3_report.txt")
OUT_IMPORT_QUEUE = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_import_queue_v3.csv")
OUT_REVIEW_QUEUE = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_review_queue_v3.csv")

# ── Constants ─────────────────────────────────────────────────────────────

FILLER_NOISE = frozenset({
    "いー", "んー", "うー", "まー", "あー", "えー", "おー", "あっ",
})

# v2 explicit list + additional katakana person/place names
PROPER_NAME_LIST = frozenset({
    # v2 list
    "ヤマダ", "モリ", "カゲヤマ", "アサダ", "イケダ", "サトウ",
    "ナカムラ", "ヤマカワ", "ヤマモト", "エンリケ",
    # import_candidate_high
    "キムラ", "トウキョウ",
    # import_candidate_normal
    "ベルン", "サクラ", "フジ", "ミナミ", "モリシマ", "ヤマグチ",
    "アイ", "ウ", "オン", "ハン", "オサム", "ジミック", "スマン", "タダ",
})

# Explicit review list for katakana names/place names still seen in import queue.
# Do not generalize this to every katakana word: many loanwords are valid JLPT items.
KATAKANA_NAME_REVIEW_LIST = frozenset({
    "ヤマシタ", "スズキ", "リョウ", "キョウト", "ヒロシ", "アオキ", "ケン",
    "タカハシ", "ハヤシ", "ユウ", "ナカジマ", "ヒラヤマ", "アキラ", "マエダ",
    "シュウ", "タダタカ", "タケモト", "イシカワ", "ミラ", "モウリ", "ヨシトキ",
    "アオヤマ", "ウノ", "キタヤマ", "ナカイチ", "ニシヤマ", "ミト", "ミムラ",
})

KATAKANA_NOISE_REVIEW_LIST = frozenset({
    "ア", "イウ",
})

KATAKANA_FORM_REVIEW_LIST = frozenset({
    "ヌノ",
})

EXAM_TERMS = frozenset({
    "問題", "注", "選ぶ", "答え", "ページ", "以上", "以下",
    "説明", "試験", "確認", "番号", "解答", "開始",
})

# Original strict function-word list (v2)
BASIC_FUNC_STRICT = frozenset({
    "する", "いる", "なる", "いい", "もの", "ない", "こと", "ある",
    "人", "一", "この", "その", "それ", "これ", "行く", "来る", "思う",
    "ため", "中", "前", "後", "ところ", "どう", "そう", "こう", "もう",
    "どの", "何",
})

# N4/N5 words too basic for dedicated N2 study — added in v3
# Determined by looking at basic_review list word by word.
# Words kept in basic_review are left out of this set.
BASIC_SKIP_EXTRA = frozenset({
    # Pronouns / interrogatives
    "私", "此処", "其処", "何れ", "いつ", "何処", "どんな",
    # Basic conjunctions
    "しかし", "そして",
    # N5 verbs / auxiliary patterns
    "できる", "くる", "しまう", "もらう",
    "走る", "待つ", "忘れる", "止める", "見付ける", "始める",
    # N5/N4 nouns
    "とき", "方", "日", "月", "年", "今", "度", "他", "多く",
    "二", "家", "学校", "店", "地", "中略",
    # N4 adjectives / adverbs
    "早い", "良く", "初めて", "あまり", "少ない",
    # Other clearly basic
    "何故", "或る", "上げる", "通り",
})

# Union for quick lookup
ALL_BASIC_SKIP = BASIC_FUNC_STRICT | BASIC_SKIP_EXTRA

DECISION_ORDER = {
    "import_candidate_high":    0,
    "import_candidate_normal":  1,
    "basic_review":             2,
    "grammar_review":           3,
    "katakana_name_review":      4,
    "katakana_noise_review":     5,
    "katakana_form_review":      6,
    "proper_name_review":        7,
    "review":                   8,
    "skip_proper_name":         9,
    "skip_basic_function_word": 10,
    "skip_exam_term":           11,
    "skip_noise":               12,
}

# ── Manual decisions from 2026-05-13 basic_review pass ───────────────────

MANUAL_IMPORT_APPROVED = frozenset({
    "よる", "間", "付く", "うまい", "願う", "続ける", "それぞれ",
    "掛ける", "掛かる", "洗濯", "受ける", "割り引き", "所為",
    "叱る", "気付く", "挨拶", "致す", "申し込む", "侭", "際",
})

READING_OVERRIDES = {
    "うまい": "うまい",
    "願う": "ねがう",
    "続ける": "つづける",
    "掛ける": "かける",
    "受ける": "うける",
    "致す": "いたす",
}

GRAMMAR_REVIEW = {
    "於く": "において / おいて",
}

# ── Helper ────────────────────────────────────────────────────────────────

def safe_int(s):
    try: return int(str(s).strip())
    except: return 0

def decide_v3(row: dict) -> tuple[str, str]:
    dw            = row["display_word"].strip()
    tier          = row["frequency_tier"].strip()
    layer         = row.get("learning_layer", "").strip()
    review_reason = row.get("review_reason", "").strip()
    v1_decision   = row.get("import_decision", "").strip()
    pos_group     = row.get("pos_group", "").strip()

    # 0. Manual basic_review decisions
    if dw in GRAMMAR_REVIEW:
        return "grammar_review", f"manual_grammar_review:{GRAMMAR_REVIEW[dw]}"
    if dw in KATAKANA_NAME_REVIEW_LIST:
        return "katakana_name_review", "suspected_proper_name_or_place_name"
    if dw in KATAKANA_NOISE_REVIEW_LIST:
        return "katakana_noise_review", "suspected_ocr_or_tokenization_noise"
    if dw in KATAKANA_FORM_REVIEW_LIST:
        return "katakana_form_review", "abnormal_katakana_form_should_be_kanji_or_hiragana"
    if dw in MANUAL_IMPORT_APPROVED:
        if tier in ("tier_1", "tier_2"):
            return "import_candidate_high", "manual_basic_review_approved"
        if tier == "tier_3":
            return "import_candidate_normal", "manual_basic_review_approved"
        return "review", "manual_approved_but_low_frequency"

    # 1. Filler noise
    if dw in FILLER_NOISE:
        return "skip_noise", "filler_noise"

    # 2. Proper name (expanded list + source flags)
    if (dw in PROPER_NAME_LIST
            or "proper_name" in layer.lower()
            or "proper_name" in review_reason.lower()):
        return "skip_proper_name", "proper_name_candidate"

    # 3. Exam boilerplate
    if (dw in EXAM_TERMS
            or layer == "exam_boilerplate"
            or "exam_term" in review_reason):
        return "skip_exam_term", "exam_boilerplate_term"

    # 4. Basic function / too-basic word
    #    — strict list + extra N4/N5 words + pronoun POS
    if dw in ALL_BASIC_SKIP or pos_group == "代名词":
        return "skip_basic_function_word", "basic_function_word"

    # 5. Was marked skip_basic in v1 but didn't hit any skip rule above
    #    → genuine ambiguous content word, needs human check
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
    reader    = csv.DictReader(f)
    v1_fields = list(reader.fieldnames)
    v1_rows   = list(reader)

# ── Apply v3 decisions ────────────────────────────────────────────────────

for row in v1_rows:
    dw = row["display_word"].strip()
    if dw in READING_OVERRIDES:
        row["reading"] = READING_OVERRIDES[dw]
    row["import_decision"], row["decision_reason"] = decide_v3(row)
    if row["import_decision"] in (
        "grammar_review",
        "katakana_name_review",
        "katakana_noise_review",
        "katakana_form_review",
        "proper_name_review",
    ):
        row["import_status"] = "hold"
    row["display_term"] = row.get("display_word", "")
    row["pos"] = row.get("pos_group", "")
    row["source_layer"] = row.get("learning_layer", "")
    row["decision"] = row.get("import_decision", "")

# ── Sort ──────────────────────────────────────────────────────────────────

v1_rows.sort(key=lambda r: (
    DECISION_ORDER.get(r["import_decision"], 9),
    -safe_int(r["count"])
))
for i, row in enumerate(v1_rows, 1):
    row["rank"] = i

# ── Write CSV ─────────────────────────────────────────────────────────────

out_fields = list(v1_fields)
for field in ("display_term", "pos", "source_layer", "decision"):
    if field not in out_fields:
        out_fields.append(field)

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
    writer.writeheader()
    for row in v1_rows:
        writer.writerow(row)

import_queue = [
    r for r in v1_rows
    if r["import_decision"] in ("import_candidate_high", "import_candidate_normal")
]
review_queue = [
    r for r in v1_rows
    if r["import_decision"] in (
        "basic_review",
        "grammar_review",
        "katakana_name_review",
        "katakana_noise_review",
        "katakana_form_review",
        "proper_name_review",
        "review",
    )
]

with open(OUT_IMPORT_QUEUE, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(import_queue)

with open(OUT_REVIEW_QUEUE, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(review_queue)

# ── Counts ────────────────────────────────────────────────────────────────

dec     = Counter(r["import_decision"] for r in v1_rows)
high    = [r for r in v1_rows if r["import_decision"] == "import_candidate_high"]
normal  = [r for r in v1_rows if r["import_decision"] == "import_candidate_normal"]
br      = [r for r in v1_rows if r["import_decision"] == "basic_review"]
grammar = [r for r in v1_rows if r["import_decision"] == "grammar_review"]
katakana_name = [r for r in v1_rows if r["import_decision"] == "katakana_name_review"]
katakana_noise = [r for r in v1_rows if r["import_decision"] == "katakana_noise_review"]
katakana_form = [r for r in v1_rows if r["import_decision"] == "katakana_form_review"]
proper_review = [r for r in v1_rows if r["import_decision"] == "proper_name_review"]
rev     = [r for r in v1_rows if r["import_decision"] == "review"]
s_prop  = [r for r in v1_rows if r["import_decision"] == "skip_proper_name"]
s_noise = [r for r in v1_rows if r["import_decision"] == "skip_noise"]
s_exam  = [r for r in v1_rows if r["import_decision"] == "skip_exam_term"]
s_func  = [r for r in v1_rows if r["import_decision"] == "skip_basic_function_word"]

# ── Report ────────────────────────────────────────────────────────────────

W   = 72
SEP = "=" * W
s2  = "-" * W
L: list[str] = []
ln = L.append

ln(SEP)
ln("缺失 ready 词补充候选表 v3  vocab_missing_ready_candidates_v3.csv")
ln("生成日期：2026-05-13")
ln(SEP)
ln("")
ln(f"[1]  总候选数                    : {len(v1_rows)}")
ln("")
ln(f"[2]  import_candidate_high       : {dec.get('import_candidate_high',0)}")
ln(f"[3]  import_candidate_normal     : {dec.get('import_candidate_normal',0)}")
ln(f"[4]  basic_review（需人工确认）   : {dec.get('basic_review',0)}")
ln(f"[5]  grammar_review              : {dec.get('grammar_review',0)}")
ln(f"[6]  katakana_name_review        : {dec.get('katakana_name_review',0)}")
ln(f"[7]  katakana_noise_review       : {dec.get('katakana_noise_review',0)}")
ln(f"[8]  katakana_form_review        : {dec.get('katakana_form_review',0)}")
ln(f"[9]  proper_name_review          : {dec.get('proper_name_review',0)}")
ln(f"[10] review                      : {dec.get('review',0)}")
ln(f"[11] skip_proper_name            : {dec.get('skip_proper_name',0)}")
ln(f"[12] skip_basic_function_word    : {dec.get('skip_basic_function_word',0)}")
ln(f"[13] skip_exam_term              : {dec.get('skip_exam_term',0)}")
ln(f"[14] skip_noise                  : {dec.get('skip_noise',0)}")
ln("")
ln(f"  → 确定导入（high + normal）    : "
   f"{dec.get('import_candidate_high',0)+dec.get('import_candidate_normal',0)}")
ln(f"  → review 队列（basic + grammar + katakana/proper + review）: "
   f"{dec.get('basic_review',0)+dec.get('grammar_review',0)+dec.get('katakana_name_review',0)+dec.get('katakana_noise_review',0)+dec.get('katakana_form_review',0)+dec.get('proper_name_review',0)+dec.get('review',0)}")
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
        ln(f"  {r['display_word']:<18} {r['reading']:<14} "
           f"count={r['count']:<5} {r['pos_group']:<10}  "
           f"{r.get('decision_reason','')}")
    ln("")

section(11, "basic_review — 需人工确认（全部列出）", br, 100)
section(12, "grammar_review",                       grammar, 100)
section(13, "katakana_name_review",                 katakana_name, 100)
section(14, "katakana_noise_review",                katakana_noise, 100)
section(15, "katakana_form_review",                 katakana_form, 100)
section(16, "proper_name_review",                   proper_review, 100)
section(17, "skip_proper_name",                     s_prop, 100)
section(18, "import_candidate_high（前100）",        high,   100)
section(19, "import_candidate_normal（前100）",      normal, 100)

ln(s2)
ln("[20] manual reading overrides")
ln(s2)
for word, reading in READING_OVERRIDES.items():
    ln(f"  {word:<18} -> {reading}")
ln("")

ln(s2)
ln("[21] manual import approvals")
ln(s2)
for word in sorted(MANUAL_IMPORT_APPROVED):
    ln(f"  {word}")
ln("")

OUT_RPT.write_text("\n".join(L), encoding="utf-8")

print(f"CSV    → {OUT_CSV}  ({len(v1_rows)} rows)")
print(f"Import → {OUT_IMPORT_QUEUE}  ({len(import_queue)} rows)")
print(f"Review → {OUT_REVIEW_QUEUE}  ({len(review_queue)} rows)")
print(f"Report → {OUT_RPT}")
print(f"  high={len(high)}  normal={len(normal)}  basic_review={len(br)}  "
      f"grammar_review={len(grammar)}  katakana_name_review={len(katakana_name)}  "
      f"katakana_noise_review={len(katakana_noise)}  "
      f"katakana_form_review={len(katakana_form)}  "
      f"proper_name_review={len(proper_review)}  skip_proper={len(s_prop)}  "
      f"skip_func={len(s_func)}  review={len(rev)}")
