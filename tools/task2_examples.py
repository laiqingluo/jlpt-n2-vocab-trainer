"""任务二：清洗 examples 字段，每词保留最短清晰的1-2个例句"""
import csv, json, re, shutil
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"


def split_examples(raw: str) -> list[str]:
    """把粘连的例句拆分成列表"""
    if not raw or not raw.strip():
        return []

    # 先按 / 分隔
    parts = [p.strip() for p in raw.split("/") if p.strip()]

    # 对每个 part 再尝试按句末标点（。！？）+大写假名/汉字 做二次拆分
    result = []
    for part in parts:
        # 在句末标点后、下一个句子开头处切开（不切断括号内）
        sub = re.split(r'(?<=[。！？」」])\s*(?=[「「『【】ァ-ヿぁ-ゟ一-鿿])', part)
        result.extend([s.strip() for s in sub if s.strip()])

    return result


def clean_examples(raw: str) -> str:
    """拆分后去重，按长度排序取最短的1-2个，用 / 连接"""
    parts = split_examples(raw)
    if not parts:
        return ""

    # 去除完全重复（忽略尾部省略号）
    seen = set()
    unique = []
    for p in parts:
        # 截断到30字作为去重key，避免截断导致"类似"被保留
        key = re.sub(r'\s+', '', p)[:40]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # 过滤明显不完整的句子（少于4个字符，或以 / 结尾）
    unique = [p for p in unique if len(p) >= 4 and not p.endswith("/")]

    # 按长度升序，取最短的1-2个
    unique.sort(key=len)
    chosen = unique[:2]

    return " / ".join(chosen)


def main():
    rows = []
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    sample = []

    for row in rows:
        old = row.get('examples', '') or ''
        new = clean_examples(old)
        if new != old:
            if len(sample) < 5:
                sample.append({
                    'word': row['word'],
                    'before': old[:80],
                    'after': new,
                })
            row['examples'] = new
            changed += 1

    # 备份
    shutil.copy(CSV_PATH, CSV_PATH.with_suffix('.task2-backup.csv'))

    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 写验证文件
    out = CSV_PATH.parent / "_verify_task2.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"Task 2 done. Changed: {changed} rows. Sample written to {out}")


if __name__ == "__main__":
    main()
