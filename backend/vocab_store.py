from __future__ import annotations

from db import get_conn

_WORD_ID_MAP: dict[str, int] = {}


def _ensure_word_id_map() -> None:
    if not _WORD_ID_MAP:
        rows = get_conn().execute("SELECT id, word FROM words").fetchall()
        _WORD_ID_MAP.update({r["word"]: r["id"] for r in rows})


def get_word_id(word_text: str) -> int | None:
    _ensure_word_id_map()
    return _WORD_ID_MAP.get(word_text)


def load_n2_vocab() -> list[dict]:
    rows = get_conn().execute(
        """
        SELECT id, word, reading, pos, meaning, meaning_detail, collocation,
               examples, count, source, is_n2_core, quadrant, need_story, audio_path,
               jlpt_level
        FROM words
        ORDER BY count DESC, word
        """
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r) -> dict:
    return {
        "id":             r["id"],
        "word":           r["word"],
        "reading":        r["reading"],
        "pos":            r["pos"] or "",
        "meaning":        r["meaning_detail"] or r["meaning"] or "",
        "meaning_detail": r["meaning_detail"] or "",
        "collocation":    r["collocation"] or "",
        "examples":       r["examples"] or "",
        "count":       r["count"] or 0,
        "source":      r["source"] or "",
        "is_n2_core":  bool(r["is_n2_core"]),
        "quadrant":    r["quadrant"] or "",
        "need_story":  r["need_story"],
        "audio_path":  r["audio_path"],
        "jlpt_level":  r["jlpt_level"],
    }
