from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"
DEFAULT_SEEDS = PROJECT_ROOT / "data" / "crawl_seed_sites_life_work_edu_news.csv"
SCRAPER_PATH = PROJECT_ROOT / "tools" / "scrape_japanese_sentence_materials.py"
FALLBACK_CRAWLER_PATH = PROJECT_ROOT / "tools" / "crawl_web_sentence_materials.py"

USER_AGENT = "jlpt-context-material-builder/0.1 (+educational research; sitemap-first crawl)"

URL_KEYWORDS = [
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
    "faq",
    "help",
    "support",
    "guide",
    "procedure",
    "application",
    "change",
    "料理",
    "レシピ",
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
    "キャリア",
    "ビジネス",
    "仕事",
    "学校",
    "授業",
    "学習",
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

SKIP_FRAGMENTS = {
    "login",
    "auth",
    "signin",
    "signup",
    "mypage",
    "account",
    "cart",
    "checkout",
    "purchase",
    "/tag/",
    "/tags/",
    "?replytocom=",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_seeds(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("start_url")]


def normalize_url(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/")


def same_site(url: str, seed_netloc: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    seed = seed_netloc.lower()
    return netloc == seed or netloc.endswith("." + seed)


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True
    lower = url.lower()
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    return any(fragment in lower for fragment in SKIP_FRAGMENTS)


def url_is_relevant(url: str, include_all: bool = False) -> bool:
    if include_all:
        return True
    lower = url.lower()
    return any(keyword.lower() in lower for keyword in URL_KEYWORDS)


class RobotsCache:
    def __init__(self, session: requests.Session) -> None:
        self.session = session
        self.parsers: dict[str, RobotFileParser | None] = {}
        self.sitemaps: dict[str, list[str]] = {}

    def base(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def load(self, url: str) -> None:
        base = self.base(url)
        if base in self.parsers:
            return
        robots_url = base + "/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            text = self.session.get(robots_url, timeout=15).text
            parser.parse(text.splitlines())
            sitemap_urls = []
            for line in text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_urls.append(line.split(":", 1)[1].strip())
            self.parsers[base] = parser
            self.sitemaps[base] = sitemap_urls
        except Exception:
            self.parsers[base] = None
            self.sitemaps[base] = []

    def can_fetch(self, url: str) -> bool:
        self.load(url)
        parser = self.parsers.get(self.base(url))
        if parser is None:
            return True
        return parser.can_fetch(USER_AGENT, url)

    def sitemap_urls(self, url: str) -> list[str]:
        self.load(url)
        return self.sitemaps.get(self.base(url), [])


def candidate_sitemaps(start_url: str, robots: RobotsCache) -> list[str]:
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    urls = list(robots.sitemap_urls(start_url))
    urls.extend(
        [
            base + "/sitemap.xml",
            base + "/sitemap_index.xml",
            base + "/sitemap-index.xml",
        ]
    )
    seen = set()
    result = []
    for url in urls:
        url = normalize_url(url)
        if url and url not in seen and same_site(url, parsed.netloc):
            seen.add(url)
            result.append(url)
    return result


def fetch_bytes(session: requests.Session, url: str, timeout: int) -> bytes:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def decode_sitemap_bytes(url: str, content: bytes) -> str:
    if url.endswith(".gz"):
        content = gzip.decompress(content)
    return content.decode("utf-8", errors="replace")


def xml_text(element: ET.Element, name: str) -> str:
    for child in element:
        if child.tag.endswith(name):
            return (child.text or "").strip()
    return ""


def parse_sitemap_xml(text: str) -> tuple[list[str], list[str]]:
    root = ET.fromstring(text)
    sitemap_links: list[str] = []
    page_links: list[str] = []
    if root.tag.endswith("sitemapindex"):
        for sitemap in root:
            if sitemap.tag.endswith("sitemap"):
                loc = xml_text(sitemap, "loc")
                if loc:
                    sitemap_links.append(loc)
    elif root.tag.endswith("urlset"):
        for url_node in root:
            if url_node.tag.endswith("url"):
                loc = xml_text(url_node, "loc")
                if loc:
                    page_links.append(loc)
    return sitemap_links, page_links


def discover_urls_from_sitemaps(
    session: requests.Session,
    start_url: str,
    robots: RobotsCache,
    max_sitemaps: int,
    max_urls: int,
    timeout: int,
    include_all: bool,
) -> tuple[list[str], Counter]:
    seed_netloc = urlparse(start_url).netloc
    queue = candidate_sitemaps(start_url, robots)
    seen_sitemaps: set[str] = set()
    page_urls: list[str] = []
    stats: Counter = Counter()

    while queue and len(seen_sitemaps) < max_sitemaps and len(page_urls) < max_urls:
        sitemap_url = normalize_url(queue.pop(0))
        if sitemap_url in seen_sitemaps or not same_site(sitemap_url, seed_netloc):
            continue
        seen_sitemaps.add(sitemap_url)
        try:
            content = fetch_bytes(session, sitemap_url, timeout)
            text = decode_sitemap_bytes(sitemap_url, content)
            sitemap_links, links = parse_sitemap_xml(text)
            stats["sitemaps_read"] += 1
            for child_sitemap in sitemap_links:
                child_sitemap = normalize_url(child_sitemap)
                if child_sitemap not in seen_sitemaps and same_site(child_sitemap, seed_netloc):
                    queue.append(child_sitemap)
            for link in links:
                link = normalize_url(link)
                if not same_site(link, seed_netloc) or should_skip_url(link):
                    continue
                if not url_is_relevant(link, include_all=include_all):
                    stats["irrelevant_url"] += 1
                    continue
                page_urls.append(link)
                if len(page_urls) >= max_urls:
                    break
        except Exception:
            stats["sitemap_errors"] += 1

    # Stable de-dupe while preserving sitemap order.
    seen_pages = set()
    unique_pages = []
    for url in page_urls:
        if url not in seen_pages:
            seen_pages.add(url)
            unique_pages.append(url)
    return unique_pages[:max_urls], stats


def response_text(response: requests.Response) -> str:
    detected = response.apparent_encoding or "utf-8"
    if not response.encoding or response.encoding.lower() in {"iso-8859-1", "latin-1", "ascii"}:
        response.encoding = detected
    return response.text


def fetch_html(session: requests.Session, url: str, timeout: int) -> tuple[str, str]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    ctype = response.headers.get("Content-Type", "")
    if ctype and "html" not in ctype and "xhtml" not in ctype:
        raise ValueError(f"non_html_content_type={ctype}")
    return response_text(response), response.url


def append_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sitemap-first crawler for targeted Japanese sentence materials.")
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--classes", default="A,B,C")
    parser.add_argument("--max-urls-per-site", type=int, default=300)
    parser.add_argument("--max-sitemaps-per-site", type=int, default=80)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--max-sites", type=int, default=0)
    parser.add_argument("--include-all-sitemap-urls", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scraper = load_module("sentence_scraper", SCRAPER_PATH)
    fallback = load_module("fallback_crawler", FALLBACK_CRAWLER_PATH)

    seeds = read_seeds(args.seeds)
    if args.max_sites:
        seeds = seeds[: args.max_sites]

    run_dir = OUTPUT_ROOT / f"sitemap_crawl_{args.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    page_csv = run_dir / "crawled_pages.csv"
    page_jsonl = run_dir / "crawled_pages_text.jsonl"
    material_csv = run_dir / "web_sentence_materials.csv"
    material_jsonl = run_dir / "web_sentence_materials.jsonl"
    discovered_csv = run_dir / "discovered_urls.csv"
    log_path = run_dir / "crawl.log"
    report_path = run_dir / "crawl_report.md"

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"})
    robots = RobotsCache(session)
    vocab = scraper.load_vocab(scraper.DEFAULT_VOCAB_PATH, {item.strip() for item in args.classes.split(",") if item.strip()})

    stats: Counter = Counter()
    errors: list[str] = []
    material_fields = list(scraper.MaterialRow.__dataclass_fields__.keys())
    page_fields = ["group", "name", "url", "final_url", "title", "text_length", "sentence_count", "candidate_count", "discovery_method"]
    discovered_fields = ["group", "name", "url", "method"]

    def log(message: str) -> None:
        stamped = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(stamped)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(stamped + "\n")

    def write_report() -> None:
        lines = [
            "# Sitemap Priority Crawl Report",
            "",
            f"- run_dir: `{run_dir}`",
            f"- fetched_pages: {stats.get('fetched_pages', 0)}",
            f"- candidate_sentences: {stats.get('candidate_sentences', 0)}",
            f"- discovered_urls: {stats.get('discovered_urls', 0)}",
            f"- sitemap_pages_read: {stats.get('sitemaps_read', 0)}",
            f"- errors: {len(errors)}",
            "",
            "## Per Site",
            "| site | discovered | fetched | candidates | sitemap_read | sitemap_errors |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        sites = sorted({k.split(":", 1)[1] for k in stats if k.startswith("site_discovered:") or k.startswith("site_fetched:")})
        for site in sites:
            lines.append(
                f"| {site} | {stats.get('site_discovered:' + site, 0)} | {stats.get('site_fetched:' + site, 0)} | "
                f"{stats.get('site_candidates:' + site, 0)} | {stats.get('site_sitemaps:' + site, 0)} | "
                f"{stats.get('site_sitemap_errors:' + site, 0)} |"
            )
        if errors:
            lines.extend(["", "## Errors", "| error |", "| --- |"])
            for err in errors[:300]:
                safe_err = err.replace("|", "\\|")
                lines.append(f"| {safe_err} |")
        report_path.write_text("\n".join(lines), encoding="utf-8")

    log(f"START seeds={len(seeds)} classes={args.classes} max_urls_per_site={args.max_urls_per_site}")

    for idx, seed in enumerate(seeds, 1):
        group = seed.get("group", "")
        name = seed.get("name", f"site{idx}")
        start_url = normalize_url(seed["start_url"])
        log(f"[{idx}/{len(seeds)}] SITE_START {name} {start_url}")

        urls, sitemap_stats = discover_urls_from_sitemaps(
            session,
            start_url,
            robots,
            args.max_sitemaps_per_site,
            args.max_urls_per_site,
            args.timeout,
            args.include_all_sitemap_urls,
        )
        stats.update(sitemap_stats)
        stats["site_sitemaps:" + name] += sitemap_stats.get("sitemaps_read", 0)
        stats["site_sitemap_errors:" + name] += sitemap_stats.get("sitemap_errors", 0)

        method = "sitemap"
        if not urls:
            # Fallback: use the older same-site link extractor just on the start page.
            try:
                html, final_url = fetch_html(session, start_url, args.timeout)
                seed_netloc = urlparse(start_url).netloc
                urls = fallback.extract_links(html, final_url, seed_netloc)[: args.max_urls_per_site]
                if start_url not in urls:
                    urls.insert(0, start_url)
                method = "fallback_links"
            except Exception as exc:
                errors.append(f"{name} discovery failed: {type(exc).__name__}: {exc}")
                urls = [start_url]
                method = "start_only"

        stats["discovered_urls"] += len(urls)
        stats["site_discovered:" + name] += len(urls)
        append_csv(discovered_csv, discovered_fields, [{"group": group, "name": name, "url": u, "method": method} for u in urls])
        log(f"SITE_DISCOVERED {name} method={method} urls={len(urls)}")

        fetched = 0
        candidates = 0
        for url in urls:
            if should_skip_url(url) or not robots.can_fetch(url):
                continue
            try:
                html, final_url = fetch_html(session, url, args.timeout)
                if should_skip_url(final_url):
                    continue
                title, text = scraper.html_to_text(html)
                text = scraper.clean_text(text)
                sentences = scraper.split_sentences(text)
                page_rows, page_filtered = scraper.build_rows(final_url, title or final_url, text, vocab)
                page_row = {
                    "group": group,
                    "name": name,
                    "url": url,
                    "final_url": final_url,
                    "title": title or final_url,
                    "text_length": len(text),
                    "sentence_count": len(sentences),
                    "candidate_count": len(page_rows),
                    "discovery_method": method,
                }
                append_csv(page_csv, page_fields, [page_row])
                append_jsonl(page_jsonl, [{**page_row, "text": text}])
                append_csv(material_csv, material_fields, [asdict(row) for row in page_rows])
                append_jsonl(material_jsonl, [asdict(row) for row in page_rows])
                fetched += 1
                candidates += len(page_rows)
                stats["fetched_pages"] += 1
                stats["candidate_sentences"] += len(page_rows)
                stats["site_fetched:" + name] += 1
                stats["site_candidates:" + name] += len(page_rows)
                if fetched % 25 == 0:
                    log(f"SITE_PROGRESS {name} fetched={fetched} candidates={candidates}")
            except Exception as exc:
                errors.append(f"{name} {url}: {type(exc).__name__}: {exc}")
            if args.delay > 0:
                time.sleep(args.delay)

        log(f"SITE_DONE {name} discovered={len(urls)} fetched={fetched} candidates={candidates}")
        write_report()

    write_report()
    log(f"DONE fetched_pages={stats.get('fetched_pages', 0)} candidate_sentences={stats.get('candidate_sentences', 0)} errors={len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
