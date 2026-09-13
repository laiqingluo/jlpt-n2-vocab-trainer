"""
通过 Jisho API 为数据库里的词查询 JLPT 等级，写回 words.jlpt_level。

- 只查 jlpt_level IS NULL 或 jlpt_level = 2 (当前兜底N2) 的词
- 限速：每秒最多 3 个并发请求
- 进度保存到 data/_jlpt_fetch_progress.json，可中断后续跑
- 结果写入数据库 jlpt_level 字段（整数：5/4/3/2/1，NULL=未知）

用法：
    python tools/fetch_jlpt_levels.py
    python tools/fetch_jlpt_levels.py --all      # 重新查所有词
    python tools/fetch_jlpt_levels.py --dry-run  # 只打印，不写库
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

import aiohttp

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH      = PROJECT_ROOT / "data" / "n2.db"
PROGRESS_FILE = PROJECT_ROOT / "data" / "_jlpt_fetch_progress.json"

JISHO_API = "https://jisho.org/api/v1/search/words"
LEVEL_MAP  = {"jlpt-n5": 5, "jlpt-n4": 4, "jlpt-n3": 3, "jlpt-n2": 2, "jlpt-n1": 1}
RATE_LIMIT = 3   # 每秒并发上限
BATCH_SAVE = 50  # 每处理多少词保存一次进度


def load_progress() -> dict[str, int | None]:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {}


def save_progress(progress: dict[str, int | None]) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_words(conn: sqlite3.Connection, query_all: bool) -> list[tuple[int, str]]:
    if query_all:
        rows = conn.execute("SELECT id, word FROM words ORDER BY count DESC").fetchall()
    else:
        # 只查还没有可信等级标注的词（NULL 或 兜底N2）
        rows = conn.execute(
            "SELECT id, word FROM words WHERE jlpt_level IS NULL OR jlpt_level = 2 ORDER BY count DESC"
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def parse_level(word: str, data: list[dict]) -> int | None:
    """从 Jisho API 返回的 data 数组里找 JLPT 等级。
    优先精确匹配 word，找不到则用第一条结果。
    """
    def entry_level(entry: dict) -> int | None:
        tags = [LEVEL_MAP[t] for t in entry.get("jlpt", []) if t in LEVEL_MAP]
        return min(tags) if tags else None

    # 1. 精确匹配：word 出现在该条目的任意 japanese[].word 或 reading 字段中
    for entry in data:
        for jp in entry.get("japanese", []):
            if jp.get("word") == word or jp.get("reading") == word:
                lvl = entry_level(entry)
                if lvl is not None:
                    return lvl

    # 2. 退路：用第一条有 JLPT 标注的结果
    for entry in data:
        lvl = entry_level(entry)
        if lvl is not None:
            return lvl

    return None


async def fetch_level(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    word: str,
) -> int | None:
    async with semaphore:
        try:
            async with session.get(
                JISHO_API,
                params={"keyword": word},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                payload = await resp.json()
                return parse_level(word, payload.get("data", []))
        except Exception:
            return None
        finally:
            # 保证不超过 RATE_LIMIT 个/秒
            await asyncio.sleep(1.0 / RATE_LIMIT)


async def run(words: list[tuple[int, str]], dry_run: bool) -> dict[str, int | None]:
    progress = load_progress()
    todo = [(wid, w) for wid, w in words if w not in progress]

    print(f"总词数: {len(words)}  已有进度: {len(progress)}  待查: {len(todo)}")

    conn = sqlite3.connect(str(DB_PATH)) if not dry_run else None
    semaphore = asyncio.Semaphore(RATE_LIMIT)

    start = time.time()
    done = 0

    async def fetch_and_store(word_id: int, word: str) -> None:
        nonlocal done
        level = await fetch_level(session, semaphore, word)
        progress[word] = level
        done += 1

        if done % 10 == 0:
            elapsed = time.time() - start
            speed = done / elapsed
            remaining = (len(todo) - done) / speed if speed > 0 else 0
            print(
                f"\r  {done}/{len(todo)}  {speed:.1f}词/s  剩余~{remaining/60:.1f}min",
                end="", flush=True,
            )

        if done % BATCH_SAVE == 0:
            save_progress(progress)
            if conn:
                _write_batch(conn, progress, todo[:done])

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_and_store(wid, w) for wid, w in todo]
        await asyncio.gather(*tasks)

    print()
    save_progress(progress)
    if conn:
        _write_batch(conn, progress, todo)
        conn.close()

    return progress


def _write_batch(
    conn: sqlite3.Connection,
    progress: dict[str, int | None],
    pairs: list[tuple[int, str]],
) -> None:
    updates = [(progress.get(w), wid) for wid, w in pairs if w in progress]
    conn.executemany("UPDATE words SET jlpt_level = ? WHERE id = ?", updates)
    conn.commit()


def print_stats(progress: dict[str, int | None]) -> None:
    from collections import Counter
    counts = Counter(v for v in progress.values())
    print("\n=== 查询结果统计 ===")
    for lvl in [5, 4, 3, 2, 1, None]:
        label = f"N{lvl}" if lvl else "无标注"
        print(f"  {label}: {counts[lvl]}")
    print(f"  总计: {sum(counts.values())}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="重查所有词，忽略进度")
    parser.add_argument("--dry-run", action="store_true", help="只查询，不写数据库")
    parser.add_argument("--stats", action="store_true", help="只打印已有进度统计")
    args = parser.parse_args()

    if args.stats:
        print_stats(load_progress())
        return

    conn_r = sqlite3.connect(str(DB_PATH))
    words = get_words(conn_r, args.all)
    conn_r.close()

    if not words:
        print("没有需要查询的词。")
        return

    progress = await run(words, dry_run=args.dry_run)
    print_stats(progress)

    if not args.dry_run:
        # 最终写入一次确保全部更新
        conn = sqlite3.connect(str(DB_PATH))
        all_words_in_db = conn.execute("SELECT id, word FROM words").fetchall()
        updates = [
            (progress[w], wid)
            for wid, w in all_words_in_db
            if w in progress and progress[w] is not None
        ]
        conn.executemany("UPDATE words SET jlpt_level = ? WHERE id = ?", updates)
        conn.commit()
        conn.close()
        print(f"\n已写入数据库：{len(updates)} 条")


if __name__ == "__main__":
    asyncio.run(main())
