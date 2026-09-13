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
INPUT_CSV = OUTPUT_DIR / "clean_web_sentence_materials.csv"
LAYERED_VOCAB_CSV = OUTPUT_DIR / "n2_vocab_context_layers.csv"
OUT_CSV = OUTPUT_DIR / "word_sentence_candidates_top30.csv"
REPORT_MD = OUTPUT_DIR / "word_sentence_candidates_top30_report.md"

MAX_PER_WORD = 30
PRIMARY_CUTOFF = 10

BAD_TARGET_WORDS = {
    "こと",
    "もの",
    "ため",
    "より",
    "イン",
    "ページ",
    "サイト",
    "テーマ",
    "トップ",
}


def load_vocab_meta() -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    if not LAYERED_VOCAB_CSV.exists():
        return meta
    with LAYERED_VOCAB_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            word = (row.get("word") or "").strip()
            if word:
                meta[word] = row
    return meta


def matched_words(row: dict[str, str], vocab_meta: dict[str, dict[str, str]]) -> list[str]:
    words = []
    for word in (row.get("matched_words") or "").split(" / "):
        word = word.strip()
        if not word or word in BAD_TARGET_WORDS:
            continue
        if vocab_meta and word not in vocab_meta:
            continue
        words.append(word)
    return list(dict.fromkeys(words))


def as_int(value: str) -> int:
    try:
        return int(float(value or "0"))
    except ValueError:
        return 0


def sentence_len_score(sentence: str) -> int:
    length = len(sentence)
    if 45 <= length <= 110:
        return 20
    if 30 <= length < 45 or 110 < length <= 140:
        return 10
    return 0


def rank_score(row: dict[str, str], target_word: str) -> int:
    sentence = row.get("sentence", "")
    score = as_int(row.get("clean_score"))
    score += sentence_len_score(sentence)
    if target_word in sentence:
        score += 12
    if row.get("source_pool") == "life_health_parenting_cooking":
        score += 3
    if row.get("risk_level") == "low":
        score += 4
    if len(re.findall(r"[0-9０-９]", sentence)) >= 8:
        score -= 8
    if sentence.count("（") + sentence.count("(") >= 3:
        score -= 5
    return score


def sentence_key(sentence: str) -> str:
    return re.sub(r"\s+", "", sentence.strip())


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

    vocab_meta = load_vocab_meta()
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    raw_word_counts: Counter = Counter()
    skipped_no_word = 0

    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            words = matched_words(row, vocab_meta)
            if not words:
                skipped_no_word += 1
                continue
            for word in words:
                raw_word_counts[word] += 1
                item = dict(row)
                item["target_word"] = word
                item["target_word_reading"] = vocab_meta.get(word, {}).get("reading", "")
                item["target_word_cn"] = vocab_meta.get(word, {}).get("meaning", "")
                item["target_context_class"] = vocab_meta.get(word, {}).get("context_class", "")
                item["target_context_class_label"] = vocab_meta.get(word, {}).get("context_class_label", "")
                item["word_rank_score"] = str(rank_score(row, word))
                buckets[word].append(item)

    output_rows: list[dict[str, str]] = []
    for word, rows in buckets.items():
        seen_sentences: set[str] = set()
        unique_rows: list[dict[str, str]] = []
        rows.sort(
            key=lambda r: (
                -as_int(r.get("word_rank_score", "0")),
                -as_int(r.get("clean_score", "0")),
                r.get("source_domain", ""),
                len(r.get("sentence", "")),
            )
        )
        for row in rows:
            key = sentence_key(row.get("sentence", ""))
            if key in seen_sentences:
                continue
            seen_sentences.add(key)
            unique_rows.append(row)
            if len(unique_rows) >= MAX_PER_WORD:
                break

        for idx, row in enumerate(unique_rows, 1):
            row["candidate_rank_for_word"] = str(idx)
            row["candidate_tier"] = "primary" if idx <= PRIMARY_CUTOFF else "backup"
            row["candidate_status"] = "word_candidate"
            output_rows.append(row)

    output_rows.sort(
        key=lambda r: (
            r.get("target_context_class", "Z"),
            r.get("target_word", ""),
            as_int(r.get("candidate_rank_for_word", "999")),
        )
    )

    fieldnames = [
        "target_word",
        "target_word_reading",
        "target_word_cn",
        "target_context_class",
        "target_context_class_label",
        "candidate_rank_for_word",
        "candidate_tier",
        "word_rank_score",
    ]
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        original_fields = list(csv.DictReader(f).fieldnames or [])
    fieldnames.extend([field for field in original_fields if field not in fieldnames])

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in output_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    selected_counts = Counter(row["target_word"] for row in output_rows)
    class_counts = Counter(row.get("target_context_class", "") for row in output_rows)
    tier_counts = Counter(row.get("candidate_tier", "") for row in output_rows)
    domain_counts = Counter(row.get("source_domain", "") for row in output_rows)
    words_with_primary = sum(1 for word in selected_counts if selected_counts[word] >= 1)
    words_with_30 = sum(1 for word, count in selected_counts.items() if count >= MAX_PER_WORD)
    low_coverage = [(word, count) for word, count in selected_counts.items() if count <= 3]
    low_coverage.sort(key=lambda x: (x[1], x[0]))

    total_vocab = len(vocab_meta)
    covered_vocab = len(selected_counts)
    uncovered_vocab = total_vocab - covered_vocab if total_vocab else 0
    uncovered_words = [word for word in vocab_meta if word not in selected_counts]

    report = [
        "# Word Sentence Candidates Top 30 Report",
        "",
        "## Summary",
        md_table(
            ["metric", "value"],
            [
                ["clean_sentence_input", sum(1 for _ in INPUT_CSV.open("r", encoding="utf-8-sig")) - 1],
                ["output_rows", len(output_rows)],
                ["covered_words", covered_vocab],
                ["total_vocab_words", total_vocab],
                ["coverage", f"{covered_vocab / total_vocab:.1%}" if total_vocab else ""],
                ["uncovered_words", uncovered_vocab],
                ["words_with_30_candidates", words_with_30],
                ["skipped_clean_rows_no_valid_word", skipped_no_word],
                ["output_csv", OUT_CSV],
            ],
        ),
        "",
        "## Candidate Tier Counts",
        md_table(["tier", "count"], tier_counts.most_common()),
        "",
        "## Target Context Class Counts",
        md_table(["class", "count"], class_counts.most_common()),
        "",
        "## Top Words Before Cap",
        md_table(["word", "raw_clean_hits"], raw_word_counts.most_common(50)),
        "",
        "## Top Domains After Cap",
        md_table(["domain", "count"], domain_counts.most_common(30)),
        "",
        "## Low Coverage Words Selected (1-3 candidates) Sample",
        md_table(["word", "selected_count"], low_coverage[:100]),
        "",
        "## Uncovered Words Sample",
        ", ".join(uncovered_words[:200]),
        "",
        "## Sample Output Rows",
        md_table(
            ["word", "rank", "tier", "class", "domain", "score", "sentence"],
            [
                [
                    row.get("target_word", ""),
                    row.get("candidate_rank_for_word", ""),
                    row.get("candidate_tier", ""),
                    row.get("target_context_class", ""),
                    row.get("source_domain", ""),
                    row.get("word_rank_score", ""),
                    row.get("sentence", ""),
                ]
                for row in output_rows[:30]
            ],
        ),
        "",
    ]
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    print(f"输出候选行数: {len(output_rows)}")
    print(f"覆盖词数: {covered_vocab}/{total_vocab}" + (f" = {covered_vocab / total_vocab:.1%}" if total_vocab else ""))
    print(f"primary: {tier_counts.get('primary', 0)}")
    print(f"backup: {tier_counts.get('backup', 0)}")
    print(f"满 30 条的词数: {words_with_30}")
    print(f"输出 CSV: {OUT_CSV}")
    print(f"报告: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
