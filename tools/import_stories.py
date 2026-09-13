"""
把审核/打磨后的故事 TSV 文件导入回数据库。

用法：
    python tools/import_stories.py data/stories_export.tsv          # 覆盖更新所有行
    python tools/import_stories.py data/stories_export.tsv --dry-run # 预览，不写库

规则：
- 以 word_id 为主键匹配
- story 列为空 → 跳过该行（保留原有故事）
- story 列有内容 → 覆盖写入 memory_stories，is_official=1
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "n2.db"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tsv", help="要导入的 TSV 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    tsv_path = Path(args.tsv)
    if not tsv_path.exists():
        print(f"文件不存在：{tsv_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    lines = tsv_path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    idx = {h: i for i, h in enumerate(header)}

    updated = skipped = 0
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < len(header):
            continue
        word_id = int(parts[idx["word_id"]])
        word    = parts[idx["word"]]
        story   = parts[idx["story"]].strip()

        if not story:
            skipped += 1
            continue

        print(f"  [{word}] {story[:40]}…" if len(story) > 40 else f"  [{word}] {story}")
        if not args.dry_run:
            conn.execute(
                """INSERT INTO memory_stories (word_id, user_id, method, content, status, is_official)
                   VALUES (?, 'system', 'ai_generated', ?, 'approved', 1)
                   ON CONFLICT(word_id, user_id) DO UPDATE SET
                     content = excluded.content""",
                (word_id, story),
            )
        updated += 1

    if not args.dry_run:
        conn.commit()
    conn.close()

    print(f"\n{'[dry-run] ' if args.dry_run else ''}完成：更新 {updated} 条，跳过空故事 {skipped} 条")


if __name__ == "__main__":
    main()
