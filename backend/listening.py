from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth_router import resolve_user_id
from progress_store import (
    get_all_statuses,
    get_session,
    get_word_status,
    save_session,
    update_word_status,
)
from vocab_store import load_n2_vocab


router = APIRouter()
N2_VOCAB = load_n2_vocab()

SESSION_KEY = "n2_listening"

LISTEN_MASTERY_LABELS = {
    "unknown":      "不认识",
    "recall_fail":  "想不起来",
    "passive_known": "看了能懂",
    "known":        "认识",
}
_MEANING_TO_LISTEN = {
    "known_fast": "known",
    "known_slow": "passive_known",
    "unknown":    "unknown",
}
LISTEN_DAILY_LIMITS = {
    "unknown":      2,
    "recall_fail":  2,
    "passive_known": 1,
    "known":        1,
}
LISTEN_COOLDOWN_DAYS = {
    "unknown":      2 / 24,
    "recall_fail":  1,
    "passive_known": 3,
    "known":        7,
}
LISTEN_DAILY_QUOTA = {
    "unknown":      70,
    "recall_fail":  55,
    "passive_known": 45,
    "known":        20,
}
LISTEN_ROUND_QUOTA = {
    "unknown":      16,
    "recall_fail":  12,
    "passive_known": 8,
    "known":        4,
}
LISTEN_NEIGHBORS = {
    "unknown":      ["recall_fail", "passive_known", "known"],
    "recall_fail":  ["unknown", "passive_known", "known"],
    "passive_known": ["recall_fail", "known", "unknown"],
    "known":        ["passive_known", "recall_fail", "unknown"],
}


class ListeningFeedbackRequest(BaseModel):
    word_id: str
    feedback: str


class ListeningHeardRequest(BaseModel):
    word_id: str


def today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def meaning_summary(text: str) -> str:
    if not text:
        return "暂无释义"
    parts: list[str] = []
    for segment in re.split(r"(?=[①②③④⑤⑥⑦⑧⑨⑩])", text):
        rest = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", segment).strip()
        if not rest:
            continue
        cn = rest.split("（", 1)[0].strip()
        if cn:
            parts.append(cn)
    return "；".join(parts[:3]) or text.split("（", 1)[0].strip() or "暂无释义"


def _resolve_listen_mastery(wp: dict) -> str:
    mastery = wp.get("listen_mastery", "unknown")
    if mastery in LISTEN_MASTERY_LABELS:
        return mastery
    return _MEANING_TO_LISTEN.get(wp.get("meaning_status", "unknown"), "unknown")


def _is_learned(wp: dict) -> bool:
    return wp.get("meaning_status", "unknown") != "unknown" or (wp.get("review_count") or 0) > 0


def _today_listen_count(wp: dict, today: str) -> int:
    if wp.get("listen_today_date") != today:
        return 0
    return int(wp.get("listen_today_count") or 0)


def _is_available(wp: dict, now: datetime, recent_ids: list[str], word: str) -> bool:
    if not _is_learned(wp):
        return False
    if word in recent_ids[:10]:
        return False
    mastery = _resolve_listen_mastery(wp)
    if _today_listen_count(wp, now.date().isoformat()) >= LISTEN_DAILY_LIMITS[mastery]:
        return False
    due = wp.get("listen_due_at")
    if due:
        try:
            due_dt = datetime.fromisoformat(due)
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            if due_dt > now:
                return False
        except Exception:
            pass
    return True


def _shuffle(items: list) -> list:
    result = list(items)
    random.shuffle(result)
    return result


def _select_by_quota(items: list[dict], quota: dict[str, int]) -> list[dict]:
    buckets: dict[str, list] = {m: [] for m in LISTEN_MASTERY_LABELS}
    for item in items:
        buckets.setdefault(item["listen_mastery"], []).append(item)

    selected: list[dict] = []
    used: set[str] = set()
    shortages: dict[str, int] = {}

    for mastery, count in quota.items():
        candidates = [w for w in buckets.get(mastery, []) if w["word"] not in used]
        picks = _shuffle(candidates)[:count]
        selected.extend(picks)
        used.update(w["word"] for w in picks)
        if len(picks) < count:
            shortages[mastery] = count - len(picks)

    for mastery, shortage in shortages.items():
        for neighbor in LISTEN_NEIGHBORS.get(mastery, []):
            if shortage <= 0:
                break
            candidates = [w for w in buckets.get(neighbor, []) if w["word"] not in used]
            picks = _shuffle(candidates)[:shortage]
            selected.extend(picks)
            used.update(w["word"] for w in picks)
            shortage -= len(picks)

    return selected


def _build_learned_items(statuses: dict[str, dict]) -> list[dict]:
    items = []
    for word in N2_VOCAB:
        w = word["word"]
        wp = statuses.get(w, {})
        if not _is_learned(wp):
            continue
        items.append({
            "word":         w,
            "reading":      word["reading"],
            "meaning":      meaning_summary(word["meaning"]),
            "count":        word["count"],
            "listen_mastery": _resolve_listen_mastery(wp),
            "last_review_at": wp.get("last_review_at"),
        })
    return items


def _listen_response(item: dict) -> dict:
    return {
        "word_id":      item["word"],
        "word":         item["word"],
        "reading":      item.get("reading", ""),
        "meaning":      item.get("meaning") or "暂无释义",
        "listen_mastery": item["listen_mastery"],
        "mastery_label": LISTEN_MASTERY_LABELS[item["listen_mastery"]],
        "audio_url":    "/api/word_audio",
    }


@router.get("/api/listening/session")
async def listening_session(request: Request):
    user_id  = resolve_user_id(request)
    statuses = get_all_statuses(user_id)
    state    = get_session(user_id, SESSION_KEY)
    today    = today_str()
    now      = datetime.now(timezone.utc)
    recent   = state.get("recent_listen_word_ids", [])

    learned   = _build_learned_items(statuses)
    available = [item for item in learned if _is_available(statuses.get(item["word"], {}), now, recent, item["word"])]

    if state.get("daily_pool_date") != today:
        pool_words = [item["word"] for item in _select_by_quota(available, LISTEN_DAILY_QUOTA)]
        used = set(pool_words)
        recent_learned = sorted(
            [item for item in available if item["word"] not in used],
            key=lambda x: x.get("last_review_at") or "",
            reverse=True,
        )[:10]
        pool_words.extend(item["word"] for item in recent_learned)
        state["daily_pool_date"] = today
        state["daily_pool"] = pool_words
        save_session(user_id, SESSION_KEY, state)

    by_word    = {item["word"]: item for item in learned}
    pool_items = [by_word[w] for w in state.get("daily_pool", []) if w in by_word]
    pool_avail = [item for item in pool_items if _is_available(statuses.get(item["word"], {}), now, recent, item["word"])]
    session    = _shuffle(_select_by_quota(pool_avail, LISTEN_ROUND_QUOTA))[:40]

    replay = False
    if not session and pool_items:
        session = _shuffle(pool_items)[:40]
        replay  = True

    return {
        "session_size":    len(session),
        "daily_pool_size": len(pool_items),
        "items":           [_listen_response(item) for item in session],
        "replay":          replay,
        "message": (
            "暂无新词，正在循环今日推荐" if replay
            else ("" if session else "今天可听词已经完成，可以稍后再来。")
        ),
    }


@router.post("/api/listening/feedback")
async def listening_feedback(req: ListeningFeedbackRequest, request: Request):
    if req.feedback not in LISTEN_MASTERY_LABELS:
        raise HTTPException(422, "feedback 必须为 unknown/recall_fail/passive_known/known")

    user_id = resolve_user_id(request)
    now   = datetime.now(timezone.utc)
    today = now.date().isoformat()
    wp    = get_word_status(user_id, req.word_id)

    update_word_status(user_id, req.word_id, {
        "listen_mastery":     req.feedback,
        "listen_count":       int(wp.get("listen_count") or 0) + 1,
        "listen_today_count": _today_listen_count(wp, today) + 1,
        "listen_today_date":  today,
        "last_listened_at":   now.isoformat(),
        "listen_due_at":      (now + timedelta(days=LISTEN_COOLDOWN_DAYS[req.feedback])).isoformat(),
    })

    state  = get_session(user_id, SESSION_KEY)
    recent = [w for w in state.get("recent_listen_word_ids", []) if w != req.word_id]
    state["recent_listen_word_ids"] = [req.word_id, *recent][:20]
    save_session(user_id, SESSION_KEY, state)

    return {
        "ok":           True,
        "listen_mastery": req.feedback,
        "listen_due_at":  (now + timedelta(days=LISTEN_COOLDOWN_DAYS[req.feedback])).isoformat(),
    }


@router.post("/api/listening/heard")
async def listening_heard(req: ListeningHeardRequest, request: Request):
    user_id = resolve_user_id(request)
    now     = datetime.now(timezone.utc)
    today   = now.date().isoformat()
    wp      = get_word_status(user_id, req.word_id)
    mastery = _resolve_listen_mastery(wp)

    update_word_status(user_id, req.word_id, {
        "listen_mastery":     mastery,
        "listen_count":       int(wp.get("listen_count") or 0) + 1,
        "listen_today_count": _today_listen_count(wp, today) + 1,
        "listen_today_date":  today,
        "last_listened_at":   now.isoformat(),
        "listen_due_at":      (now + timedelta(days=LISTEN_COOLDOWN_DAYS[mastery])).isoformat(),
    })

    state  = get_session(user_id, SESSION_KEY)
    recent = [w for w in state.get("recent_listen_word_ids", []) if w != req.word_id]
    state["recent_listen_word_ids"] = [req.word_id, *recent][:20]
    save_session(user_id, SESSION_KEY, state)

    return {
        "ok":           True,
        "listen_mastery": mastery,
        "listen_due_at":  (now + timedelta(days=LISTEN_COOLDOWN_DAYS[mastery])).isoformat(),
    }
