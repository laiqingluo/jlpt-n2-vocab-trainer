"""任务三：新增 quadrant 字段并统计"""
import csv, json, shutil
from pathlib import Path
from collections import Counter

CSV_PATH = Path(__file__).parent.parent / "data" / "n2_vocab.csv"


def get_quadrant(count_str: str, is_n2_core: str) -> str:
    try:
        count = int(count_str or 0)
    except (ValueError, TypeError):
        count = 0
    core = is_n2_core.strip() == "是"
    if count >= 10 and core:
        return "黄金词"
    elif count >= 10 and not core:
        return "隐藏考点"
    elif count < 10 and core:
        return "社区推荐"
    else:
        return "边缘词"


def main():
    rows = []
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # 新增字段（如果还没有）
    if 'quadrant' not in fieldnames:
        fieldnames.append('quadrant')

    for row in rows:
        row['quadrant'] = get_quadrant(row.get('count', ''), row.get('is_n2_core', ''))

    shutil.copy(CSV_PATH, CSV_PATH.with_suffix('.task3-backup.csv'))

    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 统计
    stats = Counter(row['quadrant'] for row in rows)
    result = dict(stats)
    out = CSV_PATH.parent / "_verify_task3.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Task 3 done. quadrant stats: {result}")


if __name__ == "__main__":
    main()
