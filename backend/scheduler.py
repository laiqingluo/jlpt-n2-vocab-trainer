"""FSRS-4.5 scheduler."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# FSRS-4.5 default weights (19 params)
W = [
    0.4072, 1.1829, 3.1262, 15.4722,   # w[0-3]  initial stability per rating
    7.2102, 0.5316,                      # w[4-5]  initial difficulty
    1.0651, 0.0589,                      # w[6-7]  difficulty update
    1.5330, 0.1544, 1.0070,              # w[8-10] recall stability
    1.9330, 0.1100, 0.2900, 2.2700,     # w[11-14] forget stability
    0.0800, 2.9898,                      # w[15-16] hard/easy multiplier
    0.5100, 0.4300,                      # w[17-18] (unused in 4.5)
]

DECAY             = -0.5
FACTOR            = 0.9 ** (1 / DECAY) - 1   # ≈ 19/81
DESIRED_RETENTION = 0.9
MAX_INTERVAL      = 36500   # days (~100 yr cap)

RATING_MAP = {"again": 1, "hard": 2, "good": 3, "known": 4}

# Kept for validation in app.py (same keys, values unused)
REVIEW_INTERVALS: dict[str, list[float]] = {
    "again": [1 / 144, 1, 3],
    "hard":  [1, 3, 7],
    "good":  [3, 7, 15],
    "known": [15, 30, 60],
}


# ── Core FSRS formulas ────────────────────────────────────────────────────

def _forgetting_curve(elapsed: float, s: float) -> float:
    return (1 + FACTOR * elapsed / s) ** DECAY


def _init_stability(rating: int) -> float:
    return max(W[rating - 1], 0.1)


def _init_difficulty(rating: int) -> float:
    return min(max(W[4] - math.exp(W[5] * (rating - 1)) + 1, 1.0), 10.0)


def _next_difficulty(d: float, rating: int) -> float:
    delta = -W[6] * (rating - 3)
    d_prime = d + delta * ((10 - d) / 9 if delta > 0 else (d - 1) / 9)
    d0_easy = _init_difficulty(4)
    return min(max(W[7] * d0_easy + (1 - W[7]) * d_prime, 1.0), 10.0)


def _recall_stability(d: float, s: float, r: float, rating: int) -> float:
    hard  = W[15] if rating == 2 else 1.0
    easy  = W[16] if rating == 4 else 1.0
    return max(
        s * (math.exp(W[8]) * (11 - d) * s ** (-W[9])
             * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1),
        0.1,
    )


def _forget_stability(d: float, s: float, r: float) -> float:
    return max(
        W[11] * d ** (-W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r)),
        0.1,
    )


def _interval(s: float) -> int:
    raw = s / FACTOR * (DESIRED_RETENTION ** (1 / DECAY) - 1)
    return min(max(round(raw), 1), MAX_INTERVAL)


# ── Public API ────────────────────────────────────────────────────────────

def next_review(entry: dict, result: str) -> tuple[str, bool, int]:
    """Return (next_review_at_iso, is_mastered, _unused).

    Mutates entry in-place to persist fsrs_stability and fsrs_difficulty.
    """
    rating = RATING_MAP.get(result, 3)
    now    = datetime.now(timezone.utc)

    s = entry.get("fsrs_stability")
    d = entry.get("fsrs_difficulty")

    if s is None:
        # First review (or migrating from old fixed-interval records)
        new_s = _init_stability(rating)
        new_d = _init_difficulty(rating)
    else:
        last = entry.get("last_reviewed_at") or entry.get("updated_at", "")
        try:
            elapsed = max((now - datetime.fromisoformat(last)).total_seconds() / 86400, 0.0)
        except Exception:
            elapsed = 0.0

        r     = _forgetting_curve(elapsed, s)
        new_d = _next_difficulty(d, rating)
        new_s = _forget_stability(d, s, r) if rating == 1 else _recall_stability(d, s, r, rating)

    interval = _interval(new_s)
    next_dt  = now + timedelta(days=interval)

    entry["fsrs_stability"]  = round(new_s, 4)
    entry["fsrs_difficulty"] = round(new_d, 4)

    is_mastered = interval >= 180 and rating >= 3
    return next_dt.isoformat(), is_mastered, 0
