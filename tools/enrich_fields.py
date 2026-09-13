"""
enrich_fields.py
Fill meaning_detail / collocation / examples for words missing these fields.
Runs three passes in order. Skips rows that already have the field filled.
"""
import csv, os, shutil, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

VOCAB   = Path(r"E:\codex\jlpt背单词\data\n2_vocab.csv")
BACKUP  = Path(r"E:\codex\jlpt背单词\data\n2_vocab_backup_before_enrich.csv")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ── Prompts ───────────────────────────────────────────────────────────────

SYSTEM_DETAIL = """你是日语词典助手。为每个日语单词生成详细释义。
格式：序号. ①意思1（日语例句。｜中文翻译。）②意思2（日语例句。｜中文翻译。）
规则：
- 1~3个义项，每个义项配一个短例句
- 例句用日语，后面加｜和中文翻译
- 只输出"序号. 内容"，每行一个，不要多余说明"""

SYSTEM_COLLOC = """你是日语词典助手。为每个日语单词生成3个最常用搭配。
格式：序号. 搭配1 / 搭配2 / 搭配3
规则：
- 搭配要体现词的典型用法，用「を/に/が/で」等助词连接
- 只输出"序号. 内容"，每行一个，不要多余说明"""

SYSTEM_EXAMPLE = """你是日语学习助手。为每个日语单词生成2个自然的N2水平例句。
格式：序号. 例句1 / 例句2
规则：
- 例句符合N2语法水平，贴近考试场景（日常生活、工作、学校）
- 例句用日语，不需要翻译
- 只输出"序号. 内容"，每行一个，不要多余说明"""

# ── Helpers ───────────────────────────────────────────────────────────────

def build_prompt(rows: list[dict]) -> str:
    lines = []
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {r['word']} ({r['reading']}) [{r['pos']}] {r['meaning']}")
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
            val = line[dot+1:].strip()
            if 0 <= idx < n:
                results[idx] = val
        except ValueError:
            continue
    return results

def run_pass(rows: list[dict], field: str, system: str, batch: int, label: str):
    targets = [(i, r) for i, r in enumerate(rows) if not r.get(field)]
    if not targets:
        print(f"  {label}: 全部已有，跳过")
        return

    total = len(targets)
    filled = 0
    print(f"\n{'='*50}")
    print(f"  {label}：{total} 词，批次大小 {batch}")
    print(f"{'='*50}")

    for start in range(0, total, batch):
        chunk = targets[start : start + batch]
        prompt = build_prompt([r for _, r in chunk])
        n = len(chunk)

        print(f"  batch {start//batch+1}/{(total-1)//batch+1} ({n}词)...", end=" ", flush=True)
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0,
            )
            vals = parse_response(resp.choices[0].message.content, n)
            for (row_idx, row), val in zip(chunk, vals):
                if val:
                    rows[row_idx][field] = val
                    filled += 1
            sample_word = chunk[0][1]["word"]
            sample_val  = vals[0][:30] if vals[0] else "?"
            print(f"ok  ({sample_word}→{sample_val}…)")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.3)

    print(f"  完成：{filled}/{total}")

def save(rows, fieldnames, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# ── Main ──────────────────────────────────────────────────────────────────

shutil.copy2(VOCAB, BACKUP)
print(f"Backup → {BACKUP}")

with open(VOCAB, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

run_pass(rows, "meaning_detail", SYSTEM_DETAIL,  45, "meaning_detail (473词)")
save(rows, fieldnames, VOCAB)

run_pass(rows, "collocation",    SYSTEM_COLLOC,  60, "collocation (5422词)")
save(rows, fieldnames, VOCAB)

run_pass(rows, "examples",       SYSTEM_EXAMPLE, 40, "examples (1338词)")
save(rows, fieldnames, VOCAB)

print("\n全部完成。")
