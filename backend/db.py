from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "n2.db"

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _create_tables(_conn)
    return _conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            word           TEXT NOT NULL UNIQUE,
            reading        TEXT NOT NULL,
            pos            TEXT,
            meaning        TEXT,
            meaning_detail TEXT,
            collocation    TEXT,
            examples       TEXT,
            count          INTEGER DEFAULT 0,
            source         TEXT,
            is_n2_core     INTEGER DEFAULT 0,
            quadrant       TEXT,
            need_story     INTEGER,
            audio_path     TEXT
        );

        CREATE TABLE IF NOT EXISTS memory_stories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id     INTEGER NOT NULL REFERENCES words(id),
            user_id     INTEGER,
            method      TEXT,
            content     TEXT NOT NULL,
            image_path  TEXT,
            likes       INTEGER DEFAULT 0,
            dislikes    INTEGER DEFAULT 0,
            status      TEXT DEFAULT 'approved',
            is_official INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_word_status (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id            TEXT NOT NULL DEFAULT 'default',
            word_id            INTEGER NOT NULL REFERENCES words(id),
            meaning_status     TEXT DEFAULT 'unknown',
            reading_status     TEXT DEFAULT 'unknown',
            listening_status   TEXT DEFAULT 'unknown',
            usage_status       TEXT DEFAULT 'unknown',
            output_status      TEXT DEFAULT 'none',
            review_count       INTEGER DEFAULT 0,
            wrong_count        INTEGER DEFAULT 0,
            correct_streak     INTEGER DEFAULT 0,
            next_review_at     TEXT,
            last_review_at     TEXT,
            fsrs_stability     REAL,
            fsrs_difficulty    REAL,
            is_mastered        INTEGER DEFAULT 0,
            via_screening      INTEGER DEFAULT 0,
            listen_mastery     TEXT DEFAULT 'unknown',
            listen_count       INTEGER DEFAULT 0,
            listen_today_count INTEGER DEFAULT 0,
            listen_today_date  TEXT,
            last_listened_at   TEXT,
            listen_due_at      TEXT,
            meaning_tested     INTEGER DEFAULT 0,
            reading_tested     INTEGER DEFAULT 0,
            listening_tested   INTEGER DEFAULT 0,
            usage_tested       INTEGER DEFAULT 0,
            usage_streak       INTEGER DEFAULT 0,
            context_tested     INTEGER DEFAULT 0,
            UNIQUE(user_id, word_id)
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id TEXT NOT NULL,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        );

        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            token      TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL,
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS word_test_questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id     INTEGER NOT NULL REFERENCES words(id),
            q_type      TEXT NOT NULL,
            question    TEXT NOT NULL,
            answer      TEXT NOT NULL,
            distractors TEXT NOT NULL,
            explanation TEXT DEFAULT '',
            created_at  TEXT NOT NULL,
            UNIQUE(word_id, q_type)
        );

        CREATE TABLE IF NOT EXISTS bug_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT,
            screen      TEXT,
            description TEXT NOT NULL,
            user_agent  TEXT,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS word_sentences (
            word_id   INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
            sentence  TEXT NOT NULL,
            source    TEXT DEFAULT '',
            UNIQUE(word_id, sentence)
        );

        CREATE INDEX IF NOT EXISTS idx_uws_user
            ON user_word_status(user_id);
        CREATE INDEX IF NOT EXISTS idx_uws_review
            ON user_word_status(user_id, next_review_at);
        CREATE INDEX IF NOT EXISTS idx_uws_listen
            ON user_word_status(user_id, listen_mastery);
        CREATE INDEX IF NOT EXISTS idx_wtq_word
            ON word_test_questions(word_id);
        CREATE INDEX IF NOT EXISTS idx_word_sentences_word
            ON word_sentences(word_id);
    """)
    conn.commit()
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(user_word_status)").fetchall()}
    new_cols = [
        ("meaning_tested",   "INTEGER DEFAULT 0"),
        ("reading_tested",   "INTEGER DEFAULT 0"),
        ("listening_tested", "INTEGER DEFAULT 0"),
        ("usage_tested",     "INTEGER DEFAULT 0"),
        ("usage_streak",     "INTEGER DEFAULT 0"),
        ("context_tested",   "INTEGER DEFAULT 0"),
    ]
    # words table migrations
    words_existing = {row[1] for row in conn.execute("PRAGMA table_info(words)").fetchall()}
    if "jlpt_level" not in words_existing:
        conn.execute("ALTER TABLE words ADD COLUMN jlpt_level INTEGER")
    for col, typedef in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE user_word_status ADD COLUMN {col} {typedef}")

    # auth_tokens table migrations
    tokens_existing = {row[1] for row in conn.execute("PRAGMA table_info(auth_tokens)").fetchall()}
    if "expires_at" not in tokens_existing:
        conn.execute("ALTER TABLE auth_tokens ADD COLUMN expires_at TEXT")
        # Pre-existing tokens predate expiry tracking; drop them so every
        # session goes through the new expiring-token path on next request.
        conn.execute("DELETE FROM auth_tokens WHERE expires_at IS NULL")
    conn.commit()


def init_db() -> None:
    """Ensure DB file and tables exist. Idempotent."""
    get_conn()
