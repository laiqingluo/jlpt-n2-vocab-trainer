"""
为高频词批量生成记忆故事，写入 memory_stories 表。

策略：
- 优先谐音联想（把日语读音谐音成中文词）
- 汉字和中文意思相同时，重点帮记忆读音
- 2句话以内，生动有画面感

用法：
    python tools/gen_memory_stories.py --limit 20 --dry-run   # 预览，不写库
    python tools/gen_memory_stories.py --limit 300            # 生成前300高频词
    python tools/gen_memory_stories.py --level 2 --limit 100  # 只生成N2词
    python tools/gen_memory_stories.py --word 曖昧            # 指定单词
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "n2.db"
ENV_PATH = PROJECT_ROOT / "backend" / ".env"

# 加载 .env
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_PROMPT = """你是一名专门为中文母语者设计日语单词记忆故事的老师。

规则：
1. 优先谐音：把日语读音谐音成有意思的中文词或短句，再和含义编一个小故事
2. 如果汉字和中文意思完全一样（比如 記念/纪念），只需帮助记忆读音
3. 故事不超过 2 句话，直接输出故事，不要任何前缀或解释
4. 要生动、有画面感，可以搞笑或夸张
5. 用中文写

谐音示例参考（仅供参考，不要照抄）：
- 曖昧（あいまい）→ "哎，没（あいまい）说清楚，这段关系真是太曖昧了。"
- 挨拶（あいさつ）→ "哎，杀死（あいさつ）了这段沉默——赶快打个招呼！"
- 諦める（あきらめる）→ "啊，吃了亏么（あきらめる）——算了，就此放弃吧。"
"""

def make_prompt(word: str, reading: str, pos: str, meaning: str) -> str:
    return (
        f"单词：{word}（读音：{reading}）\n"
        f"词性：{pos}\n"
        f"含义：{meaning}\n\n"
        "请为这个词写一段记忆故事："
    )


def generate_story(word: str, reading: str, pos: str, meaning: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": make_prompt(word, reading, pos, meaning)},
        ],
        max_tokens=200,
        temperature=0.85,
    )
    return resp.choices[0].message.content.strip()


def get_words(conn: sqlite3.Connection, level: int | None, limit: int, word: str | None) -> list[dict]:
    if word:
        rows = conn.execute(
            "SELECT id, word, reading, pos, meaning, meaning_detail FROM words WHERE word = ?",
            (word,),
        ).fetchall()
    else:
        level_clause = f"AND jlpt_level = {level}" if level else ""
        rows = conn.execute(
            f"""SELECT w.id, w.word, w.reading, w.pos, w.meaning, w.meaning_detail
                FROM words w
                LEFT JOIN memory_stories ms ON ms.word_id = w.id AND ms.is_official = 1
                WHERE ms.id IS NULL  -- 还没有官方故事
                  {level_clause}
                ORDER BY w.count DESC
                LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_story(conn: sqlite3.Connection, word_id: int, content: str) -> None:
    conn.execute(
        """INSERT INTO memory_stories (word_id, user_id, method, content, status, is_official)
           VALUES (?, 'system', 'ai_generated', ?, 'approved', 1)
           ON CONFLICT DO NOTHING""",
        (word_id, content),
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",   type=int, default=50,  help="最多生成多少词（默认50）")
    parser.add_argument("--level",   type=int, default=None, help="只处理指定JLPT等级（1-5）")
    parser.add_argument("--word",    type=str, default=None, help="指定单个词")
    parser.add_argument("--dry-run", action="store_true",    help="只打印，不写数据库")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    words = get_words(conn, args.level, args.limit, args.word)
    if not words:
        print("没有找到符合条件的词（可能已全部生成）")
        return

    print(f"待生成：{len(words)} 词  model=gpt-4o-mini  dry-run={args.dry_run}")
    print()

    ok = fail = 0
    for i, w in enumerate(words, 1):
        meaning = w["meaning_detail"] or w["meaning"] or ""
        try:
            story = generate_story(w["word"], w["reading"], w["pos"] or "", meaning)
            print(f"[{i}/{len(words)}] {w['word']}（{w['reading']}）")
            print(f"  含义：{meaning[:40]}")
            print(f"  故事：{story}")
            print()
            if not args.dry_run:
                save_story(conn, w["id"], story)
            ok += 1
        except Exception as e:
            print(f"[{i}] {w['word']} 失败：{e}")
            fail += 1

        if i < len(words):
            time.sleep(0.3)   # 简单限速

    print(f"完成：成功 {ok}  失败 {fail}")
    if not args.dry_run:
        total = conn.execute("SELECT COUNT(*) FROM memory_stories WHERE is_official=1").fetchone()[0]
        print(f"数据库官方故事总数：{total}")

    conn.close()


if __name__ == "__main__":
    main()
