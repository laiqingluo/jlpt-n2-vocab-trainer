"""
enrich_meaning.py
Fill meaning field for words where import_source == "missing_ready_v3".
Uses OpenAI gpt-4o-mini, batches of 60 words per request.
"""
import csv, os, shutil, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

VOCAB   = Path(r"E:\codex\jlpt背单词\data\n2_vocab.csv")
BACKUP  = Path(r"E:\codex\jlpt背单词\data\n2_vocab_backup_before_meaning.csv")
BATCH   = 60

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = (
    "你是日语词典助手。用户给你一批日语单词（格式：序号. 词 読み 词性），"
    "请为每个词提供最核心的中文释义，1-4个汉字，不要解释，不要举例。"
    "输出格式：序号. 释义（每行一个，序号与输入对应）。"
)

def build_prompt(words: list[tuple[str,str,str]]) -> str:
    lines = []
    for i, (word, reading, pos) in enumerate(words, 1):
        lines.append(f"{i}. {word} {reading} {pos}")
    return "\n".join(lines)

def parse_response(text: str, n: int) -> list[str]:
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
            meaning = line[dot+1:].strip()
            if 0 <= idx < n:
                results[idx] = meaning
        except ValueError:
            continue
    return results

# ── Load ──────────────────────────────────────────────────────────────────
shutil.copy2(VOCAB, BACKUP)
print(f"Backup → {BACKUP}")

with open(VOCAB, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

targets = [(i, r) for i, r in enumerate(rows)
           if r.get("import_source") == "missing_ready_v3" and r.get("meaning", "") == ""]
print(f"待补充: {len(targets)} 词")

# ── Batch process ─────────────────────────────────────────────────────────
total_fixed = 0
for batch_start in range(0, len(targets), BATCH):
    batch = targets[batch_start : batch_start + BATCH]
    words = [(r["word"], r["reading"], r["pos"]) for _, r in batch]
    prompt = build_prompt(words)

    print(f"  batch {batch_start//BATCH + 1}/{(len(targets)-1)//BATCH + 1} "
          f"({len(batch)} 词)...", end=" ", flush=True)

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0,
    )
    meanings = parse_response(resp.choices[0].message.content, len(batch))

    for (row_idx, row), meaning in zip(batch, meanings):
        if meaning:
            rows[row_idx]["meaning"] = meaning
            total_fixed += 1

    print(f"done  (sample: {words[0][0]}→{meanings[0]})")
    time.sleep(0.5)

# ── Write ─────────────────────────────────────────────────────────────────
with open(VOCAB, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n完成：{total_fixed}/{len(targets)} 词已填充 meaning")

# Show sample
still_empty = [r for r in rows if r.get("import_source") == "missing_ready_v3" and not r.get("meaning")]
if still_empty:
    print(f"仍为空: {len(still_empty)} 词")
    for r in still_empty[:5]:
        print(f"  {r['word']}")
