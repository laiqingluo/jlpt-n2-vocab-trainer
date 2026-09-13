from __future__ import annotations

from datetime import datetime, date, timezone
from pathlib import Path

from db import get_conn, init_db

# init_db must run before any module that touches the DB is imported
init_db()

from fastapi import FastAPI, HTTPException, Request, Depends  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from audio import router as audio_router  # noqa: E402
from auth_router import router as auth_router  # noqa: E402
from listening import router as listening_router  # noqa: E402
from test_router import router as test_router  # noqa: E402
from test_store import check_all_tested  # noqa: E402
from progress_store import (  # noqa: E402
    DEFAULT_USER_ID,
    get_all_statuses,
    get_session,
    get_word_status,
    save_session,
    update_word_status,
)
from scheduler import REVIEW_INTERVALS, next_review  # noqa: E402
from vocab_store import load_n2_vocab  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title="JLPT N2 Trainer", version="0.3.0")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Resolve user_id from Bearer token; fall back to 'default'."""
    user_id = DEFAULT_USER_ID
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        row = get_conn().execute(
            "SELECT user_id FROM auth_tokens WHERE token=?", (token,)
        ).fetchone()
        if row:
            user_id = row["user_id"]
    request.state.user_id = user_id
    return await call_next(request)


def _uid(request: Request) -> str:
    return getattr(request.state, "user_id", DEFAULT_USER_ID)


app.include_router(audio_router)
app.include_router(auth_router)
app.include_router(listening_router)
app.include_router(test_router)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

N2_VOCAB: list[dict] = load_n2_vocab()
if not N2_VOCAB:
    print("WARNING: words table is empty. Run:  python tools/migrate_to_sqlite.py")

_RESULT_TO_MEANING = {
    "known": "known_fast",
    "good":  "known_slow",
    "hard":  "unknown",
    "again": "unknown",
}

_MEANING_TO_RESULT = {
    "known_fast": "known",
    "known_slow": "good",
}


class N2ReviewRequest(BaseModel):
    word: str
    result: str
    dim: str = "recognition"


class ScreeningItem(BaseModel):
    word: str
    result: str


class ScreeningBatch(BaseModel):
    results: list[ScreeningItem]


def _status_to_api(wp: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    next_at = wp.get("next_review_at")
    is_mastered = bool(wp.get("is_mastered"))
    is_due = bool(next_at and next_at <= now_iso and not is_mastered)
    meaning_st = wp.get("meaning_status", "unknown")
    return {
        "meaning_status":   meaning_st,
        "reading_status":   wp.get("reading_status", "unknown"),
        "listening_status": wp.get("listening_status", "unknown"),
        "usage_status":     wp.get("usage_status", "unknown"),
        "output_status":    wp.get("output_status", "none"),
        "review_count":     wp.get("review_count", 0),
        "next_review_at":   next_at,
        "is_mastered":      is_mastered,
        "is_due":           is_due,
        "review_result":    _MEANING_TO_RESULT.get(meaning_st),
    }


@app.get("/api/n2/vocab")
async def get_n2_vocab(user_id: str = Depends(_uid)):
    statuses = get_all_statuses(user_id)
    result = []
    for word in N2_VOCAB:
        entry = dict(word)
        entry.update(_status_to_api(statuses.get(word["word"], {})))
        result.append(entry)
    due_count = sum(1 for item in result if item["is_due"])
    new_count  = sum(1 for item in result if item["meaning_status"] == "unknown")
    return {"vocab": result, "total": len(result), "due": due_count, "new": new_count}


@app.get("/api/n2/vocab/stats")
async def get_n2_vocab_stats(user_id: str = Depends(_uid)):
    statuses = get_all_statuses(user_id)
    now_iso  = datetime.now(timezone.utc).isoformat()
    today    = date.today().isoformat()
    total    = len(N2_VOCAB)
    learned  = sum(1 for wp in statuses.values() if wp.get("meaning_status", "unknown") != "unknown")
    due      = sum(
        1 for wp in statuses.values()
        if wp.get("next_review_at") and wp["next_review_at"] <= now_iso and not wp.get("is_mastered")
    )
    switches = {
        "meaning":   sum(1 for wp in statuses.values() if wp.get("meaning_status", "unknown") != "unknown"),
        "reading":   sum(1 for wp in statuses.values() if wp.get("reading_status", "unknown") != "unknown"),
        "listening": sum(1 for wp in statuses.values() if wp.get("listening_status", "unknown") != "unknown"),
        "usage":     sum(1 for wp in statuses.values() if wp.get("usage_status", "unknown") != "unknown"),
        "output":    sum(1 for wp in statuses.values() if wp.get("output_status", "none") != "none"),
    }
    daily    = get_session(user_id, "daily_switches") or {}
    today_switches = int(daily.get("count", 0)) if daily.get("date") == today else 0
    settings = get_session(user_id, "user_settings") or {}
    daily_target = int(settings.get("daily_word_count", 10))
    learned_today = sum(
        1 for wp in statuses.values()
        if wp.get("review_count", 0) == 1
        and wp.get("meaning_status", "unknown") != "unknown"
        and (wp.get("last_review_at") or "")[:10] == today
    )
    # 按等级统计：各等级总词数、已学词数、已掌握词数
    by_level: dict[str, dict] = {}
    mastered = 0
    for w in N2_VOCAB:
        lvl = w.get("jlpt_level")
        key = f"N{lvl}" if lvl else "N?"
        wp = statuses.get(w["word"], {})
        if key not in by_level:
            by_level[key] = {"total": 0, "learned": 0, "mastered": 0}
        by_level[key]["total"] += 1
        if wp.get("meaning_status", "unknown") != "unknown":
            by_level[key]["learned"] += 1
        if check_all_tested(wp, w.get("pos", "")):
            by_level[key]["mastered"] += 1
            mastered += 1
    test_pending = sum(
        1 for w in N2_VOCAB
        if statuses.get(w["word"], {}).get("meaning_status", "unknown") != "unknown"
        and not check_all_tested(statuses.get(w["word"], {}), w.get("pos", ""))
    )
    return {
        "total": total, "due": due, "learned": learned, "new": total - learned,
        "mastered": mastered,
        "switches": switches, "today_switches": today_switches,
        "learned_today": learned_today, "daily_target": daily_target,
        "usage_pending": test_pending, "by_level": by_level,
    }


@app.post("/api/n2/review")
async def n2_review(req: N2ReviewRequest, user_id: str = Depends(_uid)):
    if req.result not in REVIEW_INTERVALS:
        raise HTTPException(422, "result 必须为 known/again/hard/good")

    wp = get_word_status(user_id, req.word)
    fsrs_entry = {
        "fsrs_stability":   wp.get("fsrs_stability"),
        "fsrs_difficulty":  wp.get("fsrs_difficulty"),
        "last_reviewed_at": wp.get("last_review_at"),
    }
    next_iso, is_mastered, _ = next_review(fsrs_entry, req.result)
    now_iso = datetime.now(timezone.utc).isoformat()

    word_data = next((w for w in N2_VOCAB if w["word"] == req.word), None)
    pos = word_data.get("pos", "") if word_data else ""
    actual_mastered = check_all_tested(wp, pos)

    update_word_status(user_id, req.word, {
        "meaning_status":  _RESULT_TO_MEANING[req.result],
        "review_count":    wp.get("review_count", 0) + 1,
        "wrong_count":     wp.get("wrong_count", 0) + (1 if req.result == "again" else 0),
        "last_review_at":  now_iso,
        "next_review_at":  next_iso,
        "fsrs_stability":  fsrs_entry["fsrs_stability"],
        "fsrs_difficulty": fsrs_entry["fsrs_difficulty"],
        "is_mastered":     1 if actual_mastered else 0,
    })
    return {"ok": True, "next_review_at": next_iso, "is_mastered": actual_mastered}


@app.post("/api/n2/screening/batch")
async def screening_batch(req: ScreeningBatch, user_id: str = Depends(_uid)):
    now_iso = datetime.now(timezone.utc).isoformat()
    saved = 0
    for item in req.results:
        if item.result not in REVIEW_INTERVALS:
            continue
        wp = get_word_status(user_id, item.word)
        fsrs_entry = {
            "fsrs_stability":   wp.get("fsrs_stability"),
            "fsrs_difficulty":  wp.get("fsrs_difficulty"),
            "last_reviewed_at": wp.get("last_review_at"),
        }
        next_iso, is_mastered, _ = next_review(fsrs_entry, item.result)
        update_word_status(user_id, item.word, {
            "meaning_status":  _RESULT_TO_MEANING[item.result],
            "review_count":    wp.get("review_count", 0) + 1,
            "last_review_at":  now_iso,
            "next_review_at":  next_iso,
            "fsrs_stability":  fsrs_entry["fsrs_stability"],
            "fsrs_difficulty": fsrs_entry["fsrs_difficulty"],
            "via_screening":   1,
        })
        saved += 1
    return {"ok": True, "saved": saved}


@app.get("/api/screen/queue")
async def get_screen_queue(user_id: str = Depends(_uid)):
    # 申报词汇量 → 筛词起始JLPT等级（从该等级开始筛，更简单的自动标已知）
    # 800=N5基础, 1500=N4基础, 3000=N3基础, 5000=N2基础
    VOCAB_TO_MIN_JLPT = {800: 5, 1500: 4, 3000: 3, 5000: 2}
    settings = get_session(user_id, "user_settings") or {}
    declared = int(settings.get("declared_vocab_level") or 0)
    min_jlpt = VOCAB_TO_MIN_JLPT.get(declared)  # None = 零基础，筛全部

    conn = get_conn()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 把低于申报等级的词自动标为"已知"（仅首次，meaning_status 仍为 unknown 的）
    if min_jlpt is not None:
        skip_rows = conn.execute(
            """SELECT w.id, w.word FROM words w
               LEFT JOIN user_word_status uws ON uws.word_id = w.id AND uws.user_id = ?
               WHERE w.jlpt_level > ?
                 AND COALESCE(uws.meaning_status, 'unknown') = 'unknown'""",
            (user_id, min_jlpt),
        ).fetchall()
        for r in skip_rows:
            conn.execute(
                """INSERT INTO user_word_status
                     (user_id, word_id, meaning_status, via_screening, last_review_at)
                   VALUES (?, ?, 'known_fast', 1, ?)
                   ON CONFLICT(user_id, word_id) DO UPDATE SET
                     meaning_status = 'known_fast', via_screening = 1,
                     last_review_at = excluded.last_review_at""",
                (user_id, r["id"], now_iso),
            )
        conn.commit()

    # 返回筛词队列：申报等级以内（含）且未知的词，按频率排序
    if min_jlpt is not None:
        rows = conn.execute(
            """SELECT w.word, w.reading FROM words w
               LEFT JOIN user_word_status uws ON uws.word_id = w.id AND uws.user_id = ?
               WHERE COALESCE(uws.meaning_status, 'unknown') = 'unknown'
                 AND (w.jlpt_level <= ? OR w.jlpt_level IS NULL)
               ORDER BY w.jlpt_level DESC, w.count DESC, w.word""",
            (user_id, min_jlpt),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT w.word, w.reading FROM words w
               LEFT JOIN user_word_status uws ON uws.word_id = w.id AND uws.user_id = ?
               WHERE COALESCE(uws.meaning_status, 'unknown') = 'unknown'
               ORDER BY w.count DESC, w.word""",
            (user_id,),
        ).fetchall()

    return {"words": [{"word": r["word"], "reading": r["reading"] or ""} for r in rows]}


@app.get("/api/learn/queue")
async def get_learn_queue(user_id: str = Depends(_uid)):
    statuses = get_all_statuses(user_id)
    settings = get_session(user_id, "user_settings") or {}
    daily_limit = int(settings.get("daily_word_count", 10))
    new_words = [
        w for w in N2_VOCAB
        if statuses.get(w["word"], {}).get("meaning_status", "unknown") == "unknown"
    ]
    # N2优先 → N3 → N4 → N5 → N1（N1是超纲词，排最后）
    _LEVEL_PRIORITY = {2: 1, 3: 2, 4: 3, 5: 4, 1: 5}
    new_words.sort(key=lambda w: (
        _LEVEL_PRIORITY.get(w.get("jlpt_level"), 3),
        -(w.get("count") or 0),
    ))
    return {"words": new_words[:daily_limit], "remaining": len(new_words)}


@app.get("/api/learn/story/{word}")
async def get_word_story(word: str):
    row = get_conn().execute(
        """SELECT ms.content, ms.method, ms.is_official
           FROM memory_stories ms
           JOIN words w ON w.id = ms.word_id
           WHERE w.word = ? AND ms.status = 'approved'
           ORDER BY ms.is_official DESC, ms.likes DESC
           LIMIT 1""",
        (word,),
    ).fetchone()
    return {"story": dict(row) if row else None}


class LearnCompleteRequest(BaseModel):
    word: str
    recall: str
    listened: bool = True
    shadowed: bool = True
    saw_example: bool = True


@app.post("/api/learn/complete")
async def learn_complete(req: LearnCompleteRequest, user_id: str = Depends(_uid)):
    if req.recall not in REVIEW_INTERVALS:
        raise HTTPException(422, "recall 必须为 known/good/hard/again")

    wp = get_word_status(user_id, req.word)
    fsrs_entry = {
        "fsrs_stability":   wp.get("fsrs_stability"),
        "fsrs_difficulty":  wp.get("fsrs_difficulty"),
        "last_reviewed_at": wp.get("last_review_at"),
    }
    next_iso, is_mastered, _ = next_review(fsrs_entry, req.recall)
    now_iso = datetime.now(timezone.utc).isoformat()

    meaning_st   = _RESULT_TO_MEANING[req.recall]
    listening_st = "slow"      if req.listened  else wp.get("listening_status", "unknown")
    reading_st   = "uncertain" if req.shadowed  else wp.get("reading_status",   "unknown")

    word_data       = next((w for w in N2_VOCAB if w["word"] == req.word), None)
    has_collocation = bool(word_data and word_data.get("collocation"))
    usage_st = "collocation" if (req.saw_example and has_collocation) else wp.get("usage_status", "unknown")

    old = {k: wp.get(k, "unknown") for k in ("meaning_status", "listening_status", "reading_status", "usage_status")}
    switches_lit = sum([
        old["meaning_status"]   == "unknown" and meaning_st   != "unknown",
        old["listening_status"] == "unknown" and listening_st != "unknown",
        old["reading_status"]   == "unknown" and reading_st   != "unknown",
        old["usage_status"]     == "unknown" and usage_st     != "unknown",
    ])

    pos = word_data.get("pos", "") if word_data else ""
    actual_mastered = check_all_tested(wp, pos)

    update_word_status(user_id, req.word, {
        "meaning_status":   meaning_st,
        "listening_status": listening_st,
        "reading_status":   reading_st,
        "usage_status":     usage_st,
        "review_count":     wp.get("review_count", 0) + 1,
        "wrong_count":      wp.get("wrong_count", 0) + (1 if req.recall == "again" else 0),
        "last_review_at":   now_iso,
        "next_review_at":   next_iso,
        "fsrs_stability":   fsrs_entry["fsrs_stability"],
        "fsrs_difficulty":  fsrs_entry["fsrs_difficulty"],
        "is_mastered":      1 if actual_mastered else 0,
    })

    today = date.today().isoformat()
    daily = get_session(user_id, "daily_switches") or {}
    if daily.get("date") != today:
        daily = {"date": today, "count": 0}
    daily["count"] = int(daily["count"]) + switches_lit
    save_session(user_id, "daily_switches", daily)

    return {"ok": True, "switches_lit": switches_lit}


class UserSettingsRequest(BaseModel):
    declared_vocab_level: int
    daily_word_count: int | None = None


@app.get("/api/user/settings")
async def get_user_settings(user_id: str = Depends(_uid)):
    settings = get_session(user_id, "user_settings")
    return settings if settings else {"declared_vocab_level": None}


@app.post("/api/user/settings")
async def save_user_settings(req: UserSettingsRequest, user_id: str = Depends(_uid)):
    current = get_session(user_id, "user_settings") or {}
    current["declared_vocab_level"] = req.declared_vocab_level
    if req.daily_word_count is not None:
        current["daily_word_count"] = req.daily_word_count
    save_session(user_id, "user_settings", current)
    return {"ok": True}


class BugReportRequest(BaseModel):
    description: str
    screen: str = ""


@app.post("/api/bugs")
async def submit_bug(req: BugReportRequest, request: Request, user_id: str = Depends(_uid)):
    if not req.description.strip():
        raise HTTPException(422, "描述不能为空")
    now = datetime.now(timezone.utc).isoformat()
    ua  = request.headers.get("user-agent", "")
    get_conn().execute(
        "INSERT INTO bug_reports (user_id, screen, description, user_agent, created_at) VALUES (?,?,?,?,?)",
        (user_id, req.screen[:100], req.description.strip()[:2000], ua[:500], now),
    )
    get_conn().commit()
    return {"ok": True}


@app.get("/api/bugs")
async def list_bugs():
    rows = get_conn().execute(
        "SELECT id, user_id, screen, description, user_agent, created_at FROM bug_reports ORDER BY id DESC LIMIT 200"
    ).fetchall()
    return {"bugs": [dict(r) for r in rows]}


@app.get("/")
async def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "frontend/index.html not found")
    return FileResponse(index_path)
