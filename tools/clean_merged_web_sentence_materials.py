from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
INPUT_CSV = OUTPUT_DIR / "merged_web_sentence_materials.csv"
CLEAN_CSV = OUTPUT_DIR / "clean_web_sentence_materials.csv"
REVIEW_CSV = OUTPUT_DIR / "review_web_sentence_materials.csv"
REJECTED_CSV = OUTPUT_DIR / "rejected_web_sentence_materials.csv"
REPORT_MD = OUTPUT_DIR / "clean_web_sentence_materials_report.md"


SENTENCE_END_RE = re.compile(r"[。？！!?]$")
JAPANESE_RE = re.compile(r"[ぁ-んァ-ン一-龥]")
NUMBER_RE = re.compile(r"[0-9０-９]")

NAV_OR_TITLE_WORDS = {
    "トップ",
    "メニュー",
    "ログイン",
    "マイページ",
    "サイトマップ",
    "お問い合わせ",
    "ヘルプ",
    "検索",
    "一覧",
    "カテゴリ",
    "ランキング",
    "キャンペーン",
    "特集",
    "ニュース",
    "戻る",
    "次へ",
    "詳しくはこちら",
}

GOOD_CONTEXT_WORDS = {
    "場合",
    "必要",
    "確認",
    "提出",
    "申請",
    "手続き",
    "手続",
    "変更",
    "登録",
    "利用",
    "対象",
    "条件",
    "方法",
    "理由",
    "原因",
    "結果",
    "情報",
    "可能",
    "必要があります",
    "ことができます",
    "してください",
    "となります",
    "されます",
    "について",
    "により",
}

BAD_MATCHED_WORDS = {
    "こと",
    "もの",
    "ため",
    "より",
    "イン",
    "サイト",
    "ページ",
    "トップ",
    "テーマ",
    "サービス",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ")).strip()


def looks_like_title(sentence: str) -> bool:
    if SENTENCE_END_RE.search(sentence):
        return False
    if len(sentence) <= 35:
        return True
    if any(word in sentence for word in NAV_OR_TITLE_WORDS) and len(sentence) <= 55:
        return True
    return False


def too_many_proper_noun_like(sentence: str) -> bool:
    latin_chunks = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", sentence)
    katakana_chunks = re.findall(r"[ァ-ンー]{6,}", sentence)
    return len(latin_chunks) + len(katakana_chunks) >= 5


def matched_word_list(row: dict[str, str]) -> list[str]:
    return [w.strip() for w in (row.get("matched_words") or "").split(" / ") if w.strip()]


def score_and_route(row: dict[str, str]) -> tuple[str, int, str]:
    sentence = normalize_space(row.get("sentence", ""))
    words = matched_word_list(row)
    reasons: list[str] = []
    score = 50

    if not sentence or not JAPANESE_RE.search(sentence):
        return "rejected", 0, "不是日文句子或为空"

    length = len(sentence)
    if length < 18:
        return "rejected", 10, "太短，像标题/导航碎片"
    if length > 180:
        return "rejected", 25, "太长，信息过密，暂不适合直接做题"

    if looks_like_title(sentence):
        return "rejected", 20, "没有句末标点，像标题/菜单项"

    if re.search(r"https?://|www\.", sentence):
        return "rejected", 10, "包含 URL"

    if sentence.count(" ") >= 8 or "\t" in sentence:
        return "rejected", 20, "像表格/导航拼接"

    if len(NUMBER_RE.findall(sentence)) >= 14:
        return "review", 45, "数字/金额/日期较多，需要人工确认"

    if sentence.count("（") + sentence.count("(") >= 5:
        return "review", 45, "括号说明太多，需要人工确认"

    if too_many_proper_noun_like(sentence):
        return "review", 45, "专有名词/外来语块较多，需要人工确认"

    if 35 <= length <= 120:
        score += 18
        reasons.append("长度适合")
    elif 25 <= length < 35 or 120 < length <= 150:
        score += 8
        reasons.append("长度可用但需确认")
    else:
        score -= 8
        reasons.append("长度边界")

    good_hits = sum(1 for word in GOOD_CONTEXT_WORDS if word in sentence)
    if good_hits:
        score += min(good_hits * 4, 20)
        reasons.append("上下文/文脈規定信号明确")

    useful_words = [word for word in words if word not in BAD_MATCHED_WORDS]
    if len(useful_words) >= 2:
        score += 10
        reasons.append("命中多个有效词")
    elif len(useful_words) == 1:
        score += 4
        reasons.append("命中有效词")
    else:
        score -= 15
        reasons.append("命中词偏泛")

    original_quality = int(float(row.get("quality_score") or 0))
    if original_quality >= 80:
        score += 6
        reasons.append("原始质量分较高")
    elif original_quality < 60:
        score -= 8
        reasons.append("原始质量分较低")

    if row.get("risk_level") == "high":
        score -= 12
        reasons.append("原始风险较高")

    if any(word in sentence for word in NAV_OR_TITLE_WORDS) and length < 70:
        score -= 8
        reasons.append("可能含导航/标题词")

    score = max(1, min(100, score))
    reason = "；".join(dict.fromkeys(reasons)) or "基础规则通过"

    if score >= 72:
        return "clean", score, reason
    if score >= 45:
        return "review", score, reason
    return "rejected", score, reason


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

    clean_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []

    route_counts: Counter = Counter()
    reason_counts: Counter = Counter()
    pool_counts: dict[str, Counter] = defaultdict(Counter)
    domain_counts: dict[str, Counter] = defaultdict(Counter)
    word_counts: dict[str, Counter] = defaultdict(Counter)

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        base_fields = list(reader.fieldnames or [])
        fieldnames = ["clean_status", "clean_score", "clean_reason"] + base_fields
        for row in reader:
            route, score, reason = score_and_route(row)
            enriched = dict(row)
            enriched["sentence"] = normalize_space(enriched.get("sentence", ""))
            enriched["clean_status"] = route
            enriched["clean_score"] = str(score)
            enriched["clean_reason"] = reason

            route_counts[route] += 1
            reason_counts[reason] += 1
            pool_counts[route][row.get("source_pool", "")] += 1
            domain_counts[route][row.get("source_domain", "")] += 1
            for word in matched_word_list(row):
                word_counts[route][word] += 1

            if route == "clean":
                clean_rows.append(enriched)
            elif route == "review":
                review_rows.append(enriched)
            else:
                rejected_rows.append(enriched)

    clean_rows.sort(key=lambda r: (-int(r["clean_score"]), r.get("source_domain", ""), r.get("sentence", "")))
    review_rows.sort(key=lambda r: (-int(r["clean_score"]), r.get("source_domain", ""), r.get("sentence", "")))
    rejected_rows.sort(key=lambda r: (r.get("clean_reason", ""), r.get("source_domain", "")))

    write_csv(CLEAN_CSV, fieldnames, clean_rows)
    write_csv(REVIEW_CSV, fieldnames, review_rows)
    write_csv(REJECTED_CSV, fieldnames, rejected_rows)

    total = sum(route_counts.values())
    report = [
        "# Clean Web Sentence Materials Report",
        "",
        "## Summary",
        md_table(
            ["status", "count", "percent"],
            [
                [status, route_counts.get(status, 0), f"{route_counts.get(status, 0) / total:.1%}" if total else "0.0%"]
                for status in ["clean", "review", "rejected"]
            ],
        ),
        "",
        "## Output Files",
        md_table(
            ["status", "path"],
            [["clean", CLEAN_CSV], ["review", REVIEW_CSV], ["rejected", REJECTED_CSV]],
        ),
        "",
        "## Source Pool Counts",
    ]
    for status in ["clean", "review", "rejected"]:
        report.extend(
            [
                f"### {status}",
                md_table(["source_pool", "count"], pool_counts[status].most_common()),
                "",
            ]
        )

    report.extend(["## Top Domains By Status"])
    for status in ["clean", "review", "rejected"]:
        report.extend(
            [
                f"### {status}",
                md_table(["domain", "count"], domain_counts[status].most_common(20)),
                "",
            ]
        )

    report.extend(["## Top Matched Words In Clean"])
    report.append(md_table(["word", "count"], word_counts["clean"].most_common(50)))
    report.extend(["", "## Top Reasons"])
    report.append(md_table(["reason", "count"], reason_counts.most_common(30)))

    for status, rows in [("clean", clean_rows), ("review", review_rows), ("rejected", rejected_rows)]:
        report.extend(
            [
                "",
                f"## Sample {status}",
                md_table(
                    ["score", "reason", "domain", "words", "sentence"],
                    [
                        [
                            row.get("clean_score", ""),
                            row.get("clean_reason", ""),
                            row.get("source_domain", ""),
                            row.get("matched_words", ""),
                            row.get("sentence", ""),
                        ]
                        for row in rows[:25]
                    ],
                ),
            ]
        )

    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    print(f"输入行数: {total}")
    print(f"clean: {len(clean_rows)}")
    print(f"review: {len(review_rows)}")
    print(f"rejected: {len(rejected_rows)}")
    print(f"clean CSV: {CLEAN_CSV}")
    print(f"review CSV: {REVIEW_CSV}")
    print(f"rejected CSV: {REJECTED_CSV}")
    print(f"报告: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
