from __future__ import annotations

import json
import os
import random
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth_router import resolve_user_id
from progress_store import get_all_statuses, get_word_status
from test_store import (
    check_all_tested,
    get_test_questions,
    make_fill_particle_question,
    make_fill_word_question,
    needs_usage_test,
    record_test_answer,
    save_test_question,
)
from vocab_store import get_word_id, load_n2_vocab

router = APIRouter()

_VOCAB: list[dict] = []
_VOCAB_BY_WORD: dict[str, dict] = {}

# Fixed test order for all words
_TEST_ORDER = ["meaning_mcq", "reading_mcq", "listening_mcq", "fill_word"]


def _get_vocab() -> list[dict]:
    global _VOCAB, _VOCAB_BY_WORD
    if not _VOCAB:
        _VOCAB = load_n2_vocab()
        _VOCAB_BY_WORD = {w["word"]: w for w in _VOCAB}
    return _VOCAB


def _word_data(word: str) -> dict | None:
    _get_vocab()
    return _VOCAB_BY_WORD.get(word)


def _distractor_pool(pos: str, exclude_word: str, key: str) -> list[str]:
    """Build a distractor pool for the given key ('word', 'reading', 'meaning').
    Prefers same-POS words; falls back to full vocab."""
    vocab = _get_vocab()
    same = [w for w in vocab if w.get("pos") == pos and w["word"] != exclude_word]
    rest = [w for w in vocab if w.get("pos") != pos and w["word"] != exclude_word]
    random.shuffle(same)
    random.shuffle(rest)
    ordered = same + rest

    seen: set[str] = set()
    pool: list[str] = []
    for w in ordered:
        val = w[key] if key != "meaning" else _short_meaning(w.get("meaning", ""))
        if val and val not in seen:
            seen.add(val)
            pool.append(val)
        if len(pool) >= 20:
            break
    return pool


def _short_meaning(text: str) -> str:
    """Extract a short Chinese meaning summary (first numbered entry)."""
    if not text:
        return ""
    m = re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]\s*([^（①②③④⑤⑥⑦⑧⑨⑩]{1,20})", text)
    if m:
        return m.group(1).split("（")[0].strip()
    return text.split("（")[0][:20].strip()


def _make_meaning_mcq(word: str, wd: dict) -> dict | None:
    correct = _short_meaning(wd.get("meaning", ""))
    if not correct:
        return None
    distractors = [d for d in _distractor_pool(wd.get("pos", ""), word, "meaning") if d != correct][:3]
    if len(distractors) < 3:
        return None
    options = [correct] + distractors
    random.shuffle(options)
    return {"q_type": "meaning_mcq", "question": word, "answer": correct, "options": options}


def _make_reading_mcq(word: str, wd: dict) -> dict | None:
    correct = wd.get("reading", "")
    if not correct:
        return None
    distractors = [d for d in _distractor_pool(wd.get("pos", ""), word, "reading") if d != correct][:3]
    if len(distractors) < 3:
        return None
    options = [correct] + distractors
    random.shuffle(options)
    return {"q_type": "reading_mcq", "question": word, "answer": correct, "options": options}


def _make_listening_mcq(word: str, wd: dict) -> dict | None:
    """Audio plays client-side; options are Japanese words (kanji)."""
    distractors = [d for d in _distractor_pool(wd.get("pos", ""), word, "word")][:3]
    if len(distractors) < 3:
        return None
    options = [word] + distractors
    random.shuffle(options)
    return {
        "q_type": "listening_mcq",
        "question": "",          # no text shown; audio plays
        "audio_word": wd.get("reading") or word,
        "answer": word,
        "options": options,
    }


def _pick_context_sentence(word: str, examples: str) -> str | None:
    """从例句中找一个包含目标词的句子并将目标词替换为＿＿。"""
    # 清理PDF来源标记
    clean = re.sub(r"\d{4}年\d{2}月[^\s:：]*[：:]\s*", "", examples)
    sentences = [s.strip() for s in re.split(r"[/／]", clean) if s.strip()]
    for s in sentences:
        if word in s and len(s) >= 8:
            return s.replace(word, "＿＿", 1)
    return None


def _make_context_mcq(word: str, wd: dict) -> dict | None:
    """文脈規定：在例句中挖空目标词，从同词性选项里选出正确答案。"""
    examples = wd.get("examples", "") or ""
    question = _pick_context_sentence(word, examples)
    if not question:
        # 降级：用搭配短语
        collocation = wd.get("collocation", "") or ""
        if collocation and word in collocation:
            question = collocation.split("/")[0].strip().replace(word, "＿＿", 1)
    if not question:
        return None

    distractors = [d for d in _distractor_pool(wd.get("pos", ""), word, "word") if d != word][:3]
    if len(distractors) < 3:
        return None
    options = [word] + distractors
    random.shuffle(options)
    return {
        "q_type": "context_mcq",
        "question": question,
        "answer": word,
        "options": options,
    }


def _question_options(question: dict) -> list[str]:
    """Return shuffled choices for both live and cached question formats."""
    options = list(question.get("options") or [])
    if not options:
        options = [question.get("answer"), *(question.get("distractors") or [])]
    # Preserve order while removing empty or duplicate choices, then shuffle so
    # cached usage questions do not always put the correct answer first.
    options = list(dict.fromkeys(option for option in options if option))
    random.shuffle(options)
    return options


def _ensure_usage_questions(word: str, word_id: int, wd: dict) -> dict[str, dict]:
    """Return cached fill_word / fill_particle questions, generating if missing."""
    questions = get_test_questions(word_id)

    if "fill_word" not in questions and wd.get("collocation"):
        pos = wd.get("pos", "")
        pool = _distractor_pool(pos, word, "word")
        distractors = pool[:3]
        if len(distractors) >= 3:
            q = make_fill_word_question(word, wd["collocation"], distractors, wd.get("examples", "") or "")
            if q:
                save_test_question(word_id, "fill_word", q["question"], q["answer"], q["distractors"])
                questions["fill_word"] = q

    if "fill_particle" not in questions and wd.get("collocation"):
        q = make_fill_particle_question(wd["collocation"], wd.get("examples", "") or "")
        if q:
            save_test_question(word_id, "fill_particle", q["question"], q["answer"], q["distractors"])
            questions["fill_particle"] = q

    return questions


def _next_q_type(wp: dict, wd: dict) -> str | None:
    """Return the first untested q_type in the fixed order, or None if all done."""
    pos = wd.get("pos", "")
    if not wp.get("meaning_tested"):
        return "meaning_mcq"
    if not wp.get("reading_tested"):
        return "reading_mcq"
    if not wp.get("listening_tested"):
        return "listening_mcq"
    if not wp.get("context_tested"):
        return "context_mcq"
    # Usage test only for applicable POS
    if needs_usage_test(pos) and not wp.get("usage_tested"):
        streak = int(wp.get("usage_streak", 0))
        return "fill_particle" if streak >= 1 else "fill_word"
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/test/queue")
async def get_test_queue(request: Request):
    """Words that have been learned but still have at least one untested dimension."""
    vocab = _get_vocab()
    user_id  = resolve_user_id(request)
    statuses = get_all_statuses(user_id)
    queue = []
    for w in vocab:
        wp = statuses.get(w["word"], {})
        if wp.get("meaning_status", "unknown") == "unknown":
            continue  # not yet learned
        if check_all_tested(wp, w.get("pos", "")):
            continue  # all tests passed
        next_qt = _next_q_type(wp, w)
        if next_qt is None:
            continue
        queue.append({
            "word":        w["word"],
            "reading":     w["reading"],
            "meaning":     w.get("meaning", ""),
            "pos":         w.get("pos", ""),
            "next_q_type": next_qt,
        })
    return {"queue": queue, "total": len(queue)}


@router.get("/api/test/question/{word}")
async def get_test_question(word: str, request: Request):
    """Return the next question for this word following the fixed test order."""
    wd = _word_data(word)
    if not wd:
        raise HTTPException(404, "word not found")
    word_id = get_word_id(word)
    if not word_id:
        raise HTTPException(404, "word not in DB")

    user_id = resolve_user_id(request)
    wp = get_word_status(user_id, word)
    q_type = _next_q_type(wp, wd)

    if q_type is None:
        raise HTTPException(200, "all tests passed for this word")

    # Generate the question
    if q_type == "meaning_mcq":
        q = _make_meaning_mcq(word, wd)
    elif q_type == "reading_mcq":
        q = _make_reading_mcq(word, wd)
    elif q_type == "listening_mcq":
        q = _make_listening_mcq(word, wd)
    elif q_type == "context_mcq":
        q = _make_context_mcq(word, wd)
    else:
        # fill_word or fill_particle — use cached questions
        usage_qs = _ensure_usage_questions(word, word_id, wd)
        q = usage_qs.get(q_type)

    if not q:
        raise HTTPException(404, f"could not generate question of type '{q_type}'")

    streak = int(wp.get("usage_streak", 0))
    return {
        "word":        word,
        "reading":     wd["reading"],
        "meaning":     wd.get("meaning", ""),
        "streak":      streak,
        "q_type":      q["q_type"],
        "question":    q.get("question", ""),
        "audio_word":  q.get("audio_word", ""),
        "options":     _question_options(q),
        "answer":      q["answer"],   # included so client can verify locally after reveal
        "explanation": q.get("explanation", ""),
    }


class TestAnswerRequest(BaseModel):
    word: str
    q_type: str
    answer: str


@router.post("/api/test/answer")
async def submit_test_answer(req: TestAnswerRequest, request: Request):
    wd = _word_data(req.word)
    if not wd:
        raise HTTPException(404, "word not found")

    # For usage types, verify against cached DB question
    if req.q_type in ("fill_word", "fill_particle"):
        word_id = get_word_id(req.word)
        if not word_id:
            raise HTTPException(404, "word not found")
        cached = get_test_questions(word_id)
        if req.q_type not in cached:
            raise HTTPException(404, f"question '{req.q_type}' not cached")
        correct_answer = cached[req.q_type]["answer"]
        explanation = cached[req.q_type].get("explanation", "")
    else:
        # For MCQ types, regenerate on-the-fly to get correct answer
        if req.q_type == "meaning_mcq":
            q = _make_meaning_mcq(req.word, wd)
        elif req.q_type == "reading_mcq":
            q = _make_reading_mcq(req.word, wd)
        elif req.q_type == "listening_mcq":
            q = _make_listening_mcq(req.word, wd)
        elif req.q_type == "context_mcq":
            q = _make_context_mcq(req.word, wd)
        else:
            raise HTTPException(422, f"unknown q_type '{req.q_type}'")
        if not q:
            raise HTTPException(500, "could not generate question")
        correct_answer = q["answer"]
        explanation = ""

    user_id = resolve_user_id(request)
    correct = req.answer == correct_answer
    result = record_test_answer(user_id, req.word, req.q_type, correct)

    # Determine next q_type after this answer
    wp = get_word_status(user_id, req.word)
    next_q_type = _next_q_type(wp, wd)

    # All tests passed → mastered immediately (no FSRS stability gate)
    if next_q_type is None and check_all_tested(wp, wd.get("pos", "")):
        from progress_store import update_word_status
        update_word_status(user_id, req.word, {"is_mastered": 1})

    return {
        "correct":        correct,
        "correct_answer": correct_answer,
        "explanation":    explanation,
        "next_q_type":    next_q_type,
        **result,
    }


class GenerateRequest(BaseModel):
    word: str


@router.post("/api/test/generate")
async def generate_question(req: GenerateRequest):
    """AI-generate and cache a fill_particle question for a word."""
    wd = _word_data(req.word)
    if not wd:
        raise HTTPException(404, "word not found")
    word_id = get_word_id(req.word)
    if not word_id:
        raise HTTPException(404, "word not in DB")
    if not wd.get("collocation"):
        raise HTTPException(422, "word has no collocation data")

    result = await _generate_ai_fill_particle(req.word, wd["reading"], wd["collocation"])
    if not result:
        raise HTTPException(500, "AI generation failed")

    save_test_question(
        word_id, "fill_particle",
        result["question"], result["answer"], result["distractors"],
        result.get("explanation", ""),
    )
    return {"ok": True, "question": result}


@router.get("/api/debug/fill-question")
async def debug_fill_question(q_type: str = "fill_word"):
    """Return a randomly generated fill_word or fill_particle question (bypasses progress)."""
    if q_type not in ("fill_word", "fill_particle"):
        raise HTTPException(422, "q_type must be fill_word or fill_particle")
    vocab = _get_vocab()
    candidates = [w for w in vocab if w.get("collocation") and needs_usage_test(w.get("pos", ""))]
    random.shuffle(candidates)
    for wd in candidates[:50]:
        word = wd["word"]
        if q_type == "fill_word":
            pool = _distractor_pool(wd.get("pos", ""), word, "word")
            if len(pool) < 3:
                continue
            q = make_fill_word_question(word, wd["collocation"], pool[:3], wd.get("examples", "") or "")
        else:
            q = make_fill_particle_question(wd["collocation"], wd.get("examples", "") or "")
        if q:
            return {
                "word":    word,
                "reading": wd["reading"],
                "meaning": wd.get("meaning", ""),
                "pos":     wd.get("pos", ""),
                **q,
            }
    raise HTTPException(500, "could not generate question")


async def _generate_ai_fill_particle(word: str, reading: str, collocation: str) -> dict | None:
    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None

    client = AsyncOpenAI(api_key=api_key)
    prompt = (
        f"为JLPT N2单词「{word}」（{reading}）生成一道填助词题。\n"
        f"搭配例句: {collocation}\n\n"
        "从例句中选一个包含该单词的短句，把其中的助词替换成空白（__）。\n"
        "只输出JSON：\n"
        '{"question":"感想__述べる","answer":"を","distractors":["に","が","で"],'
        '"explanation":"「感想を述べる」は他動詞構造で「を」が目的語を示す。"}'
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=150,
        )
        text = resp.choices[0].message.content.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return None
