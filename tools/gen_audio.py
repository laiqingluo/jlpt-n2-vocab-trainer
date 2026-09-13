"""
批量预生成所有单词的 Azure TTS 音频，缓存到 backend/cache/word/。

用法：
    python tools/gen_audio.py               # 生成全部（跳过已有缓存）
    python tools/gen_audio.py --level 2     # 只生成 N2 词
    python tools/gen_audio.py --limit 100   # 只生成前100个（测试用）
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH      = PROJECT_ROOT / "data" / "n2.db"
CACHE_DIR    = PROJECT_ROOT / "backend" / "cache" / "word"
ENV_PATH     = PROJECT_ROOT / "backend" / ".env"

# 加载 .env
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

CACHE_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
from tts_provider import generate_word_speech  # noqa: E402


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_readings(level: int | None, limit: int) -> list[tuple[str, str]]:
    """返回 [(word, reading), ...] 去重后的列表，按频率排序。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    level_clause = f"AND jlpt_level = {level}" if level else ""
    rows = conn.execute(f"""
        SELECT word, reading FROM words
        WHERE reading IS NOT NULL AND reading != ''
        {level_clause}
        ORDER BY count DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    # 以 reading 去重（同音词只生成一次）
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for r in rows:
        if r["reading"] not in seen:
            seen.add(r["reading"])
            result.append((r["word"], r["reading"]))
    return result


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--limit", type=int, default=99999)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    pairs = get_readings(args.level, args.limit)

    # 过滤已有缓存
    todo = [(w, r) for w, r in pairs if not (CACHE_DIR / f"{_md5(r)}.mp3").exists()]
    already = len(pairs) - len(todo)

    print(f"总计: {len(pairs)}  已缓存: {already}  待生成: {len(todo)}")
    if not todo:
        print("全部已缓存，无需重新生成。")
        return

    ok = fail = 0
    for i, (word, reading) in enumerate(todo, 1):
        cache_path = CACHE_DIR / f"{_md5(reading)}.mp3"
        try:
            audio = await generate_word_speech(reading)
            cache_path.write_bytes(audio)
            ok += 1
            if i % 50 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] {word}（{reading}）✓")
        except Exception as e:
            fail += 1
            print(f"  [{i}/{len(todo)}] {word}（{reading}）失败: {e}")
        await asyncio.sleep(0.3)  # Azure 限速保护

    print(f"\n完成: 成功 {ok}  失败 {fail}  缓存目录: {CACHE_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
