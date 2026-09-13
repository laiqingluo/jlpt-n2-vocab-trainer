"""
把 memory_stories 官方故事导出为 TSV 文件，方便在聊天窗口批量审核、打磨。

用法：
    python tools/export_stories.py                    # 导出全部，输出到 data/stories_export.tsv
    python tools/export_stories.py --level 2          # 只导出 N2 词
    python tools/export_stories.py --no-story         # 导出还没有故事的词（用于补充生成）

格式（制表符分隔）：
    word_id  word  reading  pos  meaning  story

导入时用 import_stories.py 读取修改后的文件。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "n2.db"
DEFAULT_OUT = PROJECT_ROOT / "data" / "stories_export.tsv"


def short_meaning(text: str) -> str:
    if not text:
        return ""
    import re
    m = re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]\s*([^（①②③④⑤⑥⑦⑧⑨⑩]{1,30})", text)
    if m:
        return m.group(1).split("（")[0].strip()
    return text.split("（")[0][:30].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level",    type=int, default=None, help="只导出指定JLPT等级")
    parser.add_argument("--no-story", action="store_true",    help="只导出还没有故事的词")
    parser.add_argument("--out",      type=str, default=str(DEFAULT_OUT), help="输出路径")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    level_clause = f"AND w.jlpt_level = {args.level}" if args.level else ""

    if args.no_story:
        rows = conn.execute(f"""
            SELECT w.id, w.word, w.reading, w.pos, w.meaning, w.meaning_detail,
                   NULL as story
            FROM words w
            LEFT JOIN memory_stories ms ON ms.word_id = w.id AND ms.is_official = 1
            WHERE ms.id IS NULL {level_clause}
            ORDER BY w.count DESC
        """).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT w.id, w.word, w.reading, w.pos, w.meaning, w.meaning_detail,
                   ms.content as story
            FROM words w
            LEFT JOIN memory_stories ms ON ms.word_id = w.id AND ms.is_official = 1
            {('WHERE w.jlpt_level = ' + str(args.level)) if args.level else ''}
            ORDER BY w.count DESC
        """).fetchall()

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write("word_id\tword\treading\tpos\tmeaning\tstory\n")
        for r in rows:
            meaning = short_meaning(r["meaning_detail"] or r["meaning"] or "")
            story = (r["story"] or "").replace("\n", " ").replace("\t", " ")
            f.write(f"{r['id']}\t{r['word']}\t{r['reading']}\t{r['pos'] or ''}\t{meaning}\t{story}\n")

    conn.close()
    print(f"导出完成：{len(rows)} 条 → {out_path}")


if __name__ == "__main__":
    main()
