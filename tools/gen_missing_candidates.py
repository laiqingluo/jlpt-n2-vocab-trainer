"""
gen_missing_candidates.py
Generate vocab_missing_ready_candidates.csv and report.
No source files are modified.
"""
import csv
from pathlib import Path
from collections import Counter

CLEAN    = Path(r"E:\codex\PDF解析\output\content_lemma_frequency_clean.csv")
VOCAB    = Path(r"E:\codex\jlpt背单词\data\n2_vocab.csv")
OUT_CSV  = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates.csv")
OUT_RPT  = Path(r"E:\codex\PDF解析\output\vocab_missing_ready_candidates_report.txt")

# ── Constants ─────────────────────────────────────────────────────────────

BASIC_WORDS = frozenset({
    "する", "いる", "なる", "いい", "もの", "ない", "こと", "ある",
    "人", "一", "この", "その", "それ", "行く", "来る", "思う",
})

FILLER_NOISE = frozenset({
    "いー", "んー", "うー", "まー", "あー", "えー", "おー", "あっ",
})

EXAM_TERMS = frozenset({
    "問題", "注", "選ぶ", "答え", "ページ", "以上", "以下",
    "説明", "試験", "確認", "番号", "解答", "開始",
})

OUT_FIELDS = [
    "rank", "display_word", "lemma", "reading", "pos_group",
    "count", "frequency_tier", "learning_layer",
    "quality_status", "import_status", "content_status", "review_reason",
    "source_samples", "pdf_files", "pages",
    "import_decision", "decision_reason",
]

# ── Helpers ───────────────────────────────────────────────────────────────

def to_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")

def safe_int(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0

def decide(r: dict) -> tuple[str, str]:
    """Return (import_decision, decision_reason) in priority order."""
    dw              = r["display_word"].strip()
    layer           = r.get("learning_layer", "").strip()
    review_reason   = r.get("review_reason", "").strip()
    tier            = r["frequency_tier"].strip()
    is_basic_gen    = to_bool(r.get("is_basic_generic_candidate", "False"))
    is_basic_hf     = to_bool(r.get("is_basic_high_frequency",   "False"))
    is_exam         = to_bool(r.get("is_exam_boilerplate_candidate", "False"))

    # Priority 1: basic / generic
    if (is_basic_gen
            or is_basic_hf
            or layer == "basic_generic"
            or "basic" in review_reason.lower()
            or dw in BASIC_WORDS):
        return "skip_basic", "basic_generic_or_basic_high_frequency"

    # Priority 2: filler noise
    if dw in FILLER_NOISE:
        return "skip_noise", "filler_noise"

    # Priority 3: exam / boilerplate
    if (is_exam
            or layer == "exam_boilerplate"
            or "exam_term" in review_reason
            or dw in EXAM_TERMS):
        return "skip_exam_term", "exam_boilerplate_term"

    # Priority 4 & 5: import candidates
    if tier in ("tier_1", "tier_2"):
        return "import_candidate_high", f"count≥10_not_in_vocab"
    if tier == "tier_3":
        return "import_candidate_normal", f"count5-9_not_in_vocab"

    # Fallback
    return "review", "needs_manual_check"

# ── Load sources ──────────────────────────────────────────────────────────

with open(CLEAN, encoding="utf-8-sig", newline="") as f:
    clean_rows = list(csv.DictReader(f))

with open(VOCAB, encoding="utf-8-sig", newline="") as f:
    vocab_rows = list(csv.DictReader(f))

total_clean = len(clean_rows)
total_vocab = len(vocab_rows)

# Build vocab lookup (word field + reading as secondary)
vocab_words = {r["word"].strip() for r in vocab_rows}

# Build clean lookup for match counting
clean_by_display  = {r["display_word"].strip(): r for r in clean_rows}
clean_by_original = {
    r["original_form"].strip(): r for r in clean_rows
    if r["original_form"].strip() != r["display_word"].strip()
}

matched = sum(
    1 for r in clean_rows
    if r["display_word"].strip() in vocab_words
    or r["original_form"].strip() in vocab_words
)
not_matched = total_clean - matched

# ── Filter: ready + ok + missing from vocab ───────────────────────────────

candidates = []
for r in clean_rows:
    if r["import_status"].strip() != "ready":
        continue
    if r["quality_status"].strip() != "ok":
        continue
    dw = r["display_word"].strip()
    of = r["original_form"].strip()
    if dw in vocab_words or of in vocab_words:
        continue
    candidates.append(r)

total_missing_ready = len(candidates)

# ── Apply import_decision ─────────────────────────────────────────────────

for r in candidates:
    r["import_decision"], r["decision_reason"] = decide(r)

# ── Sort: decision priority then count desc ───────────────────────────────

DECISION_ORDER = {
    "import_candidate_high":   0,
    "import_candidate_normal": 1,
    "review":                  2,
    "skip_basic":              3,
    "skip_exam_term":          4,
    "skip_noise":              5,
}
candidates.sort(key=lambda r: (
    DECISION_ORDER.get(r["import_decision"], 9),
    -safe_int(r["count"])
))

# ── Write CSV ─────────────────────────────────────────────────────────────

with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for rank, r in enumerate(candidates, 1):
        r["rank"] = rank
        writer.writerow(r)

# ── Counts ────────────────────────────────────────────────────────────────

dec_counts = Counter(r["import_decision"] for r in candidates)

high    = [r for r in candidates if r["import_decision"] == "import_candidate_high"]
normal  = [r for r in candidates if r["import_decision"] == "import_candidate_normal"]
s_basic = [r for r in candidates if r["import_decision"] == "skip_basic"]
s_noise = [r for r in candidates if r["import_decision"] == "skip_noise"]
s_exam  = [r for r in candidates if r["import_decision"] == "skip_exam_term"]
rev     = [r for r in candidates if r["import_decision"] == "review"]

# ── Report ────────────────────────────────────────────────────────────────

W   = 72
SEP = "=" * W
s2  = "-" * W
lines: list[str] = []
ln = lines.append

ln(SEP)
ln("缺失 ready 词补充候选表  vocab_missing_ready_candidates.csv")
ln("生成日期：2026-05-13")
ln(SEP)
ln("")
ln(f"[1]  clean 表总行数              : {total_clean}")
ln(f"[2]  n2_vocab 总行数             : {total_vocab}")
ln(f"[3]  两表匹配数量                 : {matched}")
ln(f"[4]  clean 有、vocab 没有         : {not_matched}")
ln(f"[5]  缺失 ready 词总数            : {total_missing_ready}")
ln("")
ln(f"[6]  import_candidate_high       : {dec_counts.get('import_candidate_high',0)}")
ln(f"[7]  import_candidate_normal     : {dec_counts.get('import_candidate_normal',0)}")
ln(f"[8]  skip_basic                  : {dec_counts.get('skip_basic',0)}")
ln(f"[9]  skip_noise                  : {dec_counts.get('skip_noise',0)}")
ln(f"[10] skip_exam_term              : {dec_counts.get('skip_exam_term',0)}")
ln(f"[11] review                      : {dec_counts.get('review',0)}")
ln("")

def section(num, title, rows, n=100):
    ln(s2)
    ln(f"[{num}] {title}（前{n}，按 count 降序）")
    ln(s2)
    if not rows:
        ln("  （无）")
    for r in sorted(rows, key=lambda x: -safe_int(x["count"]))[:n]:
        ln(f"  {r['display_word']:<18} {r['reading']:<16} "
           f"count={r['count']:<5} {r['pos_group']:<10} "
           f"{r.get('decision_reason','')}")
    ln("")

section(12, "import_candidate_high",   high,    100)
section(13, "import_candidate_normal", normal,  100)
section(14, "skip_basic",              s_basic, 100)
section(15, "review",                  rev,     100)

OUT_RPT.write_text("\n".join(lines), encoding="utf-8")

print(f"CSV    → {OUT_CSV}  ({len(candidates)} rows)")
print(f"Report → {OUT_RPT}")
print(f"  import_candidate_high={len(high)}  normal={len(normal)}  "
      f"skip_basic={len(s_basic)}  skip_exam={len(s_exam)}  "
      f"skip_noise={len(s_noise)}  review={len(rev)}")
