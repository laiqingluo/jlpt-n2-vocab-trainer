"""Idempotent sync: n2_vocab.csv + legacy progress/default.json → data/n2.db.

Run from the project root:
    python tools/migrate_to_sqlite.py

Existing user progress and session state are preserved.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from db import DB_PATH, get_conn, init_db  # noqa: E402


VERB_ENDINGS = frozenset("るうくぐすつぬぶむ")


def validate_reading(word: str, reading: str, pos: str) -> None:
    """Reject the common lemma/inflected-reading mismatch before DB sync."""
    if (
        "動詞" in pos
        and word
        and word[-1] in VERB_ENDINGS
        and (not reading or reading[-1] != word[-1])
    ):
        raise ValueError(
            f"动词读音与词典形不一致：{word} / {reading}；"
            "请先运行 tools/fix_reading_conjugated.py"
        )


def migrate_words() -> dict[str, int]:
    """Insert all rows from n2_vocab.csv into words table.

    Returns a {word_text: word_id} map for use by migrate_progress.
    """
    csv_path = PROJECT_ROOT / "data" / "n2_vocab.csv"
    conn = get_conn()

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    processed = inserted = updated = 0
    for csv_id, r in enumerate(rows, start=1):
        word = r.get("word", "").strip()
        if not word:
            continue
        reading = r.get("reading", "").strip()
        pos = r.get("pos", "").strip()
        validate_reading(word, reading, pos)
        is_n2_core = 1 if r.get("is_n2_core", "否").strip() == "是" else 0
        values = (
            reading, pos, r.get("meaning", ""),
            r.get("meaning_detail", ""), r.get("collocation", ""),
            r.get("examples", ""), int(r.get("count") or 0),
            r.get("source", ""), is_n2_core, r.get("quadrant", ""),
        )

        existing = conn.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE words SET
                     reading=?, pos=?, meaning=?, meaning_detail=?, collocation=?,
                     examples=?, count=?, source=?, is_n2_core=?, quadrant=?
                   WHERE word=?""",
                (*values, word),
            )
            updated += 1
        else:
            id_owner = conn.execute("SELECT word FROM words WHERE id = ?", (csv_id,)).fetchone()
            if id_owner is None:
                # CSV row ids are stable in this dataset. Reusing a free original id
                # also reconnects stories left behind by an interrupted word import.
                conn.execute(
                    """INSERT INTO words
                         (id, word, reading, pos, meaning, meaning_detail, collocation,
                          examples, count, source, is_n2_core, quadrant)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (csv_id, word, *values),
                )
            else:
                # Never overwrite a differently mapped id in databases created by
                # another importer; allocate a fresh id and preserve its relations.
                conn.execute(
                    """INSERT INTO words
                         (word, reading, pos, meaning, meaning_detail, collocation,
                          examples, count, source, is_n2_core, quadrant)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (word, *values),
                )
            inserted += 1
        processed += 1

    conn.commit()
    print(f"  words: {processed} rows processed ({inserted} inserted, {updated} updated)")

    word_id_map = {
        row["word"]: row["id"]
        for row in conn.execute("SELECT id, word FROM words").fetchall()
    }
    print(f"  words: {len(word_id_map)} total in DB")
    return word_id_map


def _meaning_to_status(result: str | None) -> str:
    return {"known": "known_fast", "good": "known_slow"}.get(result or "", "unknown")


def _reading_to_status(result: str | None) -> str:
    return {"known": "known", "good": "known", "hard": "uncertain"}.get(result or "", "unknown")


def _listening_to_status(result: str | None) -> str:
    return {"known": "known", "good": "known", "hard": "slow"}.get(result or "", "unknown")


def migrate_progress(word_id_map: dict[str, int]) -> None:
    """Migrate progress/default.json into user_word_status and user_sessions."""
    progress_path = PROJECT_ROOT / "progress" / "default.json"
    if not progress_path.exists():
        print("  No progress/default.json found — skipping.")
        return

    conn = get_conn()
    with progress_path.open(encoding="utf-8") as f:
        progress = json.load(f)

    vocab_progress: dict = progress.get("n2_vocab", {})
    inserted = skipped = 0

    for word_text, wp in vocab_progress.items():
        word_id = word_id_map.get(word_text)
        if word_id is None:
            skipped += 1
            continue

        dims = wp.get("dims", {})
        rec_result    = wp.get("result")
        listen_result = dims.get("listening", {}).get("result")
        read_result   = dims.get("reading", {}).get("result")

        conn.execute(
            """
            INSERT INTO user_word_status
                (user_id, word_id,
                 meaning_status, reading_status, listening_status,
                 review_count, next_review_at, last_review_at,
                 fsrs_stability, fsrs_difficulty,
                 is_mastered, via_screening,
                 listen_mastery)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, word_id) DO NOTHING
            """,
            (
                "default",
                word_id,
                _meaning_to_status(rec_result),
                _reading_to_status(read_result),
                _listening_to_status(listen_result),
                wp.get("review_count", 0),
                wp.get("next_review_at"),
                wp.get("last_reviewed_at"),
                wp.get("fsrs_stability"),
                wp.get("fsrs_difficulty"),
                1 if wp.get("is_mastered") else 0,
                1 if wp.get("via_screening") else 0,
                wp.get("listen_mastery", "unknown"),
            ),
        )
        inserted += 1

    conn.commit()
    print(f"  progress: {inserted} words migrated, {skipped} skipped (word not in vocab)")

    # Migrate listening session state
    listening_state = progress.get("n2_listening", {})
    if listening_state:
        conn.execute(
            "INSERT INTO user_sessions (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO NOTHING",
            ("default", "n2_listening", json.dumps(listening_state, ensure_ascii=False)),
        )
        conn.commit()
        print("  listening session state migrated")


def main() -> None:
    print(f"Target DB: {DB_PATH}")
    init_db()
    print("Migrating words...")
    word_id_map = migrate_words()
    print("Migrating progress...")
    migrate_progress(word_id_map)
    print("Done.")


if __name__ == "__main__":
    main()
