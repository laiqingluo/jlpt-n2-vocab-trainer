from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "articles.txt"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
CSV_PATH = OUTPUT_DIR / "collocation_candidates.csv"
JSON_PATH = OUTPUT_DIR / "collocation_candidates.json"
REPORT_PATH = OUTPUT_DIR / "collocation_report.md"

FIELDNAMES = [
    "source_id",
    "source_title",
    "sentence",
    "collocation_key",
    "target_word",
    "target_word_reading",
    "target_word_cn",
    "pattern_type",
    "skill_layer",
    "source_domain",
    "quality_score",
    "risk_level",
    "risk_reason",
    "candidate_status",
]

TARGET_META = {
    "満たす": ("みたす", "满足"),
    "提出": ("ていしゅつ", "提交"),
    "届出": ("とどけで", "申报、备案"),
    "申請": ("しんせい", "申请"),
    "手続き": ("てつづき", "手续"),
    "手続": ("てつづき", "手续"),
    "認可": ("にんか", "认可、许可"),
    "登録": ("とうろく", "登记、注册"),
    "対象": ("たいしょう", "对象"),
    "該当": ("がいとう", "符合、属于"),
    "適用": ("てきよう", "适用"),
    "本人確認": ("ほんにんかくにん", "本人确认、身份核验"),
    "住所": ("じゅうしょ", "住所、地址"),
    "変更": ("へんこう", "变更"),
    "申告書": ("しんこくしょ", "申报书"),
    "完了": ("かんりょう", "完成"),
    "資格": ("しかく", "资格"),
    "取得": ("しゅとく", "取得"),
    "喪失": ("そうしつ", "丧失"),
    "確認": ("かくにん", "确认"),
    "添付": ("てんぷ", "附加、附上"),
    "保存": ("ほぞん", "保存"),
    "必要": ("ひつよう", "必要"),
    "記入": ("きにゅう", "填写"),
    "交付": ("こうふ", "交付、发放"),
    "返戻": ("へんれい", "退回"),
    "防止": ("ぼうし", "防止"),
    "確保": ("かくほ", "确保"),
    "判断": ("はんだん", "判断"),
    "選択": ("せんたく", "选择"),
    "記載": ("きさい", "记载、填写"),
    "利用": ("りよう", "利用、使用"),
    "発行": ("はっこう", "发行、出具"),
    "承認": ("しょうにん", "批准、承认"),
    "加入": ("かにゅう", "加入"),
    "要件": ("ようけん", "条件、要件"),
    "条件": ("じょうけん", "条件"),
    "基準": ("きじゅん", "标准、基准"),
}

PROCEDURE_KEYWORDS = [
    "手続き",
    "手続",
    "申請",
    "届出",
    "提出",
    "確認",
    "必要",
    "対象",
    "該当",
    "適用",
    "資格",
    "取得",
    "喪失",
    "加入",
    "要件",
    "条件",
    "基準",
    "添付",
    "交付",
    "変更",
    "登録",
    "申告",
    "保存",
    "選択",
    "記入",
    "利用",
    "発行",
    "認可",
    "承認",
    "本人確認",
    "住所",
    "書類",
    "申告書",
]

NAVIGATION_PATTERNS = [
    r"^本文へ$",
    r"^メニュー$",
    r"^検索$",
    r"^トップページ$",
    r"^ページトップへ$",
    r"^サイトマップ$",
    r"^お問い合わせ$",
    r"^お問い合わせ先$",
    r"^戻る$",
    r"^閉じる$",
    r"^別ウィンドウが開きます$",
    r"^https?://",
]

SECTION_HEADING_RE = re.compile(r"^\s*(\d{3})[.．]\s*$")
LIST_MARK_RE = re.compile(r"^[（(]?\d+[）)]|^[ア-ン][.．]|^[・※●○■□◆◇→⇒]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。？！!?])")
JP_NOUN = r"[一-龥々〆ヶぁ-んァ-ンーA-Za-z0-9（）()・\u3000 　]{1,35}"


@dataclass
class SentenceRecord:
    source_id: str
    source_title: str
    sentence: str


@dataclass
class Candidate:
    source_id: str
    source_title: str
    sentence: str
    collocation_key: str
    target_word: str
    target_word_reading: str
    target_word_cn: str
    pattern_type: str
    skill_layer: str
    source_domain: str
    quality_score: int
    risk_level: str
    risk_reason: str
    candidate_status: str


@dataclass
class FilteredSentence:
    source_id: str
    source_title: str
    sentence: str
    reason: str


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_navigation_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(re.search(pattern, stripped, re.IGNORECASE) for pattern in NAVIGATION_PATTERNS)


def clean_line(line: str) -> str:
    line = line.replace("\ufeff", "")
    line = re.sub(r"[ \u3000]+", " ", line)
    return line.strip()


def parse_articles(text: str) -> list[tuple[str, str, list[str]]]:
    articles: list[tuple[str, str, list[str]]] = []
    current_id = "articles"
    current_title = ""
    current_lines: list[str] = []
    pending_id: str | None = None

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if is_navigation_line(line):
            continue

        heading = SECTION_HEADING_RE.match(line)
        if heading:
            if current_lines or current_title:
                articles.append((current_id, current_title or current_id, current_lines))
            pending_id = heading.group(1)
            current_id = pending_id
            current_title = ""
            current_lines = []
            continue

        if pending_id and not current_title:
            current_title = line
            pending_id = None
            continue

        current_lines.append(line)

    if current_lines or current_title:
        articles.append((current_id, current_title or current_id, current_lines))

    return articles


def split_sentences(articles: Iterable[tuple[str, str, list[str]]]) -> list[SentenceRecord]:
    records: list[SentenceRecord] = []
    for source_id, title, lines in articles:
        buffer = ""
        for line in lines:
            if not line:
                continue
            if "\t" in line:
                # Keep table-like rows available for filtering/reporting, but do not merge them
                fragments = [line]
            else:
                buffer = f"{buffer}{line}" if buffer else line
                fragments = SENTENCE_SPLIT_RE.split(buffer)
                if fragments and not re.search(r"[。？！!?]$", fragments[-1]):
                    buffer = fragments.pop()
                else:
                    buffer = ""

            for fragment in fragments:
                sentence = fragment.strip()
                if sentence:
                    records.append(SentenceRecord(source_id, title, sentence))

        if buffer.strip():
            records.append(SentenceRecord(source_id, title, buffer.strip()))

    return records


def normalize_noun(noun: str) -> str:
    noun = re.sub(r"^[「『（(【\[]+", "", noun.strip())
    noun = re.sub(r"[」』）)】\]]+$", "", noun)
    noun = re.split(r"[、，]", noun)[-1]
    noun = re.split(r"(?:から|まで|として|には|に)", noun)[-1]
    noun = re.sub(r"\s+", "", noun)
    noun = re.sub(r"^(この|その|当該|各種|所定の|必要な|以下の|上記|それぞれ次の)", "", noun)
    return noun.strip("、，・ ")


def valid_generic_noun(noun: str) -> bool:
    if not noun or len(noun) > 22:
        return False
    if any(mark in noun for mark in ("（", "）", "(", ")", "「", "」", "：", ":", "→", "⇒")):
        return False
    if re.match(r"^[もはがをにへでと]", noun):
        return False
    if any(fragment in noun for fragment in ("間は", "金額と", "おける", "評価額", "ものとみなされ")):
        return False
    if re.search(r"[がをにはへでと]$", noun):
        return False
    if any(particle in noun for particle in ("が", "を", "には", "では")) and not noun.endswith(("書類", "申告書", "通知書", "確認書", "写し")):
        return False
    return True


def infer_domain(title: str, sentence: str) -> str:
    text = title + " " + sentence
    if any(word in text for word in ("年金", "厚生年金", "国民年金", "日本年金機構")):
        return "年金"
    if any(word in text for word in ("健康保険", "被保険者", "保険証", "協会けんぽ")):
        return "健康保険"
    if any(word in text for word in ("税", "課税", "申告", "納付", "税務署", "消費税")):
        return "税务"
    if any(word in text for word in ("在留", "入管", "出入国", "外国人", "ビザ")):
        return "入管"
    if any(word in text for word in ("通信", "電話", "OCN", "ドコモ", "ISP", "サービス")):
        return "通信"
    if any(word in text for word in ("銀行", "口座", "振込")):
        return "银行"
    if "保険" in text:
        return "保险"
    return "其他"


def target_from_key(collocation_key: str, pattern_type: str) -> str:
    if "満たす" in collocation_key:
        return "満たす"
    if "該当" in collocation_key:
        return "該当"
    if "対象となる" in collocation_key or collocation_key.endswith("対象となる"):
        return "対象"
    if "必要" in collocation_key:
        for word in ("提出", "記入", "確認", "添付", "保存", "届出"):
            if word in collocation_key:
                return word
        return "必要"
    if "受ける" in collocation_key:
        noun = normalize_noun(collocation_key.split("を", 1)[0])
        for word in ("登録", "認可", "適用", "交付", "承認"):
            if noun.endswith(word):
                return word
        return noun
    if "され" in collocation_key or "されます" in collocation_key:
        return collocation_key.split("され", 1)[0]
    if "します" in collocation_key:
        return collocation_key.split("します", 1)[0]
    if "する" in collocation_key:
        if "を" in collocation_key:
            noun, verb = collocation_key.rsplit("を", 1)
            if verb == "する":
                return normalize_noun(noun)
            return verb.replace("する", "")
        return collocation_key.replace("する", "")
    if "行う" in collocation_key:
        return "行う"
    if "変更" in collocation_key:
        return "変更"
    if "取得" in collocation_key:
        return "取得"
    if "喪失" in collocation_key:
        return "喪失"
    if "完了" in collocation_key:
        return "完了"
    return collocation_key


def meta_for_target(target_word: str) -> tuple[str, str]:
    return TARGET_META.get(target_word, ("", ""))


def compile_patterns() -> list[tuple[re.Pattern[str], str, str, str | None]]:
    exact_specs = [
        (r"(加入要件|要件|条件)を満た(?:す|し(?:ている|ます)?|した)", "{noun}を満たす", "noun_wo_verb", "満たす"),
        (r"(書類|申告書|届出|申請書|本人確認書類|添付書類|必要書類)を提出(?:する|します|し|した|される|されます)", "{noun}を提出する", "noun_wo_verb", "提出"),
        (r"(提出期限までに)提出(?:する|します)", "提出期限までに提出する", "formal_expression", "提出"),
        (r"(届出)をする|届出を行う|届け出をする|届け出を行う", "届出をする", "noun_wo_verb", "届出"),
        (r"(申請)を行(?:う|います|い)|申請する|申請します", "申請を行う", "noun_wo_verb", "申請"),
        (r"(手続き|手続)を行(?:う|います|い)|手続きをする|手続をする|手続きします", "手続きを行う", "noun_wo_verb", "手続き"),
        (r"(認可|登録|適用|交付|承認)を受け(?:る|ます|た)", "{noun}を受ける", "noun_wo_verb", None),
        (r"(対象)とな(?:る|ります|った)", "対象となる", "noun_to_naru", "対象"),
        (r"(基準|条件|要件|場合|各号|事由)に該当(?:する|します|し|した)", "{noun}に該当する", "noun_ni_verb", "該当"),
        (r"(添付書類|確認|添付|届出|保存|提出|記入|発行)が必要(?:です|となる|となります|な場合|ありません|です。)?", "{noun}が必要", "noun_ga_hitsuyou", None),
        (r"提出する必要があります|提出が必要です", "提出する必要があります", "formal_expression", "提出"),
        (r"記入する必要があります|記入が必要です", "記入する必要があります", "formal_expression", "記入"),
        (r"(住所)を変更(?:する|します|した)", "住所を変更する", "noun_wo_verb", "変更"),
        (r"(手続き|手続)が完了(?:する|します|した)", "手続きが完了する", "formal_expression", "完了"),
        (r"(資格)を取得(?:する|します|し|した)", "資格を取得する", "noun_wo_verb", "取得"),
        (r"(資格)を喪失(?:する|します|し|した)", "資格を喪失する", "noun_wo_verb", "喪失"),
        (r"(本人確認|確認)を行(?:う|います|い)", "{noun}を行う", "noun_wo_verb", "確認"),
        (r"(適用|交付|提出|記載|添付|発行|登録|承認)され(?:る|ます|ました)", "{noun}されます", "formal_passive", None),
        (r"返戻します|返戻され(?:る|ます)", "返戻します", "formal_passive", "返戻"),
        (r"(防止|確保|判断|選択|記載|添付|利用|確認|保存|発行)する", "{noun}する", "suru_verb", None),
    ]
    return [(re.compile(pattern), template, pattern_type, target) for pattern, template, pattern_type, target in exact_specs]


PATTERNS = compile_patterns()
GENERIC_PATTERNS = [
    (re.compile(rf"({JP_NOUN})を(提出|確認|添付|記載|保存|選択|利用|登録|変更|防止|確保|判断|発行)(?:する|します|し|した)"), "noun_wo_verb"),
    (re.compile(rf"({JP_NOUN})を(行)(?:う|います|い|った)"), "noun_wo_verb"),
    (re.compile(rf"({JP_NOUN})を(受け)(?:る|ます|た)"), "noun_wo_verb"),
    (re.compile(rf"({JP_NOUN})に(該当)(?:する|します|し|した)"), "noun_ni_verb"),
    (re.compile(rf"({JP_NOUN})とな(?:る|ります|った)"), "noun_to_naru"),
    (re.compile(rf"({JP_NOUN})が必要(?:です|となる|となります|な場合|ありません)?"), "noun_ga_hitsuyou"),
    (re.compile(r"(適用|交付|提出|記載|添付|発行|登録|承認|返戻)され(?:る|ます|ました)"), "formal_passive"),
]


def extract_candidates_from_sentence(record: SentenceRecord) -> list[tuple[str, str, str]]:
    sentence = record.sentence
    found: list[tuple[str, str, str]] = []

    for pattern, template, pattern_type, fixed_target in PATTERNS:
        for match in pattern.finditer(sentence):
            noun = normalize_noun(match.group(1)) if match.groups() and match.group(1) else ""
            if not noun and "{noun}" in template:
                continue
            key = template.format(noun=noun)
            target = fixed_target or target_from_key(key, pattern_type)
            found.append((key, target, pattern_type))

    for pattern, pattern_type in GENERIC_PATTERNS:
        for match in pattern.finditer(sentence):
            if pattern_type == "formal_passive":
                noun = normalize_noun(match.group(1))
                key = f"{noun}されます"
                target = noun
            elif pattern_type == "noun_to_naru":
                noun = normalize_noun(match.group(1))
                if not valid_generic_noun(noun):
                    continue
                if not any(keyword in noun for keyword in PROCEDURE_KEYWORDS) and "者" not in noun:
                    continue
                key = f"{noun}となる"
                target = "対象" if "対象" in noun else noun
            elif pattern_type == "noun_ga_hitsuyou":
                noun = normalize_noun(match.group(1))
                if not valid_generic_noun(noun):
                    continue
                if not any(keyword in noun for keyword in PROCEDURE_KEYWORDS):
                    continue
                key = f"{noun}が必要"
                target = "必要"
            else:
                noun = normalize_noun(match.group(1))
                verb_root = match.group(2)
                if not valid_generic_noun(noun):
                    continue
                if not any(keyword in noun for keyword in PROCEDURE_KEYWORDS) and noun not in ("住所", "氏名", "内容", "情報"):
                    continue
                if verb_root == "行":
                    key = f"{noun}を行う"
                    target = "行う"
                elif verb_root == "受け":
                    key = f"{noun}を受ける"
                    target = next((word for word in ("登録", "認可", "適用", "交付", "承認") if noun.endswith(word)), noun)
                elif pattern_type == "noun_ni_verb":
                    key = f"{noun}に該当する"
                    target = "該当"
                else:
                    key = f"{noun}を{verb_root}する"
                    target = verb_root
            found.append((key, target, pattern_type))

    seen: set[tuple[str, str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def filter_sentence(sentence: str) -> str | None:
    stripped = sentence.strip()
    if len(stripped) < 15:
        return "句子过短或标题碎片"
    if len(stripped) > 180:
        return "句子过长，需要人工拆分或确认"
    if "\t" in stripped or stripped.count(" ") >= 8:
        return "表格残片或栏目拼接"
    if re.search(r"https?://|www\.", stripped):
        return "包含 URL 或导航文字"
    if LIST_MARK_RE.match(stripped) and "。" not in stripped:
        return "列表项或标题碎片"
    if len(re.findall(r"\d", stripped)) >= 12:
        return "数字、日期或金额过多"
    if stripped.count("（") + stripped.count("(") >= 4:
        return "括号说明过多"
    if any(word in stripped for word in ("長官官房", "課税部", "徴収部", "組織", "機構図")):
        return "组织介绍，学习价值较低"
    return None


def score_candidate(sentence: str, collocation_key: str, source_domain: str) -> tuple[int, str, str]:
    score = 70
    reasons: list[str] = []

    if 25 <= len(sentence) <= 100:
        score += 12
        reasons.append("固定搭配明确，句子适中")
    elif len(sentence) <= 120:
        score += 4
        reasons.append("可用但需要人工确认")
    else:
        score -= 18
        reasons.append("句子较长，需要人工确认")

    keyword_hits = sum(1 for keyword in PROCEDURE_KEYWORDS if keyword in sentence)
    score += min(keyword_hits * 2, 10)

    if collocation_key in sentence or collocation_key.replace("する", "し") in sentence:
        score += 4

    digit_count = len(re.findall(r"\d", sentence))
    if digit_count >= 8:
        score -= 14
        reasons.append("数字和制度细节较多")

    if sentence.count("（") + sentence.count("(") >= 3:
        score -= 8
        reasons.append("括号说明较多")

    if source_domain == "税务" and any(word in sentence for word in ("税率", "控除", "課税", "納付")):
        score -= 8
        reasons.append("税务专业词较多")

    if any(word in sentence for word in ("法第", "条第", "政令", "省令")):
        score -= 8
        reasons.append("法律条文较硬")

    score = max(1, min(100, score))
    if score >= 80:
        risk_level = "low"
    elif score >= 60:
        risk_level = "medium"
    else:
        risk_level = "high"

    if not reasons:
        reasons.append("搭配可识别，需人工确认")
    return score, risk_level, "；".join(dict.fromkeys(reasons))


def build_candidates(records: list[SentenceRecord]) -> tuple[list[Candidate], list[FilteredSentence], Counter]:
    candidates: list[Candidate] = []
    filtered: list[FilteredSentence] = []
    filter_reasons: Counter = Counter()
    seen_rows: set[tuple[str, str, str]] = set()

    for record in records:
        filter_reason = filter_sentence(record.sentence)
        extracted = [] if filter_reason else extract_candidates_from_sentence(record)

        if filter_reason:
            filtered.append(FilteredSentence(record.source_id, record.source_title, record.sentence, filter_reason))
            filter_reasons[filter_reason] += 1
            continue

        if not extracted:
            reason = "没有明确搭配"
            filtered.append(FilteredSentence(record.source_id, record.source_title, record.sentence, reason))
            filter_reasons[reason] += 1
            continue

        domain = infer_domain(record.source_title, record.sentence)
        for collocation_key, target_word, pattern_type in extracted:
            row_key = (record.source_id, record.sentence, collocation_key)
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            reading, cn = meta_for_target(target_word)
            score, risk_level, risk_reason = score_candidate(record.sentence, collocation_key, domain)
            candidates.append(
                Candidate(
                    source_id=record.source_id,
                    source_title=record.source_title,
                    sentence=record.sentence,
                    collocation_key=collocation_key,
                    target_word=target_word,
                    target_word_reading=reading,
                    target_word_cn=cn,
                    pattern_type=pattern_type,
                    skill_layer="fixed_collocation",
                    source_domain=domain,
                    quality_score=score,
                    risk_level=risk_level,
                    risk_reason=risk_reason,
                    candidate_status="candidate",
                )
            )

    candidates.sort(key=lambda row: (-row.quality_score, row.risk_level, row.source_id, row.collocation_key))
    return candidates, filtered, filter_reasons


def write_csv(candidates: list[Candidate]) -> None:
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(asdict(candidate))


def write_json(candidates: list[Candidate]) -> None:
    JSON_PATH.write_text(
        json.dumps([asdict(candidate) for candidate in candidates], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        escaped = [str(cell).replace("\n", " ").replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def write_report(
    total_chars: int,
    total_sentences: int,
    candidates: list[Candidate],
    filtered: list[FilteredSentence],
    filter_reasons: Counter,
) -> None:
    risk_counts = Counter(candidate.risk_level for candidate in candidates)
    target_counts = Counter(candidate.target_word for candidate in candidates)
    key_counts = Counter(candidate.collocation_key for candidate in candidates)

    sample_candidates = candidates[:20]
    sample_filtered = filtered[:20]

    sections = [
        "# Collocation Candidate Extraction Report",
        "",
        f"- 输入文件路径: `{INPUT_PATH}`",
        f"- 总字符数: {total_chars}",
        f"- 总句子数: {total_sentences}",
        f"- 被过滤句子数: {len(filtered)}",
        f"- 候选搭配数量: {len(candidates)}",
        f"- low / medium / high 风险数量: {risk_counts.get('low', 0)} / {risk_counts.get('medium', 0)} / {risk_counts.get('high', 0)}",
        "",
        "## 最常见 target_word 前 30 个",
        md_table(["target_word", "count"], [[word, count] for word, count in target_counts.most_common(30)]),
        "",
        "## 最常见 collocation_key 前 30 个",
        md_table(["collocation_key", "count"], [[key, count] for key, count in key_counts.most_common(30)]),
        "",
        "## 被过滤原因统计",
        md_table(["reason", "count"], [[reason, count] for reason, count in filter_reasons.most_common()]),
        "",
        "## 抽样候选 20 条",
        md_table(
            ["source_id", "collocation_key", "target_word", "risk", "score", "sentence"],
            [
                [
                    row.source_id,
                    row.collocation_key,
                    row.target_word,
                    row.risk_level,
                    row.quality_score,
                    row.sentence,
                ]
                for row in sample_candidates
            ],
        ),
        "",
        "## 抽样被过滤句子 20 条",
        md_table(
            ["source_id", "reason", "sentence"],
            [[row.source_id, row.reason, row.sentence] for row in sample_filtered],
        ),
        "",
    ]
    REPORT_PATH.write_text("\n".join(sections), encoding="utf-8")


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"Input file not found: {INPUT_PATH}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    text = read_text(INPUT_PATH)
    articles = parse_articles(text)
    sentence_records = split_sentences(articles)
    candidates, filtered, filter_reasons = build_candidates(sentence_records)

    write_csv(candidates)
    write_json(candidates)
    write_report(len(text), len(sentence_records), candidates, filtered, filter_reasons)

    risk_counts = Counter(candidate.risk_level for candidate in candidates)
    print(f"候选数量: {len(candidates)}")
    print(f"输出 CSV 路径: {CSV_PATH}")
    print(f"输出 JSON 路径: {JSON_PATH}")
    print(f"报告路径: {REPORT_PATH}")
    print(
        "low / medium / high 数量: "
        f"{risk_counts.get('low', 0)} / {risk_counts.get('medium', 0)} / {risk_counts.get('high', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
