"""
从手动收集的日文文章中提取例句，匹配 N2 词汇。

用法：
    python tools/extract_sentences.py                        # 预览，不写库
    python tools/extract_sentences.py --save                 # 写入数据库
    python tools/extract_sentences.py --file data/articles.txt  # 指定文件

文件格式（articles.txt）：
    1
    第一篇文章内容...

    2
    第二篇文章内容...
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH      = PROJECT_ROOT / "data" / "n2.db"
DEFAULT_FILE = PROJECT_ROOT / "articles.txt"


def load_articles(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    # 以 001. / 002. 开头的行作为文章分隔符（支持半角/全角句点）
    parts = re.split(r"^\s*\d{3}[.．]", text, flags=re.MULTILINE)
    articles = [p.strip() for p in parts if p.strip()]
    return articles


def split_sentences(text: str) -> list[str]:
    # 按句号/感叹/问号切句，保留标点
    raw = re.split(r"(?<=[。！？])", text)
    sentences = []
    for s in raw:
        s = s.strip()
        # 去掉HTML残留、括号注释
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"[（(][^）)]{1,20}[）)]", "", s)
        s = s.strip()
        if len(s) >= 10 and re.search(r"[。！？]$", s):
            sentences.append(s)
    return sentences


def is_clean(s: str) -> bool:
    if re.match(r"^[、。\s・•]", s):  return False
    if re.search(r"(注\d|※\d|▶|►|【|】|◆)", s): return False
    if len(s) > 80: return False   # 太长的句子上下文依赖强，选择题不好用
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--save", action="store_true", help="写入数据库")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    if not args.file.exists():
        print(f"文件不存在：{args.file}")
        print(f"请把文章粘贴到 {args.file}，格式见脚本头部注释。")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 加载所有 N2 词
    words = conn.execute(
        "SELECT id, word FROM words WHERE jlpt_level=2"
    ).fetchall()
    word_list = [(r["id"], r["word"]) for r in words]
    print(f"N2 词汇：{len(word_list)} 个")

    # 解析文章
    articles = load_articles(args.file)
    print(f"读取文章：{len(articles)} 篇")

    # 收集所有合格句子
    all_sentences: list[str] = []
    for article in articles:
        for s in split_sentences(article):
            if is_clean(s):
                all_sentences.append(s)
    print(f"合格句子：{len(all_sentences)} 条")
    print()

    # 逐词匹配
    matched: dict[int, tuple[str, str]] = {}   # word_id -> (word, sentence)
    for word_id, word in word_list:
        best = None
        for s in all_sentences:
            if word in s:
                # 优先选包含词的句子里最短的（上下文够用但不复杂）
                if best is None or len(s) < len(best):
                    best = s
        if best:
            matched[word_id] = (word, best)

    print(f"匹配到：{len(matched)} / {len(word_list)} 词  "
          f"({len(matched)/len(word_list)*100:.1f}%)")
    print()

    # 预览前 20 条
    print("=== 预览（前20条）===")
    for word_id, (word, sent) in list(matched.items())[:20]:
        print(f"[{word}] {sent.replace(word, '＿＿', 1)}")

    # 写库
    if args.save:
        updated = 0
        for word_id, (word, sent) in matched.items():
            conn.execute(
                """INSERT INTO word_sentences (word_id, sentence, source)
                   VALUES (?, ?, 'manual_article')
                   ON CONFLICT(word_id) DO UPDATE SET
                     sentence = excluded.sentence,
                     source   = excluded.source""",
                (word_id, sent),
            )
            updated += 1
        conn.commit()
        print(f"\n已写入 word_sentences 表：{updated} 条")
    else:
        print("\n（预览模式，未写库。加 --save 参数写入）")

    conn.close()


if __name__ == "__main__":
    main()
