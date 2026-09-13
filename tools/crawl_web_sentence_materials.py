from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
import time
from collections import Counter, deque
from dataclasses import asdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEEDS_PATH = PROJECT_ROOT / "data" / "crawl_seed_sites.csv"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"
SCRAPER_PATH = PROJECT_ROOT / "tools" / "scrape_japanese_sentence_materials.py"

USER_AGENT = "jlpt-context-material-builder/0.1 (+educational research; local controlled crawl)"

LINK_KEYWORDS = [
    "手続",
    "申請",
    "届出",
    "変更",
    "確認",
    "提出",
    "登録",
    "解約",
    "契約",
    "料金",
    "支払",
    "本人確認",
    "必要書類",
    "証明",
    "FAQ",
    "faq",
    "よくある",
    "サポート",
    "ヘルプ",
    "問い合わせ",
    "guide",
    "support",
    "help",
    "procedure",
    "application",
    "change",
    "cancel",
    "price",
    "fee",
    "payment",
    "料理",
    "レシピ",
    "作り方",
    "食材",
    "献立",
    "健康",
    "病気",
    "医療",
    "予防",
    "症状",
    "治療",
    "育児",
    "子育て",
    "妊娠",
    "出産",
    "保育",
    "転職",
    "求人",
    "面接",
    "履歴書",
    "職務経歴書",
    "キャリア",
    "ビジネス",
    "仕事",
    "働き方",
    "学校",
    "授業",
    "学習",
    "勉強",
    "教育",
    "入学",
    "受験",
    "試験",
    "塾",
    "ニュース",
    "社会",
    "経済",
    "政治",
    "国際",
    "暮らし",
    "生活",
    "recipe",
    "health",
    "career",
    "job",
    "education",
    "school",
    "news",
]

SKIP_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".css",
    ".js",
    ".mp4",
    ".mp3",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".pptx",
}

SKIP_URL_FRAGMENTS = {
    "/login",
    "/auth",
    "/signin",
    "/signup",
    "/register",
    "/mypage",
    "/my/",
    "/account",
    "/cart",
    "/basket",
    "/checkout",
    "/purchase",
    "/entry",
    "login",
    "auth",
    "signin",
    "signup",
    "mypage",
    "account",
    "cart",
    "checkout",
}


def load_scraper_module():
    spec = importlib.util.spec_from_file_location("sentence_scraper", SCRAPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scraper module: {SCRAPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["sentence_scraper"] = module
    spec.loader.exec_module(module)
    return module


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = None
        for key, value in attrs:
            if key.lower() == "href":
                href = value
                break
        self._href = href
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = re.sub(r"\s+", " ", "".join(self._text)).strip()
            self.links.append((self._href, text))
            self._href = None
            self._text = []


def read_seeds(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("start_url")]


def normalize_url(url: str) -> str:
    url, _fragment = urldefrag(url)
    return url.rstrip("/")


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    lower_path = parsed.path.lower()
    lower_url = url.lower()
    if any(lower_path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    return any(fragment in lower_path or fragment in lower_url for fragment in SKIP_URL_FRAGMENTS)


def same_site(url: str, seed_netloc: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    seed = seed_netloc.lower()
    return netloc == seed or netloc.endswith("." + seed)


def link_is_relevant(url: str, text: str) -> bool:
    haystack = (url + " " + text).lower()
    return any(keyword.lower() in haystack for keyword in LINK_KEYWORDS)


def extract_links(html: str, base_url: str, seed_netloc: str) -> list[str]:
    parser = LinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        return []
    links: list[str] = []
    seen: set[str] = set()
    for href, text in parser.links:
        absolute = normalize_url(urljoin(base_url, href))
        if should_skip_url(absolute):
            continue
        if not same_site(absolute, seed_netloc):
            continue
        if not link_is_relevant(absolute, text):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)
    return links


class RobotsCache:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self.cache: dict[str, RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self.cache:
            robot = RobotFileParser()
            robot.set_url(base + "/robots.txt")
            try:
                robot.read()
                self.cache[base] = robot
            except Exception:
                self.cache[base] = None
        robot = self.cache[base]
        if robot is None:
            return True
        return robot.can_fetch(self.user_agent, url)


def fetch_html(session: requests.Session, url: str, timeout: int) -> tuple[str, str]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type and content_type:
        raise ValueError(f"non_html_content_type={content_type}")
    detected = response.apparent_encoding or "utf-8"
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1", "ascii"}:
        response.encoding = detected
    return response.text, response.url


def append_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_run_report(run_dir: Path, stats: Counter, errors: list[str]) -> None:
    lines = [
        "# Overnight Web Crawl Report",
        "",
        f"- run_dir: `{run_dir}`",
        f"- fetched_pages: {stats.get('fetched_pages', 0)}",
        f"- candidate_sentences: {stats.get('candidate_sentences', 0)}",
        f"- skipped_by_robots: {stats.get('robots_disallow', 0)}",
        f"- fetch_errors: {len(errors)}",
        "",
        "## Per Site",
        "| site | fetched_pages | candidate_sentences | queued_seen |",
        "| --- | --- | --- | --- |",
    ]
    site_names = sorted({key.split(":", 1)[1] for key in stats if key.startswith("site_pages:")})
    for site in site_names:
        lines.append(
            f"| {site} | {stats.get('site_pages:' + site, 0)} | "
            f"{stats.get('site_candidates:' + site, 0)} | {stats.get('site_seen:' + site, 0)} |"
        )
    if errors:
        lines.extend(["", "## Errors", "| error |", "| --- |"])
        for error in errors[:300]:
            safe_error = error.replace("|", "\\|")
            lines.append(f"| {safe_error} |")
    (run_dir / "crawl_report.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled same-site crawler for Japanese real-sentence material collection.")
    parser.add_argument("--seeds", type=Path, default=SEEDS_PATH)
    parser.add_argument("--classes", default="A,B,C")
    parser.add_argument("--max-pages-per-site", type=int, default=80)
    parser.add_argument("--max-sites", type=int, default=0)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scraper = load_scraper_module()
    seeds = read_seeds(args.seeds)
    if args.max_sites:
        seeds = seeds[: args.max_sites]
    run_dir = OUTPUT_ROOT / f"web_crawl_{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    page_csv = run_dir / "crawled_pages.csv"
    page_jsonl = run_dir / "crawled_pages_text.jsonl"
    material_csv = run_dir / "web_sentence_materials.csv"
    material_jsonl = run_dir / "web_sentence_materials.jsonl"
    log_path = run_dir / "crawl.log"

    vocab = scraper.load_vocab(scraper.DEFAULT_VOCAB_PATH, {item.strip() for item in args.classes.split(",") if item.strip()})
    robots = RobotsCache(USER_AGENT)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"})

    stats: Counter = Counter()
    errors: list[str] = []
    material_fields = list(scraper.MaterialRow.__dataclass_fields__.keys())
    page_fields = [
        "group",
        "name",
        "url",
        "final_url",
        "depth",
        "title",
        "text_length",
        "sentence_count",
        "candidate_count",
        "discovered_links",
    ]

    def log(message: str) -> None:
        stamped = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(stamped)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(stamped + "\n")

    log(f"START seeds={len(seeds)} classes={args.classes} max_pages_per_site={args.max_pages_per_site} max_depth={args.max_depth}")

    for seed_index, seed in enumerate(seeds, 1):
        site_name = seed.get("name", f"site{seed_index}")
        group = seed.get("group", "")
        start_url = normalize_url(seed["start_url"])
        seed_netloc = urlparse(start_url).netloc
        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        seen: set[str] = set()
        fetched_for_site = 0

        log(f"[{seed_index}/{len(seeds)}] SITE_START {site_name} {start_url}")

        while queue and fetched_for_site < args.max_pages_per_site:
            url, depth = queue.popleft()
            url = normalize_url(url)
            if url in seen:
                continue
            seen.add(url)
            if should_skip_url(url):
                continue
            if not args.ignore_robots and not robots.can_fetch(url):
                stats["robots_disallow"] += 1
                continue

            try:
                html, final_url = fetch_html(session, url, args.timeout)
                if should_skip_url(final_url):
                    continue
                title, text = scraper.html_to_text(html)
                text = scraper.clean_text(text)
                sentences = scraper.split_sentences(text)
                page_rows, page_filtered = scraper.build_rows(final_url, title or final_url, text, vocab)
                links = extract_links(html, final_url, seed_netloc) if depth < args.max_depth else []

                for link in links:
                    if link not in seen:
                        queue.append((link, depth + 1))

                page_row = {
                    "group": group,
                    "name": site_name,
                    "url": url,
                    "final_url": final_url,
                    "depth": depth,
                    "title": title or final_url,
                    "text_length": len(text),
                    "sentence_count": len(sentences),
                    "candidate_count": len(page_rows),
                    "discovered_links": len(links),
                }
                append_csv(page_csv, page_fields, [page_row])
                append_jsonl(
                    page_jsonl,
                    [
                        {
                            **page_row,
                            "text": text,
                        }
                    ],
                )
                append_csv(material_csv, material_fields, [asdict(row) for row in page_rows])
                append_jsonl(material_jsonl, [asdict(row) for row in page_rows])

                fetched_for_site += 1
                stats["fetched_pages"] += 1
                stats["candidate_sentences"] += len(page_rows)
                stats["site_pages:" + site_name] += 1
                stats["site_candidates:" + site_name] += len(page_rows)
                stats["site_seen:" + site_name] = len(seen)

                log(
                    f"PAGE site={site_name} depth={depth} candidates={len(page_rows)} "
                    f"sentences={len(sentences)} links={len(links)} url={final_url}"
                )
            except Exception as exc:
                message = f"{site_name} {url}: {type(exc).__name__}: {exc}"
                errors.append(message)
                log("ERROR " + message)

            if args.delay > 0:
                time.sleep(args.delay)

        log(f"SITE_DONE {site_name} fetched={fetched_for_site} seen={len(seen)} queued={len(queue)}")
        write_run_report(run_dir, stats, errors)

    write_run_report(run_dir, stats, errors)
    log(f"DONE fetched_pages={stats.get('fetched_pages', 0)} candidate_sentences={stats.get('candidate_sentences', 0)} errors={len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
