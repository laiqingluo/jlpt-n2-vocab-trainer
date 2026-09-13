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

INPUTS = [
    (
        "procedure_telecom_public",
        OUTPUT_DIR / "web_crawl_overnight_fixed_20260517_2317" / "web_sentence_materials.csv",
    ),
    (
        "life_health_parenting_cooking",
        OUTPUT_DIR / "web_crawl_life_work_edu_news_clean_20260518_0640" / "web_sentence_materials.csv",
    ),
]

MERGED_CSV = OUTPUT_DIR / "merged_web_sentence_materials.csv"
REPORT_MD = OUTPUT_DIR / "merged_web_sentence_materials_report.md"

EXTRA_FIELDS = ["source_pool"]


def normalize_sentence(sentence: str) -> str:
    text = sentence.strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("　", "")
    return text


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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_fields: list[str] | None = None
    kept_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    raw_count = 0
    duplicate_count = 0
    missing_inputs: list[str] = []
    pool_counts: Counter = Counter()
    raw_pool_counts: Counter = Counter()
    domain_counts: Counter = Counter()
    risk_counts: Counter = Counter()
    word_counts: Counter = Counter()

    for source_pool, input_path in INPUTS:
        if not input_path.exists():
            missing_inputs.append(str(input_path))
            continue

        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if all_fields is None:
                all_fields = list(reader.fieldnames or [])
            for row in reader:
                raw_count += 1
                raw_pool_counts[source_pool] += 1
                sentence = row.get("sentence", "")
                domain = row.get("source_domain", "")
                key = (domain, normalize_sentence(sentence))
                if not key[1]:
                    continue
                if key in seen:
                    duplicate_count += 1
                    continue
                seen.add(key)

                enriched = dict(row)
                enriched["source_pool"] = source_pool
                kept_rows.append(enriched)
                pool_counts[source_pool] += 1
                domain_counts[domain] += 1
                risk_counts[row.get("risk_level", "")] += 1
                for word in (row.get("matched_words") or "").split(" / "):
                    word = word.strip()
                    if word:
                        word_counts[word] += 1

    if all_fields is None:
        print("No input files found.", file=sys.stderr)
        return 1

    fieldnames = EXTRA_FIELDS + all_fields
    with MERGED_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in kept_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    sample_rows = kept_rows[:30]
    report = [
        "# Merged Web Sentence Materials Report",
        "",
        "## Inputs",
        md_table(["source_pool", "path", "exists"], [[pool, path, path.exists()] for pool, path in INPUTS]),
        "",
        "## Summary",
        md_table(
            ["metric", "value"],
            [
                ["raw_rows", raw_count],
                ["deduped_rows", len(kept_rows)],
                ["duplicates_removed", duplicate_count],
                ["missing_inputs", len(missing_inputs)],
                ["output_csv", MERGED_CSV],
            ],
        ),
        "",
        "## Source Pool Counts",
        md_table(
            ["source_pool", "raw_rows", "deduped_rows"],
            [[pool, raw_pool_counts.get(pool, 0), pool_counts.get(pool, 0)] for pool, _ in INPUTS],
        ),
        "",
        "## Risk Level Counts",
        md_table(["risk_level", "count"], [[risk, count] for risk, count in risk_counts.most_common()]),
        "",
        "## Top Domains",
        md_table(["domain", "count"], [[domain, count] for domain, count in domain_counts.most_common(30)]),
        "",
        "## Top Matched Words",
        md_table(["word", "count"], [[word, count] for word, count in word_counts.most_common(50)]),
        "",
        "## Sample Rows",
        md_table(
            ["source_pool", "domain", "risk", "score", "words", "sentence"],
            [
                [
                    row.get("source_pool", ""),
                    row.get("source_domain", ""),
                    row.get("risk_level", ""),
                    row.get("quality_score", ""),
                    row.get("matched_words", ""),
                    row.get("sentence", ""),
                ]
                for row in sample_rows
            ],
        ),
        "",
    ]
    if missing_inputs:
        report.extend(["## Missing Inputs", *[f"- `{path}`" for path in missing_inputs], ""])

    REPORT_MD.write_text("\n".join(report), encoding="utf-8")

    print(f"原始总行数: {raw_count}")
    print(f"去重后行数: {len(kept_rows)}")
    print(f"去掉重复数: {duplicate_count}")
    print(f"输出 CSV: {MERGED_CSV}")
    print(f"报告: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
