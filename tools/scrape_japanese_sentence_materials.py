from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URLS_PATH = PROJECT_ROOT / "data" / "article_urls.txt"
DEFAULT_VOCAB_PATH = PROJECT_ROOT / "data" / "output" / "n2_vocab_context_layers.csv"
FALLBACK_VOCAB_PATH = Path.home() / "Desktop" / "n2_vocab.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
CSV_PATH = OUTPUT_DIR / "web_sentence_materials.csv"
JSON_PATH = OUTPUT_DIR / "web_sentence_materials.json"
REPORT_PATH = OUTPUT_DIR / "web_sentence_materials_report.md"

USER_AGENT = "jlpt-context-material-builder/0.1 (+educational research; contact: local)"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。？！!?])")
JAPANESE_RE = re.compile(r"[ぁ-んァ-ン一-龥]")

NAV_WORDS = {
    "トップ",
    "メニュー",
    "検索",
    "お問い合わせ",
    "サイトマップ",
    "ページトップ",
    "本文へ",
    "閉じる",
    "ログイン",
    "English",
}

PROCEDURE_HINTS = {
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
}


@dataclass
class MaterialRow:
    source_url: str
    source_domain: str
    source_title: str
    sentence: str
    matched_words: str
    matched_word_count: int
    matched_classes: str
    quality_score: int
    risk_level: str
    risk_reason: str
    candidate_status: str


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self.skip_depth += 1
        if tag == "title":
            self.title_depth += 1
        if tag in {"p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag in {"p", "div", "li", "tr", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = unescape(data)
        if self.title_depth:
            self.title_parts.append(text)
        self.parts.append(text)

    @property
    def text(self) -> str:
        return "\n".join(part.strip() for part in self.parts if part.strip())

    @property
    def title(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.title_parts)).strip()


def read_urls(path: Path) -> list[str]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Put one Japanese article/FAQ/procedure URL per line.\n"
            "# Lines starting with # are ignored.\n",
            encoding="utf-8",
        )
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def load_vocab(path: Path, classes: set[str]) -> dict[str, str]:
    if not path.exists():
        path = FALLBACK_VOCAB_PATH
    if not path.exists():
        raise FileNotFoundError(f"Vocab file not found: {path}")

    vocab: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        has_class = "context_class" in (reader.fieldnames or [])
        for row in reader:
            klass = row.get("context_class", "") if has_class else "A"
            if has_class and klass not in classes:
                continue
            word = (row.get("word") or "").strip()
            if not word or len(word) <= 1:
                continue
            if re.fullmatch(r"[0-9０-９A-Za-z]+", word):
                continue
            vocab[word] = klass or "A"
    return dict(sorted(vocab.items(), key=lambda item: len(item[0]), reverse=True))


def can_fetch(url: str, user_agent: str, timeout: int = 10) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    robot = RobotFileParser()
    robot.set_url(robots_url)
    try:
        robot.read()
        return robot.can_fetch(user_agent, url)
    except Exception:
        # If robots.txt cannot be read, keep the script conservative but usable.
        return True


def fetch_html(url: str, timeout: int) -> tuple[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    detected = response.apparent_encoding or "utf-8"
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1", "ascii"}:
        response.encoding = detected
    return response.text, response.url


def html_to_text(html: str) -> tuple[str, str]:
    parser = VisibleTextParser()
    parser.feed(html)
    return parser.title, parser.text


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \u3000\t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in clean_text(text).splitlines():
        line = line.strip()
        if not line:
            continue
        if any(line == word for word in NAV_WORDS):
            continue
        parts = SENTENCE_SPLIT_RE.split(line)
        for part in parts:
            sentence = part.strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def sentence_filter_reason(sentence: str) -> str | None:
    if not JAPANESE_RE.search(sentence):
        return "not_japanese"
    if len(sentence) < 18:
        return "too_short"
    if len(sentence) > 180:
        return "too_long"
    if re.search(r"https?://|www\.", sentence):
        return "contains_url"
    if sentence.count(" ") >= 10 or "\t" in sentence:
        return "table_or_navigation_fragment"
    if len(re.findall(r"\d", sentence)) >= 14:
        return "too_many_numbers"
    if sentence.count("（") + sentence.count("(") >= 5:
        return "too_many_parentheses"
    if any(nav in sentence for nav in NAV_WORDS) and len(sentence) < 40:
        return "navigation_fragment"
    return None


def match_words(sentence: str, vocab: dict[str, str], max_words: int = 20) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    occupied: list[range] = []
    for word, klass in vocab.items():
        start = sentence.find(word)
        if start < 0:
            continue
        span = range(start, start + len(word))
        if any(set(span).intersection(existing) for existing in occupied):
            continue
        matches.append((word, klass))
        occupied.append(span)
        if len(matches) >= max_words:
            break
    return matches


def score_sentence(sentence: str, matches: list[tuple[str, str]]) -> tuple[int, str, str]:
    score = 50
    reasons: list[str] = []

    if 28 <= len(sentence) <= 110:
        score += 18
        reasons.append("句子长度适中")
    elif len(sentence) <= 140:
        score += 8
        reasons.append("句子可用但略长")
    else:
        score -= 12
        reasons.append("句子较长")

    if matches:
        score += min(len(matches) * 4, 18)
        reasons.append("命中词库目标词")

    hint_count = sum(1 for hint in PROCEDURE_HINTS if hint in sentence)
    if hint_count:
        score += min(hint_count * 3, 18)
        reasons.append("手续/申请/确认类语境明显")

    if len(re.findall(r"\d", sentence)) >= 8:
        score -= 10
        reasons.append("数字细节较多")
    if sentence.count("（") + sentence.count("(") >= 3:
        score -= 6
        reasons.append("括号说明较多")

    score = max(1, min(100, score))
    risk = "low" if score >= 80 else "medium" if score >= 60 else "high"
    return score, risk, "；".join(reasons or ["需要人工确认"])


def build_rows(url: str, title: str, text: str, vocab: dict[str, str]) -> tuple[list[MaterialRow], Counter]:
    parsed = urlparse(url)
    domain = parsed.netloc
    rows: list[MaterialRow] = []
    filtered = Counter()
    for sentence in split_sentences(text):
        reason = sentence_filter_reason(sentence)
        if reason:
            filtered[reason] += 1
            continue
        matches = match_words(sentence, vocab)
        if not matches:
            filtered["no_vocab_match"] += 1
            continue
        score, risk, risk_reason = score_sentence(sentence, matches)
        rows.append(
            MaterialRow(
                source_url=url,
                source_domain=domain,
                source_title=title,
                sentence=sentence,
                matched_words=" / ".join(word for word, _ in matches),
                matched_word_count=len(matches),
                matched_classes=" / ".join(sorted({klass for _, klass in matches})),
                quality_score=score,
                risk_level=risk,
                risk_reason=risk_reason,
                candidate_status="raw_candidate",
            )
        )
    return rows, filtered


def write_outputs(rows: list[MaterialRow], filtered: Counter, errors: list[str], urls: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(MaterialRow.__dataclass_fields__.keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    JSON_PATH.write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2), encoding="utf-8")

    risk_counts = Counter(row.risk_level for row in rows)
    word_counts = Counter()
    domain_counts = Counter(row.source_domain for row in rows)
    for row in rows:
        for word in row.matched_words.split(" / "):
            if word:
                word_counts[word] += 1

    lines = [
        "# Web Sentence Materials Report",
        "",
        f"- URL count: {len(urls)}",
        f"- Candidate sentence count: {len(rows)}",
        f"- low / medium / high: {risk_counts.get('low', 0)} / {risk_counts.get('medium', 0)} / {risk_counts.get('high', 0)}",
        f"- CSV: `{CSV_PATH}`",
        f"- JSON: `{JSON_PATH}`",
        "",
        "## Domain Counts",
        "| domain | count |",
        "| --- | --- |",
    ]
    lines.extend(f"| {domain} | {count} |" for domain, count in domain_counts.most_common(30))
    lines.extend(["", "## Top Matched Words", "| word | count |", "| --- | --- |"])
    lines.extend(f"| {word} | {count} |" for word, count in word_counts.most_common(50))
    lines.extend(["", "## Filter Reasons", "| reason | count |", "| --- | --- |"])
    lines.extend(f"| {reason} | {count} |" for reason, count in filtered.most_common())
    if errors:
        lines.extend(["", "## Fetch Errors", "| error |", "| --- |"])
        for error in errors:
            safe_error = error.replace("|", "\\|")
            lines.append(f"| {safe_error} |")
    lines.extend(["", "## Sample Candidates", "| url | words | score | risk | sentence |", "| --- | --- | --- | --- | --- |"])
    for row in rows[:30]:
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                row.source_url,
                row.matched_words.replace("|", "\\|"),
                row.quality_score,
                row.risk_level,
                row.sentence.replace("|", "\\|"),
            )
        )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Japanese web pages and keep real sentences matching N2 vocab layers.")
    parser.add_argument("--urls", type=Path, default=DEFAULT_URLS_PATH, help="Text file with one URL per line.")
    parser.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB_PATH, help="Layered vocab CSV. Defaults to data/output/n2_vocab_context_layers.csv.")
    parser.add_argument("--classes", default="A", help="Comma-separated vocab classes to match, e.g. A or A,B,C.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds.")
    parser.add_argument("--max-pages", type=int, default=0, help="Optional max pages to fetch. 0 means no limit.")
    parser.add_argument("--ignore-robots", action="store_true", help="Skip robots.txt check. Use only when you have permission.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    classes = {item.strip() for item in args.classes.split(",") if item.strip()}
    urls = read_urls(args.urls)
    if args.max_pages:
        urls = urls[: args.max_pages]
    if not urls:
        print(f"No URLs found. Add one URL per line to: {args.urls}")
        print("No scraping was performed.")
        return 0

    vocab = load_vocab(args.vocab, classes)
    rows: list[MaterialRow] = []
    filtered = Counter()
    errors: list[str] = []

    for index, url in enumerate(urls, 1):
        try:
            if not args.ignore_robots and not can_fetch(url, USER_AGENT, args.timeout):
                errors.append(f"robots_disallow: {url}")
                continue
            html, final_url = fetch_html(url, args.timeout)
            title, text = html_to_text(html)
            page_rows, page_filtered = build_rows(final_url, title or final_url, text, vocab)
            rows.extend(page_rows)
            filtered.update(page_filtered)
            print(f"[{index}/{len(urls)}] {final_url} -> {len(page_rows)} candidates")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            print(f"[{index}/{len(urls)}] ERROR {url}: {exc}")
        if index < len(urls) and args.delay > 0:
            time.sleep(args.delay)

    rows.sort(key=lambda row: (-row.quality_score, row.risk_level, row.source_domain, row.sentence))
    write_outputs(rows, filtered, errors, urls)

    risk_counts = Counter(row.risk_level for row in rows)
    print(f"候选句子数量: {len(rows)}")
    print(f"输出 CSV 路径: {CSV_PATH}")
    print(f"输出 JSON 路径: {JSON_PATH}")
    print(f"报告路径: {REPORT_PATH}")
    print(f"low / medium / high 数量: {risk_counts.get('low', 0)} / {risk_counts.get('medium', 0)} / {risk_counts.get('high', 0)}")
    if errors:
        print(f"抓取错误/跳过数量: {len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
