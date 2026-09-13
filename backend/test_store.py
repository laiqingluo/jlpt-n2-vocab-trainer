from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from db import get_conn
from vocab_store import get_word_id

# POS values that do NOT need a usage test (pure nouns, pronouns, affixes, etc.)
_NO_TEST_POS = frozenset({
    "名詞", "名", "代名詞",
    "接頭辞", "接头",
    "接尾辞", "接尾",
    "感動詞",
    "連体詞", "連体", "连体",
    "词组",
})

COMMON_PARTICLES = ["を", "に", "が", "は", "で", "へ", "と", "から", "まで", "より", "の"]


def needs_usage_test(pos: str | None) -> bool:
    return bool(pos) and pos not in _NO_TEST_POS


def _clean_col(text: str) -> str:
    """Remove Chinese translations in （…） and strip whitespace."""
    return re.sub(r"[（(][^）)]*[）)]", "", text).strip()


def _first_col(collocation: str) -> str:
    parts = re.split(r"\s*/\s*", collocation)
    return _clean_col(parts[0]) if parts else ""


def make_fill_word_question(
    word: str,
    collocation: str,
    distractors: list[str],
    examples: str = "",
) -> dict | None:
    """Generate 挖词 question: blank the target word in a sentence with enough context."""
    if not distractors:
        return None
    sentence = ""

    # 1. Prefer example sentences — try complete sentences first, then any long enough
    if examples:
        clean_ex = re.sub(r"\d{4}年\d{2}月[^\s:：]*[：:]\s*", "", examples)
        parts_ex = [_clean_col(p.strip()) for p in re.split(r"[/／]", clean_ex)]
        # Pass 1: complete sentences (ends with 。！？, ≥15 chars, no annotations)
        for s in parts_ex:
            if (word in s and len(s) >= 15
                    and re.search(r"[。！？]$", s)
                    and "(注" not in s and "（注" not in s
                    and not re.match(r"^[、。\s]", s)):
                sentence = s
                break
        # Pass 2: any sentence with the word that's long enough
        if not sentence:
            for s in parts_ex:
                if word in s and len(s) >= 10:
                    sentence = s
                    break

    # 2. Fall back to collocation
    if not sentence and collocation:
        for part in re.split(r"\s*/\s*", collocation):
            s = _clean_col(part)
            if word in s:
                sentence = s
                break

    if not sentence:
        return None

    question = sentence.replace(word, "＿＿", 1)
    # Reject if remaining context is too thin (e.g. "＿＿を" alone)
    if len(question.replace("＿＿", "").strip()) < 3:
        return None

    return {
        "q_type":      "fill_word",
        "question":    question,
        "answer":      word,
        "distractors": distractors[:3],
    }


def _find_particle_in_sentence(sentence: str) -> tuple[str, str] | None:
    """Return (question_with_blank, particle) if a particle is found, else None."""
    for particle in sorted(COMMON_PARTICLES, key=len, reverse=True):
        if particle in sentence:
            return sentence.replace(particle, "＿＿", 1), particle
    return None


def make_fill_particle_question(collocation: str, examples: str = "") -> dict | None:
    """Extract 挖助词 question. Prefers full example sentences for context."""
    # 1. Try example sentences first (longer = more context = less ambiguity)
    if examples:
        clean = re.sub(r"\d{4}年\d{2}月[^\s:：]*[：:]\s*", "", examples)
        for part in re.split(r"[/／]", clean):
            s = _clean_col(part.strip())
            if len(s) >= 10:
                found = _find_particle_in_sentence(s)
                if found:
                    question, particle = found
                    wrong = [p for p in ["を", "に", "が", "で", "へ", "と"] if p != particle][:3]
                    return {"q_type": "fill_particle", "question": question,
                            "answer": particle, "distractors": wrong}

    # 2. Fall back to collocation
    if not collocation:
        return None
    sentence = _first_col(collocation)
    found = _find_particle_in_sentence(sentence)
    if found:
        question, particle = found
        wrong = [p for p in ["を", "に", "が", "で", "へ", "と"] if p != particle][:3]
        return {"q_type": "fill_particle", "question": question,
                "answer": particle, "distractors": wrong}
    return None


# ── DB operations ─────────────────────────────────────────────────────────────

def get_test_questions(word_id: int) -> dict[str, dict]:
    """Return {q_type: question_dict} for a word_id."""
    rows = get_conn().execute(
        "SELECT * FROM word_test_questions WHERE word_id=?", (word_id,)
    ).fetchall()
    result = {}
    for row in rows:
        q = dict(row)
        try:
            q["distractors"] = json.loads(q["distractors"])
        except Exception:
            q["distractors"] = []
        result[q["q_type"]] = q
    return result


def save_test_question(
    word_id: int, q_type: str, question: str, answer: str,
    distractors: list[str], explanation: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    get_conn().execute(
        """INSERT OR REPLACE INTO word_test_questions
           (word_id, q_type, question, answer, distractors, explanation, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (word_id, q_type, question, answer,
         json.dumps(distractors, ensure_ascii=False), explanation or "", now),
    )
    get_conn().commit()


def record_test_answer(user_id: str, word: str, q_type: str, correct: bool) -> dict:
    """Update the appropriate tested field. Returns updated state."""
    from progress_store import get_word_status, update_word_status

    wp = get_word_status(user_id, word)

    if q_type == "meaning_mcq":
        if correct:
            update_word_status(user_id, word, {"meaning_tested": 1})
        return {"meaning_tested": correct or bool(wp.get("meaning_tested"))}

    if q_type == "reading_mcq":
        if correct:
            update_word_status(user_id, word, {
                "reading_tested": 1,
                "reading_status": "known",
            })
        return {"reading_tested": correct or bool(wp.get("reading_tested"))}

    if q_type == "listening_mcq":
        if correct:
            update_word_status(user_id, word, {
                "listening_tested": 1,
                "listening_status": "known",
            })
        return {"listening_tested": correct or bool(wp.get("listening_tested"))}

    if q_type == "context_mcq":
        if correct:
            update_word_status(user_id, word, {"context_tested": 1})
        return {"context_tested": correct or bool(wp.get("context_tested"))}

    # fill_word / fill_particle: usage streak logic (需连续答对 2 次)
    streak = int(wp.get("usage_streak", 0))
    new_streak = (streak + 1) if correct else 0
    tested = 1 if new_streak >= 2 else 0
    updates: dict = {"usage_streak": new_streak, "usage_tested": tested}
    if tested:
        updates["usage_status"] = "tested"
    update_word_status(user_id, word, updates)
    return {"streak": new_streak, "usage_tested": bool(tested)}


def check_all_tested(wp: dict, pos: str) -> bool:
    """Return True if all required test flags are set."""
    return (
        bool(wp.get("meaning_tested"))
        and bool(wp.get("reading_tested"))
        and bool(wp.get("listening_tested"))
        and bool(wp.get("context_tested"))
        and (bool(wp.get("usage_tested")) or not needs_usage_test(pos))
    )
