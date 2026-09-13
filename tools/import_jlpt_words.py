from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOCAB_FILE = PROJECT_ROOT / "data" / "n2_vocab.csv"

SOURCE_FIELDS = [
    "word",
    "reading",
    "part_of_speech",
    "frequency",
    "first_seen_pdf",
    "first_seen_page",
    "example",
    "lemma",
    "tags",
]

EXTRA_TARGET_FIELDS = [
    "frequency",
    "source_pdf",
    "source_page",
    "lemma",
    "tags",
    "level",
    "import_source",
]

POS_MAP = {
    "动词": "動詞",
    "名词": "名詞",
    "形容词": "形容詞",
    "副词": "副詞",
    "感动词": "感動詞",
    "连体词": "連体詞",
    "接头词": "接頭詞",
    "接尾词": "接尾詞",
}


@dataclass
class ImportPlan:
    import_rows: list[dict[str, str]]
    skipped_rows: list[tuple[int, str, str]]
    conflicts: list[tuple[int, str]]
    empty_field_count: int
    source_count: int


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_pos(value: str) -> str:
    return POS_MAP.get(value.strip(), value.strip())


def build_target_row(source_row: dict[str, str], target_fields: list[str]) -> dict[str, str]:
    word = source_row["word"].strip()
    reading = source_row["reading"].strip()
    pos = normalize_pos(source_row["part_of_speech"])
    frequency = source_row["frequency"].strip()
    example = source_row["example"].strip()
    lemma = source_row["lemma"].strip()
    tags = source_row["tags"].strip()
    first_seen_pdf = source_row["first_seen_pdf"].strip()
    first_seen_page = source_row["first_seen_page"].strip()

    row = {field: "" for field in target_fields}
    row.update(
        {
            "word": word,
            "reading": reading,
            "pos": pos,
            "meaning": "",
            "collocation": "",
            "count": frequency,
            "source": "jlpt_exam_frequency",
            "is_n2_core": "否",
            "examples": example,
            "meaning_detail": "",
            "frequency": frequency,
            "source_pdf": first_seen_pdf,
            "source_page": first_seen_page,
            "lemma": lemma,
            "tags": tags,
            "level": "N2",
            "import_source": "jlpt_exam_frequency",
        }
    )
    return row


def validate_source_fields(fieldnames: list[str]) -> None:
    missing = [field for field in SOURCE_FIELDS if field not in fieldnames]
    if missing:
        raise SystemExit(f"Source CSV missing required fields: {', '.join(missing)}")


def make_plan(source_rows: list[dict[str, str]], target_rows: list[dict[str, str]], target_fields: list[str]) -> ImportPlan:
    existing_words = {row.get("word", "").strip() for row in target_rows if row.get("word", "").strip()}
    seen_source_words: set[str] = set()
    import_rows: list[dict[str, str]] = []
    skipped_rows: list[tuple[int, str, str]] = []
    conflicts: list[tuple[int, str]] = []
    empty_field_count = 0

    for index, source_row in enumerate(source_rows, start=2):
        required_values = {field: source_row.get(field, "").strip() for field in SOURCE_FIELDS}
        empty_fields = [field for field, value in required_values.items() if not value]
        empty_field_count += len(empty_fields)

        word = required_values["word"]
        if empty_fields:
            skipped_rows.append((index, word, f"empty fields: {', '.join(empty_fields)}"))
            continue
        if not required_values["frequency"].isdigit():
            skipped_rows.append((index, word, "frequency is not numeric"))
            continue
        if word in existing_words:
            conflicts.append((index, word))
            continue
        if word in seen_source_words:
            skipped_rows.append((index, word, "duplicate word inside source file"))
            continue

        seen_source_words.add(word)
        import_rows.append(build_target_row(source_row, target_fields))

    return ImportPlan(
        import_rows=import_rows,
        skipped_rows=skipped_rows,
        conflicts=conflicts,
        empty_field_count=empty_field_count,
        source_count=len(source_rows),
    )


def print_report(plan: ImportPlan, dry_run: bool, vocab_file: Path) -> None:
    print("JLPT word import report")
    print(f"Mode: {'dry-run' if dry_run else 'import'}")
    print(f"Target vocab: {vocab_file}")
    print(f"Source rows: {plan.source_count}")
    print(f"Successful imports: {len(plan.import_rows)}")
    print(f"Skipped rows: {len(plan.skipped_rows)}")
    print(f"Conflicts: {len(plan.conflicts)}")
    print(f"Empty field count: {plan.empty_field_count}")

    if plan.conflicts:
        print("\nConflict words:")
        for index, word in plan.conflicts:
            print(f"- row {index}: {word}")

    if plan.skipped_rows:
        print("\nSkipped rows:")
        for index, word, reason in plan.skipped_rows:
            print(f"- row {index}: {word or '<empty>'} ({reason})")

    print("\nFirst 20 import results:")
    for index, row in enumerate(plan.import_rows[:20], start=1):
        print(
            f"{index}. {row['word']} | {row['reading']} | {row['pos']} | "
            f"count={row['count']} | source_pdf={row.get('source_pdf', '')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import JLPT sample words into the N2 vocab CSV.")
    parser.add_argument("--file", required=True, help="Source CSV exported from the PDF parsing project.")
    parser.add_argument("--vocab-file", default=str(DEFAULT_VOCAB_FILE), help="Target vocab CSV file.")
    parser.add_argument("--dry-run", action="store_true", help="Preview import without writing the target CSV.")
    args = parser.parse_args()

    source_file = Path(args.file)
    vocab_file = Path(args.vocab_file)
    source_fields, source_rows = read_csv(source_file)
    validate_source_fields(source_fields)

    target_fields, target_rows = read_csv(vocab_file)
    for field in EXTRA_TARGET_FIELDS:
        if field not in target_fields:
            target_fields.append(field)

    plan = make_plan(source_rows[:100], target_rows, target_fields)
    print_report(plan, args.dry_run, vocab_file)

    if args.dry_run:
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = vocab_file.with_name(f"{vocab_file.stem}.before-jlpt-import-{timestamp}{vocab_file.suffix}")
    shutil.copy2(vocab_file, backup_file)
    normalized_existing_rows = [{field: row.get(field, "") for field in target_fields} for row in target_rows]
    write_csv(vocab_file, target_fields, normalized_existing_rows + plan.import_rows)
    print(f"\nBackup created: {backup_file}")
    print(f"Import complete: appended {len(plan.import_rows)} rows")


if __name__ == "__main__":
    main()
