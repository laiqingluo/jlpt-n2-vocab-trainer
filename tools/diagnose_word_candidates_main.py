from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
INPUT_CSV = OUTPUT_DIR / "word_candidates_main.csv"
REPORT_MD = OUTPUT_DIR / "word_candidates_main_diagnosis.md"
SUMMARY_CSV = OUTPUT_DIR / "word_candidates_main_word_summary.csv"


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

    rows: list[dict[str, str]] = []
    with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    by_word: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_word[row.get("target_word", "")].append(row)

    class_row_counts = Counter(row.get("target_context_class", "") for row in rows)
    class_word_counts = Counter()
    tier_counts_by_class: dict[str, Counter] = defaultdict(Counter)
    domain_counts_by_class: dict[str, Counter] = defaultdict(Counter)
    pool_counts_by_class: dict[str, Counter] = defaultdict(Counter)

    word_summary_rows: list[dict[str, object]] = []
    for word, word_rows in by_word.items():
        klass = word_rows[0].get("target_context_class", "")
        class_word_counts[klass] += 1
        domains = Counter(row.get("source_domain", "") for row in word_rows)
        pools = Counter(row.get("source_pool", "") for row in word_rows)
        tiers = Counter(row.get("candidate_tier", "") for row in word_rows)
        for row in word_rows:
            tier_counts_by_class[klass][row.get("candidate_tier", "")] += 1
            domain_counts_by_class[klass][row.get("source_domain", "")] += 1
            pool_counts_by_class[klass][row.get("source_pool", "")] += 1
        word_summary_rows.append(
            {
                "target_word": word,
                "reading": word_rows[0].get("target_word_reading", ""),
                "meaning": word_rows[0].get("target_word_cn", ""),
                "context_class": klass,
                "context_class_label": word_rows[0].get("target_context_class_label", ""),
                "candidate_count": len(word_rows),
                "primary_count": tiers.get("primary", 0),
                "backup_count": tiers.get("backup", 0),
                "domain_count": len(domains),
                "top_domain": domains.most_common(1)[0][0] if domains else "",
                "top_domain_count": domains.most_common(1)[0][1] if domains else 0,
                "source_pool_count": len(pools),
                "top_source_pool": pools.most_common(1)[0][0] if pools else "",
            }
        )

    word_summary_rows.sort(key=lambda r: (str(r["context_class"]), int(r["candidate_count"]), str(r["target_word"])))
    summary_fields = [
        "target_word",
        "reading",
        "meaning",
        "context_class",
        "context_class_label",
        "candidate_count",
        "primary_count",
        "backup_count",
        "domain_count",
        "top_domain",
        "top_domain_count",
        "source_pool_count",
        "top_source_pool",
    ]
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(word_summary_rows)

    low_coverage = [r for r in word_summary_rows if int(r["candidate_count"]) <= 3]
    enough_10 = [r for r in word_summary_rows if int(r["candidate_count"]) >= 10]
    full_30 = [r for r in word_summary_rows if int(r["candidate_count"]) >= 30]
    single_domain = [r for r in word_summary_rows if int(r["domain_count"]) == 1 and int(r["candidate_count"]) >= 10]

    report = [
        "# Word Candidates Main Diagnosis",
        "",
        "## Overall",
        md_table(
            ["metric", "value"],
            [
                ["rows", len(rows)],
                ["unique_words", len(by_word)],
                ["words_with_1_3_candidates", len(low_coverage)],
                ["words_with_10_plus_candidates", len(enough_10)],
                ["words_with_30_candidates", len(full_30)],
                ["words_10_plus_but_single_domain", len(single_domain)],
                ["summary_csv", SUMMARY_CSV],
            ],
        ),
        "",
        "## A/B/C Counts",
        md_table(
            ["class", "words", "rows", "primary", "backup"],
            [
                [
                    klass,
                    class_word_counts.get(klass, 0),
                    class_row_counts.get(klass, 0),
                    tier_counts_by_class[klass].get("primary", 0),
                    tier_counts_by_class[klass].get("backup", 0),
                ]
                for klass in ["A", "B", "C", ""]
                if class_word_counts.get(klass, 0) or class_row_counts.get(klass, 0)
            ],
        ),
        "",
    ]

    for klass in ["A", "B", "C"]:
        report.extend(
            [
                f"## Class {klass}",
                "### Top Domains",
                md_table(["domain", "rows"], domain_counts_by_class[klass].most_common(20)),
                "",
                "### Source Pools",
                md_table(["source_pool", "rows"], pool_counts_by_class[klass].most_common()),
                "",
                "### Low Coverage Words Sample",
                md_table(
                    ["word", "reading", "meaning", "count", "top_domain"],
                    [
                        [r["target_word"], r["reading"], r["meaning"], r["candidate_count"], r["top_domain"]]
                        for r in low_coverage
                        if r["context_class"] == klass
                    ][:80],
                ),
                "",
            ]
        )

    report.extend(
        [
            "## 10+ Candidates But Single Domain Sample",
            md_table(
                ["word", "class", "count", "top_domain"],
                [[r["target_word"], r["context_class"], r["candidate_count"], r["top_domain"]] for r in single_domain[:100]],
            ),
            "",
            "## Full 30 Candidate Words Sample",
            md_table(
                ["word", "class", "top_domain", "domain_count"],
                [[r["target_word"], r["context_class"], r["top_domain"], r["domain_count"]] for r in full_30[:100]],
            ),
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    print(f"主候选行数: {len(rows)}")
    print(f"覆盖词数: {len(by_word)}")
    print(f"A/B/C rows: {class_row_counts.get('A',0)} / {class_row_counts.get('B',0)} / {class_row_counts.get('C',0)}")
    print(f"A/B/C words: {class_word_counts.get('A',0)} / {class_word_counts.get('B',0)} / {class_word_counts.get('C',0)}")
    print(f"候选<=3的词: {len(low_coverage)}")
    print(f"候选>=10的词: {len(enough_10)}")
    print(f"满30条的词: {len(full_30)}")
    print(f"报告: {REPORT_MD}")
    print(f"词汇摘要: {SUMMARY_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
