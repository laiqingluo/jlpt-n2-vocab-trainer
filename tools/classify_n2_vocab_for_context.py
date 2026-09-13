from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = Path.home() / "Desktop" / "n2_vocab.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
CSV_PATH = OUTPUT_DIR / "n2_vocab_context_layers.csv"
JSON_PATH = OUTPUT_DIR / "n2_vocab_context_layers.json"
REPORT_PATH = OUTPUT_DIR / "n2_vocab_context_layers_report.md"


CLASS_LABELS = {
    "A": "固定搭配造句优先词",
    "B": "近义词辨析造句词",
    "C": "语境判断造句词",
    "D": "暂不适合文脈規定主库",
}

FUNCTION_POS_HINTS = [
    "接尾",
    "接頭",
    "接续",
    "接続",
    "連体詞",
    "连体",
    "代名詞",
    "感動詞",
]

BASIC_TOO_GENERIC = {
    "言う",
    "聞く",
    "思う",
    "考える",
    "自分",
    "ほう",
    "子ども",
    "読む",
    "書く",
    "作る",
    "使う",
    "知る",
    "わかる",
    "見る",
    "行く",
    "来る",
    "ある",
    "いる",
    "する",
    "なる",
    "いい",
    "多い",
    "同じ",
}

A_WORDS = {
    "提出",
    "申請",
    "届出",
    "手続き",
    "手続",
    "確認",
    "添付",
    "記入",
    "記載",
    "登録",
    "適用",
    "該当",
    "対象",
    "必要",
    "資格",
    "取得",
    "喪失",
    "条件",
    "要件",
    "基準",
    "保存",
    "交付",
    "発行",
    "認可",
    "承認",
    "利用",
    "変更",
    "選択",
    "判断",
    "防止",
    "確保",
    "申告",
    "申告書",
    "書類",
    "本人確認",
    "住所",
    "契約",
    "加入",
    "証明",
}

A_COLLOCATION_HINTS = [
    "を提出",
    "を申請",
    "申請する",
    "届出",
    "手続",
    "を確認",
    "を添付",
    "を記入",
    "を記載",
    "を登録",
    "に該当",
    "対象となる",
    "が必要",
    "必要がある",
    "を受ける",
    "を取得",
    "を喪失",
    "を満た",
    "を保存",
    "を交付",
    "を発行",
    "を変更",
    "を選択",
    "を判断",
    "を防止",
    "を確保",
    "を利用",
    "を行う",
    "に関する",
]

B_WORDS = {
    "述べる",
    "示す",
    "表す",
    "現れる",
    "現す",
    "比べる",
    "比較",
    "異なる",
    "違い",
    "区別",
    "区分",
    "選ぶ",
    "選択",
    "判断",
    "認める",
    "認識",
    "理解",
    "把握",
    "推測",
    "予想",
    "期待",
    "要求",
    "依頼",
    "断る",
    "避ける",
    "防ぐ",
    "減る",
    "減らす",
    "増える",
    "増やす",
    "保つ",
    "守る",
    "支える",
    "広がる",
    "広げる",
    "高まる",
    "高める",
    "深まる",
    "深める",
}

B_MEANING_HINTS = [
    "区别",
    "区分",
    "比较",
    "选择",
    "判断",
    "认为",
    "推测",
    "预测",
    "期待",
    "要求",
    "避免",
    "防止",
    "增加",
    "减少",
    "保持",
    "维持",
    "表示",
    "表达",
    "说明",
    "承认",
    "认识",
]

C_WORDS = {
    "場合",
    "内容",
    "情報",
    "状況",
    "状態",
    "結果",
    "原因",
    "理由",
    "目的",
    "方法",
    "程度",
    "影響",
    "関係",
    "問題",
    "課題",
    "傾向",
    "特徴",
    "変化",
    "効果",
    "役割",
    "価値",
    "意味",
    "可能",
    "不可能",
    "重要",
    "大切",
    "十分",
    "当然",
    "実際",
    "一般",
    "具体",
    "適切",
    "自然",
    "普通",
    "一方",
    "さらに",
    "つまり",
    "ただし",
    "なお",
    "まず",
}

C_MEANING_HINTS = [
    "情况",
    "状态",
    "内容",
    "信息",
    "结果",
    "原因",
    "理由",
    "目的",
    "方法",
    "程度",
    "影响",
    "关系",
    "问题",
    "课题",
    "倾向",
    "特征",
    "变化",
    "效果",
    "作用",
    "价值",
    "意义",
    "重要",
    "适当",
    "具体",
    "一般",
]


def as_int(value: str) -> int:
    try:
        return int(float((value or "0").replace(",", "")))
    except ValueError:
        return 0


def is_core(row: dict[str, str]) -> bool:
    return (row.get("is_n2_core") or "").strip() in {"是", "TRUE", "True", "true", "1"}


def has_any(text: str, needles: list[str] | set[str]) -> bool:
    return any(needle and needle in text for needle in needles)


def is_function_or_fragment(word: str, pos: str, meaning: str) -> bool:
    if has_any(pos, FUNCTION_POS_HINTS):
        return True
    if len(word) <= 1:
        return True
    if re.fullmatch(r"[0-9０-９]+", word):
        return True
    if meaning in {"生", "性", "化", "们", "的", "第"}:
        return True
    return False


def classify(row: dict[str, str]) -> tuple[str, int, str, str]:
    word = (row.get("word") or "").strip()
    pos = (row.get("pos") or "").strip()
    meaning = (row.get("meaning") or "").strip()
    meaning_detail = (row.get("meaning_detail") or "").strip()
    collocation = (row.get("collocation") or "").strip()
    quadrant = (row.get("quadrant") or "").strip()
    count = as_int(row.get("count") or "0")
    source = (row.get("source") or "").strip()
    text = " ".join([word, pos, meaning, meaning_detail, collocation, quadrant])

    score = 50
    reasons: list[str] = []

    if is_function_or_fragment(word, pos, meaning):
        return "D", 20, "词性偏功能词/词缀/碎片，不适合作为文脈規定主库目标词", "exclude_from_main_bank"

    if word in BASIC_TOO_GENERIC and count >= 120 and not is_core(row):
        return "D", 35, "高频基础泛用词，文脈規定学习价值较低", "exclude_or_keep_as_support_vocab"

    if quadrant == "黄金词":
        score += 16
        reasons.append("黄金词")
    elif quadrant == "隐藏考点":
        score += 8
        reasons.append("隐藏考点")
    elif quadrant == "边缘词":
        score -= 8
        reasons.append("边缘词")

    if is_core(row):
        score += 12
        reasons.append("N2核心词")
    if source in {"真题", "两者", "jlpt_exam_frequency"}:
        score += 8
        reasons.append("有真题或考试频率来源")

    a_score = 0
    b_score = 0
    c_score = 0

    if word in A_WORDS:
        a_score += 34
    if has_any(collocation, A_COLLOCATION_HINTS):
        a_score += 30
    if "名·" in pos or "サ" in pos:
        a_score += 10
    if pos in {"名詞", "名", "動詞"} and has_any(text, A_WORDS):
        a_score += 10

    if word in B_WORDS:
        b_score += 30
    if has_any(meaning + meaning_detail, B_MEANING_HINTS):
        b_score += 20
    if pos in {"動詞", "形容詞", "形状詞", "ナ形", "イ形", "副詞", "副"}:
        b_score += 10

    if word in C_WORDS:
        c_score += 28
    if has_any(meaning + meaning_detail, C_MEANING_HINTS):
        c_score += 18
    if pos in {"名詞", "名", "副詞", "副", "形状詞", "ナ形"}:
        c_score += 8
    if 20 <= count <= 180:
        c_score += 6

    if a_score >= max(b_score, c_score) and a_score >= 30:
        klass = "A"
        score += a_score
        reasons.append("固定搭配或手续类搭配明显")
        use = "extract_real_sentence_collocations_first"
    elif b_score >= max(a_score, c_score) and b_score >= 28:
        klass = "B"
        score += b_score
        reasons.append("适合做近义词/用法差异辨析")
        use = "synonym_contrast_sentence_writing"
    elif c_score >= 24:
        klass = "C"
        score += c_score
        reasons.append("需要上下文判断语义或搭配")
        use = "context_judgement_sentence_writing"
    else:
        klass = "D"
        score = min(score, 55)
        reasons.append("搭配或语境出题价值不够明确")
        use = "manual_review_or_support_vocab"

    if count > 400 and klass != "D":
        score -= 12
        reasons.append("频率很高，可能偏基础泛用")
    if not collocation:
        score -= 8
        reasons.append("缺少搭配字段")
    if not row.get("examples"):
        score -= 5
        reasons.append("缺少例句字段")

    score = max(1, min(100, score))
    return klass, score, "；".join(dict.fromkeys(reasons)), use


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"Input file not found: {INPUT_PATH}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    output_rows: list[dict[str, str]] = []
    for row in rows:
        klass, score, reason, use = classify(row)
        enriched = dict(row)
        enriched["context_class"] = klass
        enriched["context_class_label"] = CLASS_LABELS[klass]
        enriched["priority_score"] = str(score)
        enriched["layer_reason"] = reason
        enriched["recommended_use"] = use
        output_rows.append(enriched)

    output_rows.sort(key=lambda r: (r["context_class"], -as_int(r["priority_score"]), -as_int(r.get("count", "0")), r.get("word", "")))

    fieldnames = list(rows[0].keys()) + [
        "context_class",
        "context_class_label",
        "priority_score",
        "layer_reason",
        "recommended_use",
    ]

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    JSON_PATH.write_text(json.dumps(output_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    class_counts = Counter(r["context_class"] for r in output_rows)
    pos_by_class = {
        klass: Counter(r.get("pos", "") for r in output_rows if r["context_class"] == klass).most_common(12)
        for klass in CLASS_LABELS
    }

    report = [
        "# N2 Vocab Context Layering Report",
        "",
        f"- 输入文件: `{INPUT_PATH}`",
        f"- 总词条数: {len(output_rows)}",
        f"- 输出 CSV: `{CSV_PATH}`",
        f"- 输出 JSON: `{JSON_PATH}`",
        "",
        "## 分层数量",
        md_table(["class", "label", "count"], [[k, CLASS_LABELS[k], class_counts.get(k, 0)] for k in ["A", "B", "C", "D"]]),
        "",
        "## 各层词性 Top 12",
    ]
    for klass in ["A", "B", "C", "D"]:
        report.extend(
            [
                f"### {klass} {CLASS_LABELS[klass]}",
                md_table(["pos", "count"], pos_by_class[klass]),
                "",
            ]
        )

    for klass in ["A", "B", "C", "D"]:
        sample = [r for r in output_rows if r["context_class"] == klass][:30]
        report.extend(
            [
                f"## {klass}层样例 Top 30",
                md_table(
                    ["word", "reading", "pos", "meaning", "score", "collocation", "reason"],
                    [
                        [
                            r.get("word", ""),
                            r.get("reading", ""),
                            r.get("pos", ""),
                            r.get("meaning", ""),
                            r.get("priority_score", ""),
                            r.get("collocation", ""),
                            r.get("layer_reason", ""),
                        ]
                        for r in sample
                    ],
                ),
                "",
            ]
        )

    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

    print(f"总词条数: {len(output_rows)}")
    print(f"A 固定搭配造句优先词: {class_counts.get('A', 0)}")
    print(f"B 近义词辨析造句词: {class_counts.get('B', 0)}")
    print(f"C 语境判断造句词: {class_counts.get('C', 0)}")
    print(f"D 暂不适合文脈規定主库: {class_counts.get('D', 0)}")
    print(f"输出 CSV 路径: {CSV_PATH}")
    print(f"输出 JSON 路径: {JSON_PATH}")
    print(f"报告路径: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
