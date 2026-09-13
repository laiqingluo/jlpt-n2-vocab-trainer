"""
N2文脈規定 - 词汇例句自动生成工具
每次运行选择一个场景，GPT 为还没有例句的词生成句子，直接写入数据库。

使用方法：
  1. 修改下方 ARTICLE_STYLE（选一个取消注释）
  2. python n2_auto_match.py
  3. 换下一个场景，再跑一次
"""

import csv
import json
import re
import sqlite3
import time
import os
from pathlib import Path

# ============================================================
# 配置区
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH      = PROJECT_ROOT / "data" / "n2.db"
CSV_INPUT    = PROJECT_ROOT / "data" / "n2_vocab.csv"

# 场景选择：取消注释其中一个
ARTICLE_STYLE = "日本年金機構 社会保険 手続き 届出"
# ARTICLE_STYLE = "病院 診療 患者 説明 注意事項"
# ARTICLE_STYLE = "銀行 口座 手続き 申請 説明"
# ARTICLE_STYLE = "学校 通知 保護者 案内 連絡"
# ARTICLE_STYLE = "ビジネス メール 業務 連絡 依頼"
# ARTICLE_STYLE = "商品 サービス 説明 利用 案内"
# ARTICLE_STYLE = "市役所 区役所 住民 手続き 申請"
# ARTICLE_STYLE = "電力 ガス 水道 契約 手続き"

BATCH_SIZE = 10
SLEEP_SEC  = 1.0

# ============================================================

SKIP_POS = {'接尾辞', '接頭辞', '接头辞', '接尾语'}


def load_vocab():
    words = []
    with open(CSV_INPUT, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            word = row.get('word', '').strip()
            pos  = row.get('pos', '').strip()
            if not word or len(word) <= 1:
                continue
            if pos in SKIP_POS:
                continue
            try:
                cnt = int(row.get('count', '0') or '0')
            except ValueError:
                cnt = 0
            words.append({
                'word':     word,
                'reading':  row.get('reading', '').strip(),
                'pos':      pos,
                'meaning':  row.get('meaning', '').strip(),
                'count':    cnt,
            })
    return words


def get_done_words(conn):
    """已经有例句的词（来自 word_sentences 表）"""
    rows = conn.execute("""
        SELECT w.word FROM word_sentences ws
        JOIN words w ON w.id = ws.word_id
    """).fetchall()
    return {r[0] for r in rows}


def get_word_id(conn, word):
    row = conn.execute("SELECT id FROM words WHERE word=?", (word,)).fetchone()
    return row[0] if row else None


def save_sentence(conn, word_id, sentence):
    conn.execute("""
        INSERT INTO word_sentences (word_id, sentence, source)
        VALUES (?, ?, ?)
        ON CONFLICT(word_id) DO UPDATE SET
            sentence = excluded.sentence,
            source   = excluded.source
    """, (word_id, sentence, 'gpt_' + ARTICLE_STYLE[:10]))
    conn.commit()


def call_api(client, word_list):
    prompt = (
        f"あなたはJLPT N2の語彙専門家です。"
        f"以下の単語それぞれについて、「{ARTICLE_STYLE}」に関連する場面で自然に使われる例文を1つ作成してください。\n\n"
        "条件：\n"
        "- 例文は20〜60文字\n"
        "- 公的文書・ビジネス文書のスタイル\n"
        "- 文脈から単語の意味が推測できること（文脈規定問題として成立）\n"
        "- 単語の意味を直接説明しない\n"
        "- 全単語に例文を作成すること\n\n"
        f"単語リスト：{'、'.join(word_list)}\n\n"
        'JSONのみで返答：\n'
        '{"matches":[{"word":"単語","sentence":"例文"}]}'
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    try:
        return json.loads(raw).get('matches', [])
    except Exception:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                return json.loads(m.group()).get('matches', [])
            except Exception:
                pass
    return []


def main():
    try:
        from openai import OpenAI
    except ImportError:
        print("请先运行：pip install openai")
        return

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        # 从 backend/.env 读取
        env_path = PROJECT_ROOT / "backend" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("找不到 OPENAI_API_KEY，请在 backend/.env 中设置")
        return

    client = OpenAI(api_key=api_key)
    conn   = sqlite3.connect(str(DB_PATH))

    all_words = load_vocab()
    done      = get_done_words(conn)
    todo      = [w for w in all_words if w['word'] not in done]

    print(f"词汇总数：{len(all_words)}")
    print(f"已有例句：{len(done)}")
    print(f"本次待处理：{len(todo)}")
    print(f"场景：{ARTICLE_STYLE}")
    print()

    if not todo:
        print("所有词已有例句，无需处理。")
        conn.close()
        return

    total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    saved = failed = 0

    for i in range(0, len(todo), BATCH_SIZE):
        batch     = todo[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        word_list = [w['word'] for w in batch]

        print(f"[{batch_num}/{total_batches}] {'、'.join(word_list)}")

        try:
            matches = call_api(client, word_list)
            count = 0
            for m in matches:
                word     = m.get('word', '')
                sentence = m.get('sentence', '').strip()
                if not sentence or word not in sentence or len(sentence) < 15:
                    continue
                word_id = get_word_id(conn, word)
                if not word_id:
                    continue
                save_sentence(conn, word_id, sentence)
                count += 1
                saved += 1
            failed += len(batch) - count
            print(f"  → 保存 {count} 条")
        except Exception as e:
            print(f"  → 错误：{e}")
            failed += len(batch)

        if i + BATCH_SIZE < len(todo):
            time.sleep(SLEEP_SEC)

    conn.close()
    print()
    print(f"完成：保存 {saved}  未匹配 {failed}")
    print(f"数据库 word_sentences 总数：", end="")
    conn2 = sqlite3.connect(str(DB_PATH))
    print(conn2.execute("SELECT COUNT(*) FROM word_sentences").fetchone()[0])
    conn2.close()


if __name__ == '__main__':
    main()
