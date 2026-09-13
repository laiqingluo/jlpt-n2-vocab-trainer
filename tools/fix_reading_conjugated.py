"""Audit and repair verb readings that were left in a conjugated/base form.

The extraction pipeline sometimes normalized ``word`` to a dictionary/potential
form without normalizing ``reading`` at the same time.  This script fixes the
CSV and SQLite copies together and is safe to rerun.

Usage:
    python tools/fix_reading_conjugated.py --dry-run
    python tools/fix_reading_conjugated.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import jaconv
import unidic_lite
from fugashi import Tagger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = PROJECT_ROOT / "data" / "n2_vocab.csv"
DB_PATH = PROJECT_ROOT / "data" / "n2.db"
AUDIO_CACHE = PROJECT_ROOT / "backend" / "cache" / "word"

VERB_ENDINGS = frozenset("るうくぐすつぬぶむ")

# These errors keep the same final kana, so the general ending audit cannot
# detect them.  They were confirmed against UniDic and are included explicitly.
EXTRA_WORDS = frozenset({
    "生じる", "眠れる", "断れる", "学びとれる", "あなどれる", "転じる", "操れる",
})

# UniDic tokenizes the standalone spelling 込む as ごむ in this context; the
# vocabulary entry and its meaning use the common verb こむ.
READING_OVERRIDES = {"込む": "こむ"}


def dictionary_reading(tagger: Tagger, word: str) -> str:
    if word in READING_OVERRIDES:
        return READING_OVERRIDES[word]
    parts: list[str] = []
    for token in tagger(word):
        kana = getattr(token.feature, "kana", None)
        parts.append(jaconv.kata2hira(kana) if kana else token.surface)
    return "".join(parts)


def is_suspect(row: dict[str, str]) -> bool:
    if "動詞" not in (row.get("pos") or ""):
        return False
    word = (row.get("word") or "").strip()
    reading = (row.get("reading") or "").strip()
    ending_mismatch = bool(
        word and word[-1] in VERB_ENDINGS and (not reading or reading[-1] != word[-1])
    )
    return ending_mismatch or word in EXTRA_WORDS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with VOCAB_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    tagger = Tagger(f'-d "{unidic_lite.DICDIR}"')
    corrections: list[tuple[str, str, str]] = []
    for row in rows:
        if not is_suspect(row):
            continue
        old = row.get("reading", "").strip()
        new = dictionary_reading(tagger, row["word"].strip())
        if new and new != old:
            corrections.append((row["word"], old, new))
            row["reading"] = new

    print(f"Detected {len(corrections)} reading corrections")
    for word, old, new in corrections:
        print(f"  {word}: {old} -> {new}")

    if args.dry_run or not corrections:
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(VOCAB_PATH, VOCAB_PATH.with_name(f"n2_vocab.backup-reading-{stamp}.csv"))
    backup_db_path = DB_PATH.with_name(f"n2.db.backup-reading-{stamp}")
    source_db = sqlite3.connect(str(DB_PATH))
    backup_db = sqlite3.connect(str(backup_db_path))
    try:
        source_db.backup(backup_db)
    finally:
        backup_db.close()
        source_db.close()

    with VOCAB_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executemany(
            "UPDATE words SET reading=? WHERE word=?",
            [(new, word) for word, _old, new in corrections],
        )
        conn.commit()

        # Remove only obsolete audio files.  A cached reading still used by
        # another word must be kept because cache keys are shared by text.
        live_readings = {r[0] for r in conn.execute("SELECT DISTINCT reading FROM words")}
    finally:
        conn.close()

    removed = 0
    for _word, old, _new in corrections:
        if old in live_readings:
            continue
        cache_path = AUDIO_CACHE / f"{hashlib.md5(old.encode('utf-8')).hexdigest()}.mp3"
        if cache_path.exists():
            cache_path.unlink()
            removed += 1

    print(f"Updated CSV and SQLite; removed {removed} obsolete cached audio files")


if __name__ == "__main__":
    main()
