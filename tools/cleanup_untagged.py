"""
清理 jlpt_level 无标注的词：
1. 删除可能形动词（走れる、歌える 等——原形已在库中，活用形不应单独成词条）
2. 剩余无标注词全部标 N2（均来自N2真题或新完全マスター教材）

注：同音字合并（挨拶/あいさつ）风险高（よる=夜 vs よる=因る 等），跳过。

用法：
    python tools/cleanup_untagged.py           # 预览
    python tools/cleanup_untagged.py --apply   # 实际执行
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "n2.db"

# 明确保留的"看似可能形但有独立含义"的词
KEEP_WORDS = {"知れる", "見られる", "考えられる", "言える", "感じられる", "行える", "恐れる"}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def find_potential_forms(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    """找可能形动词：word和reading都以れる/られる/える结尾，且原形在库中存在"""
    rows = conn.execute(
        "SELECT id, word, reading, meaning FROM words WHERE jlpt_level IS NULL"
    ).fetchall()

    all_readings = {r[0] for r in conn.execute("SELECT reading FROM words").fetchall()}
    all_words    = {r[0] for r in conn.execute("SELECT word FROM words").fetchall()}

    to_delete: list[tuple[int, str, str]] = []

    for row in rows:
        wid, word, reading, meaning = row["id"], row["word"], row["reading"], row["meaning"] or ""
        if word in KEEP_WORDS:
            continue

        # word 和 reading 都必须以可能形结尾
        ends_reru   = word.endswith("れる") and reading.endswith("れる")
        ends_rareru = word.endswith("られる") and reading.endswith("られる")
        ends_eru    = (word.endswith("える") and reading.endswith("える")
                       and len(word) > 2 and not word.endswith("答える"))

        if not (ends_reru or ends_rareru or ends_eru):
            continue

        # 尝试还原原形
        candidates: list[str] = []

        if ends_rareru:
            candidates += [word[:-3] + "る", reading[:-3] + "る"]
        elif ends_reru:
            candidates += [word[:-2] + "る", reading[:-2] + "る"]
        elif ends_eru:
            stem_w = word[:-2]
            stem_r = reading[:-2]
            u_map = {"え":"う","け":"く","せ":"す","て":"つ","ね":"ぬ",
                     "へ":"ふ","め":"む","れ":"る","げ":"ぐ","ぜ":"ず",
                     "で":"づ","べ":"ぶ","ぺ":"ぷ"}
            if stem_r and stem_r[-1] in u_map:
                candidates.append(stem_r[:-1] + u_map[stem_r[-1]] + "る")
            if stem_w:
                candidates.append(stem_w + "う")

        base_found = any(c in all_readings or c in all_words for c in candidates if c)
        if base_found:
            to_delete.append((wid, word, reading))

    return to_delete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    conn = get_conn()

    # 第一步：找可能形
    pot_forms = find_potential_forms(conn)
    print(f"\n【第一步】可能形动词：找到 {len(pot_forms)} 个")
    for wid, word, reading in pot_forms:
        print(f"  删除: {word}({reading})")

    # 第二步：统计剩余无标注
    del_ids = {wid for wid, _, _ in pot_forms}
    remaining = conn.execute(
        "SELECT COUNT(*) FROM words WHERE jlpt_level IS NULL"
    ).fetchone()[0] - len(del_ids)

    print(f"\n【第二步】剩余无标注词：{remaining} 个 → 全部标 N2")

    print(f"\n=== 汇总 ===")
    print(f"  删除可能形：{len(pot_forms)} 个")
    print(f"  标注 N2：   {remaining} 个")

    if not args.apply:
        print("\n[预览模式] 加 --apply 参数才会实际修改")
        conn.close()
        return

    # 执行删除
    if del_ids:
        ph = ",".join("?" * len(del_ids))
        ids = list(del_ids)
        for tbl in ("user_word_status", "memory_stories", "word_test_questions"):
            conn.execute(f"DELETE FROM {tbl} WHERE word_id IN ({ph})", ids)
        conn.execute(f"DELETE FROM words WHERE id IN ({ph})", ids)

    # 标注 N2
    conn.execute("UPDATE words SET jlpt_level = 2 WHERE jlpt_level IS NULL")
    conn.commit()
    conn.close()

    # 最终统计
    conn2 = get_conn()
    print("\n=== 清理后等级分布 ===")
    total = 0
    for lvl, n in conn2.execute(
        "SELECT jlpt_level, COUNT(*) FROM words GROUP BY jlpt_level ORDER BY jlpt_level DESC"
    ).fetchall():
        label = f"N{lvl}" if lvl else "无标注"
        print(f"  {label}: {n}词")
        total += n
    print(f"  总计: {total}词")
    conn2.close()


if __name__ == "__main__":
    main()
