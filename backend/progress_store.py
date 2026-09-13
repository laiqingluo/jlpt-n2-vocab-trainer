from __future__ import annotations

import json

from db import get_conn
from vocab_store import get_word_id

DEFAULT_USER_ID = "default"


def get_word_status(user_id: str, word: str) -> dict:
    """Return status row for (user, word) as a plain dict, or {} if not found."""
    word_id = get_word_id(word)
    if word_id is None:
        return {}
    row = get_conn().execute(
        "SELECT * FROM user_word_status WHERE user_id=? AND word_id=?",
        (user_id, word_id),
    ).fetchone()
    return dict(row) if row else {}


def update_word_status(user_id: str, word: str, fields: dict) -> None:
    """Upsert the given fields for (user, word). Creates row if needed."""
    word_id = get_word_id(word)
    if word_id is None:
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_word_status (user_id, word_id) VALUES (?, ?) "
        "ON CONFLICT(user_id, word_id) DO NOTHING",
        (user_id, word_id),
    )
    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE user_word_status SET {set_clause} WHERE user_id=? AND word_id=?",
            [*fields.values(), user_id, word_id],
        )
    conn.commit()


def get_all_statuses(user_id: str) -> dict[str, dict]:
    """Return {word_text: status_dict} for every word that has a row."""
    rows = get_conn().execute(
        """
        SELECT w.word, uws.*
        FROM user_word_status uws
        JOIN words w ON w.id = uws.word_id
        WHERE uws.user_id = ?
        """,
        (user_id,),
    ).fetchall()
    return {row["word"]: dict(row) for row in rows}


def get_session(user_id: str, key: str) -> dict:
    """Load a JSON session blob. Returns {} if not found."""
    row = get_conn().execute(
        "SELECT value FROM user_sessions WHERE user_id=? AND key=?",
        (user_id, key),
    ).fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except Exception:
        return {}


def save_session(user_id: str, key: str, data: dict) -> None:
    """Upsert a JSON session blob."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_sessions (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
        (user_id, key, json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()
