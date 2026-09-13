from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
INPUT_CSV = OUTPUT_DIR / "word_sentence_candidates_top30.csv"
MAIN_CSV = OUTPUT_DIR / "word_candidates_main.csv"
REVIEW_CSV = OUTPUT_DIR / "word_candidates_target_review.csv"
EXCLUDED_CSV = OUTPUT_DIR / "word_candidates_target_excluded.csv"
REPORT_MD = OUTPUT_DIR / "word_candidates_target_filter_report.md"


EXCLUDE_WORDS = {
    "こと",
    "もの",
    "ため",
    "より",
    "イン",
    "アウト",
    "ページ",
    "サイト",
    "トップ",
    "テーマ",
    "こちら",
    "そこ",
    "ここ",
    "これ",
    "それ",
    "あれ",
    "どれ",
    "よう",
    "さん",
    "ちゃん",
    "くん",
    "たち",
    "ら",
    "など",
    "ほか",
    "かし",
    "あかり",
    "ちそう",
}

REVIEW_WORDS = {
    "おかげ",
    "せい",
    "たび",
    "ところ",
    "わけ",
    "はず",
    "まま",
    "一方",
    "現在",
    "一部",
    "全部",
    "下記",
    "上記",
}

GOOD_TARGET_HINTS = {
    "申請",
    "提出",
    "確認",
    "変更",
    "登録",
    "利用",
    "必要",
    "対象",
    "条件",
    "要件",
    "場合",
    "方法",
    "情報",
    "契約",
    "手続き",
    "手続",
    "内容",
    "理由",
    "原因",
    "結果",
    "対応",
    "可能",
    "判断",
    "選択",
    "説明",
    "相談",
    "予約",
    "料金",
    "口座",
    "住所",
    "書類",
    "証明",
    "保険",
    "医療",
    "健康",
    "教育",
    "仕事",
}


def is_hiragana_only(word: str) -> bool:
    return bool(re.fullmatch(r"[ぁ-んー]+", word))


def is_fragment(word: str) -> bool:
    if len(word) <= 1:
        return True
    if re.fullmatch(r"[0-9０-９A-Za-z_-]+", word):
        return True
    if re.fullmatch(r"[ァ-ンー]{2,}", word) and len(word) <= 3:
        return True
    return False


def classify_target(row: dict[str, str]) -> tuple[str, str]:
    word = (row.get("target_word") or "").strip()
    pos = ""
    klass = row.get("target_context_class", "")
    label = row.get("target_context_class_label", "")
    sentence = row.get("sentence", "")

    if not word:
        return "excluded", "目标词为空"
    if word in EXCLUDE_WORDS:
        return "excluded", "目标词是泛词/碎片/不适合作为出题目标"
    if is_fragment(word):
        return "excluded", "目标词太短或像碎片"
    if word not in sentence:
        return "review", "目标词未直接出现在句子中，需要确认匹配质量"
    if word in REVIEW_WORDS:
        return "review", "语法性/形式名词倾向，需要人工确认是否适合文脈規定"
    if is_hiragana_only(word) and len(word) <= 3:
        return "review", "假名短词，容易误匹配或语法化"
    if klass == "D":
        return "excluded", "词库分层为 D，暂不进主库"
    if klass in {"A", "B", "C"}:
        if word in GOOD_TARGET_HINTS:
            return "main", "目标词明确，适合继续做候选"
        if klass == "A" and len(word) >= 2:
            return "main", "A类词，暂保留"
        if klass in {"B", "C"} and len(word) >= 2:
            return "main", "B/C类词，暂保留"
    return "review", f"目标词属性不够明确：class={klass} {label}"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"Input not found: {INPUT_CSV}", file=sys.stderr)
        return 1

    main_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    reason_counts: Counter = Counter()
    status_counts: Counter = Counter()
    word_status: dict[str, str] = {}
    word_reason: dict[str, str] = {}

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        base_fields = list(reader.fieldnames or [])
        fieldnames = ["target_filter_status", "target_filter_reason"] + base_fields
        for row in reader:
            status, reason = classify_target(row)
            row = dict(row)
            row["target_filter_status"] = status
            row["target_filter_reason"] = reason
            status_counts[status] += 1
            reason_counts[reason] += 1
            word = row.get("target_word", "")
            word_status.setdefault(word, status)
            word_reason.setdefault(word, reason)
            if status == "main":
                main_rows.append(row)
            elif status == "review":
                review_rows.append(row)
            else:
                excluded_rows.append(row)

    write_csv(MAIN_CSV, fieldnames, main_rows)
    write_csv(REVIEW_CSV, fieldnames, review_rows)
    write_csv(EXCLUDED_CSV, fieldnames, excluded_rows)

    main_words = Counter(row.get("target_word", "") for row in main_rows)
    review_words = Counter(row.get("target_word", "") for row in review_rows)
    excluded_words = Counter(row.get("target_word", "") for row in excluded_rows)
    class_counts = Counter(row.get("target_context_class", "") for row in main_rows)

    report = [
        "# Word Candidate Target Filter Report",
        "",
        "## Summary",
        md_table(
            ["status", "rows", "unique_words"],
            [
                ["main", len(main_rows), len(main_words)],
                ["review", len(review_rows), len(review_words)],
                ["excluded", len(excluded_rows), len(excluded_words)],
            ],
        ),
        "",
        "## Output Files",
        md_table(
            ["status", "path"],
            [["main", MAIN_CSV], ["review", REVIEW_CSV], ["excluded", EXCLUDED_CSV]],
        ),
        "",
        "## Main Context Class Counts",
        md_table(["class", "rows"], class_counts.most_common()),
        "",
        "## Top Filter Reasons",
        md_table(["reason", "rows"], reason_counts.most_common(30)),
        "",
        "## Review Words Sample",
        md_table(["word", "rows", "reason"], [[w, c, word_reason.get(w, "")] for w, c in review_words.most_common(80)]),
        "",
        "## Excluded Words Sample",
        md_table(["word", "rows", "reason"], [[w, c, word_reason.get(w, "")] for w, c in excluded_words.most_common(80)]),
        "",
        "## Main Sample",
        md_table(
            ["word", "class", "rank", "tier", "domain", "sentence"],
            [
                [
                    row.get("target_word", ""),
                    row.get("target_context_class", ""),
                    row.get("candidate_rank_for_word", ""),
                    row.get("candidate_tier", ""),
                    row.get("source_domain", ""),
                    row.get("sentence", ""),
                ]
                for row in main_rows[:30]
            ],
        ),
        "",
    ]
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    print(f"main rows: {len(main_rows)} words: {len(main_words)}")
    print(f"review rows: {len(review_rows)} words: {len(review_words)}")
    print(f"excluded rows: {len(excluded_rows)} words: {len(excluded_words)}")
    print(f"main CSV: {MAIN_CSV}")
    print(f"review CSV: {REVIEW_CSV}")
    print(f"excluded CSV: {EXCLUDED_CSV}")
    print(f"报告: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
