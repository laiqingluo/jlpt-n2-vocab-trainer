"""
import_missing_final.py
1. Fix 走れる reading (はしる → はしれる)
2. Add 16 genuinely missing high-frequency words
3. Use GPT to fill meaning_detail / collocation / examples
4. Recalculate quadrant for all rows
"""
import csv, os, shutil, time, json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

VOCAB   = Path(r"E:\codex\jlpt背单词\data\n2_vocab.csv")
BACKUP  = Path(r"E:\codex\jlpt背单词\data\n2_vocab_backup_before_import_missing_final.csv")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── 16 words to add ────────────────────────────────────────────────────────
NEW_WORDS = [
    {"word": "家",           "reading": "いえ",       "pos": "名詞",   "meaning": "家/家庭",    "count": "85"},
    {"word": "学校",         "reading": "がっこう",   "pos": "名詞",   "meaning": "学校",        "count": "84"},
    {"word": "早い",         "reading": "はやい",     "pos": "形容詞", "meaning": "早/迅速",     "count": "84"},
    {"word": "店",           "reading": "みせ",       "pos": "名詞",   "meaning": "店铺/商店",   "count": "82"},
    {"word": "始める",       "reading": "はじめる",   "pos": "動詞",   "meaning": "开始",         "count": "76"},
    {"word": "少ない",       "reading": "すくない",   "pos": "形容詞", "meaning": "少/稀少",     "count": "72"},
    {"word": "あまり",       "reading": "あまり",     "pos": "副詞",   "meaning": "不太/过于",   "count": "73"},
    {"word": "そして",       "reading": "そして",     "pos": "接続詞", "meaning": "然后/于是",   "count": "66"},
    {"word": "上げる",       "reading": "あげる",     "pos": "動詞",   "meaning": "举起/给予",   "count": "66"},
    {"word": "走る",         "reading": "はしる",     "pos": "動詞",   "meaning": "跑步/行驶",   "count": "64"},
    {"word": "忘れる",       "reading": "わすれる",   "pos": "動詞",   "meaning": "忘记",         "count": "63"},
    {"word": "どこ",         "reading": "どこ",       "pos": "代名詞", "meaning": "哪里",         "count": "62"},
    {"word": "止める",       "reading": "とめる",     "pos": "動詞",   "meaning": "停止/阻止",   "count": "52"},
    {"word": "地",           "reading": "ち",         "pos": "名詞",   "meaning": "地/土地",     "count": "52"},
    {"word": "彼女",         "reading": "かのじょ",   "pos": "代名詞", "meaning": "她/女朋友",   "count": "17"},
    {"word": "コンピューター","reading": "こんぴゅーたー","pos": "名詞", "meaning": "电脑/计算机", "count": "24"},
]

# ── Quadrant logic (same as task3_quadrant.py) ─────────────────────────────
def get_quadrant(count_str, is_n2_core):
    try:
        count = int(count_str or 0)
    except (ValueError, TypeError):
        count = 0
    core = str(is_n2_core).strip() == "是"
    if count >= 10 and core:     return "黄金词"
    elif count >= 10 and not core: return "隐藏考点"
    elif count < 10 and core:    return "社区推荐"
    else:                         return "边缘词"

# ── GPT prompts ────────────────────────────────────────────────────────────
SYSTEM_DETAIL = """你是日语词典助手。为每个日语单词生成详细释义。
格式：序号. ①意思1（日语例句。｜中文翻译。）②意思2（可选）
规则：1~2个义项，每个义项配一个短例句，只输出"序号. 内容"，每行一个。"""

SYSTEM_COLLOC = """你是日语词典助手。为每个日语单词生成3个最常用搭配。
格式：序号. 搭配1 / 搭配2 / 搭配3
规则：搭配体现典型用法，只输出"序号. 内容"，每行一个。"""

SYSTEM_EXAMPLE = """你是日语学习助手。为每个日语单词生成2个自然的N2水平例句。
格式：序号. 例句1 / 例句2
规则：例句符合N2语法，贴近考试场景，只输出"序号. 内容"，每行一个。"""

def build_prompt(rows):
    return "\n".join(f"{i}. {r['word']} ({r['reading']}) [{r['pos']}] {r['meaning']}"
                     for i, r in enumerate(rows, 1))

def parse_response(text, n):
    results = [""] * n
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        dot = line.find(".")
        if dot == -1:
            continue
        try:
            idx = int(line[:dot].strip()) - 1
            val = line[dot+1:].strip()
            if 0 <= idx < n:
                results[idx] = val
        except ValueError:
            continue
    return results

def gpt_fill(new_rows, field, system):
    prompt = build_prompt(new_rows)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system},
                  {"role": "user",   "content": prompt}],
        temperature=0,
    )
    vals = parse_response(resp.choices[0].message.content, len(new_rows))
    for row, val in zip(new_rows, vals):
        if val:
            row[field] = val
    return vals

# ── Main ───────────────────────────────────────────────────────────────────
shutil.copy2(VOCAB, BACKUP)
print(f"Backup → {BACKUP}")

with open(VOCAB, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

print(f"Loaded {len(rows)} rows")

# Step 1: Fix 走れる reading
fixed = 0
for r in rows:
    if r["word"].strip() == "走れる" and r["reading"].strip() == "はしる":
        r["reading"] = "はしれる"
        fixed += 1
print(f"Fixed {fixed} row(s): 走れる reading はしる→はしれる")

# Step 2: Deduplicate new words against existing vocab
existing = {r["word"].strip() for r in rows}
to_add = [w for w in NEW_WORDS if w["word"] not in existing]
skipped = [w["word"] for w in NEW_WORDS if w["word"] in existing]
if skipped:
    print(f"Already in vocab (skip): {skipped}")
print(f"Adding {len(to_add)} new words")

# Build full rows for new words
new_rows = []
for w in to_add:
    row = {f: "" for f in fieldnames}
    row.update({
        "word":       w["word"],
        "reading":    w["reading"],
        "pos":        w["pos"],
        "meaning":    w["meaning"],
        "count":      w["count"],
        "source":     "真题",
        "is_n2_core": "否",
        "collocation":   "",
        "examples":      "",
        "meaning_detail":"",
        "quadrant":      "",
    })
    new_rows.append(row)

# Step 3: GPT fill for new rows
if new_rows:
    print(f"\nGPT: filling meaning_detail ({len(new_rows)} words)...")
    gpt_fill(new_rows, "meaning_detail", SYSTEM_DETAIL)
    time.sleep(0.5)

    print(f"GPT: filling collocation ({len(new_rows)} words)...")
    gpt_fill(new_rows, "collocation", SYSTEM_COLLOC)
    time.sleep(0.5)

    print(f"GPT: filling examples ({len(new_rows)} words)...")
    gpt_fill(new_rows, "examples", SYSTEM_EXAMPLE)
    time.sleep(0.5)

    rows.extend(new_rows)
    print(f"Appended {len(new_rows)} rows")

# Step 4: Recalculate quadrant for ALL rows
for r in rows:
    r["quadrant"] = get_quadrant(r.get("count", ""), r.get("is_n2_core", ""))

from collections import Counter
q = Counter(r["quadrant"] for r in rows)
print(f"\nQuadrant stats: {dict(q)}")
print(f"Total: {len(rows)} rows")

# Step 5: Save
with open(VOCAB, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nSaved → {VOCAB}")

# Write report
report = {
    "fixed_reading": {"走れる": "はしる→はしれる", "count": fixed},
    "added": [r["word"] for r in new_rows],
    "skipped_already_exist": skipped,
    "total_rows": len(rows),
    "quadrant": dict(q),
}
report_path = VOCAB.parent / "_import_missing_final_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"Report → {report_path}")
