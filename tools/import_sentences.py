"""
三源例句导入工具
优先级：web_crawl > tatoeba > gpt（保留，不覆盖）

使用方法：
  python tools/import_sentences.py --preview           # 预览统计，不写库
  python tools/import_sentences.py --save              # 写入数据库

Tatoeba 数据下载（一次性，约 60MB）：
  python tools/import_sentences.py --download-tatoeba
  下载到：data/tatoeba/jpn_sentences.tsv
           data/tatoeba/cmn_sentences.tsv
           data/tatoeba/links.csv
"""
from __future__ import annotations

import argparse
import bz2
import csv
import re
import sqlite3
import sys
import tarfile
import urllib.request
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT   = Path(__file__).resolve().parents[1]
DB_PATH        = PROJECT_ROOT / "data" / "n2.db"
MERGED_CSV     = PROJECT_ROOT / "data" / "output" / "merged_web_sentence_materials.csv"
TATOEBA_DIR    = PROJECT_ROOT / "data" / "tatoeba"

TATOEBA_URLS = {
    "jpn_sentences.tsv": "https://downloads.tatoeba.org/exports/per_language/jpn/jpn_sentences.tsv.bz2",
    "cmn_sentences.tsv": "https://downloads.tatoeba.org/exports/per_language/cmn/cmn_sentences.tsv.bz2",
    "links.csv":         "https://downloads.tatoeba.org/exports/links.tar.bz2",  # tar.bz2 containing links.csv
}

# 句子开头不应是助词/片段标志
_BAD_START = re.compile(r"^[（(※【★●▶◆\*\-・\s]|^[のがをにはもへでやとからまでより]")


def is_good(sentence: str, word: str, min_word_len: int = 2) -> bool:
    if len(word) < min_word_len:
        return False
    if word not in sentence:
        return False
    if not (15 <= len(sentence) <= 80):
        return False
    if sentence[-1] not in "。！？!?":
        return False
    if _BAD_START.match(sentence):
        return False
    return True


# ── 第1源：web crawl ─────────────────────────────────────────────────────────

def load_web_crawl(words_in_db: set[str]) -> dict[str, str]:
    if not MERGED_CSV.exists():
        print(f"[web] 文件不存在：{MERGED_CSV}")
        return {}

    word_to_sent: dict[str, str] = {}
    with open(MERGED_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            s = row["sentence"]
            matched = [w.strip() for w in row["matched_words"].split("/") if w.strip()]
            for word in matched:
                if word not in words_in_db:
                    continue
                if not is_good(s, word):
                    continue
                if word not in word_to_sent or len(s) < len(word_to_sent[word]):
                    word_to_sent[word] = s
    return word_to_sent


# ── 第2源：Tatoeba ───────────────────────────────────────────────────────────

def _open_tsv(path: Path):
    """打开 .tsv 或 .tsv.bz2，返回文本行迭代器。"""
    bz2_path = path.with_suffix(path.suffix + ".bz2")
    if path.exists():
        return open(path, encoding="utf-8")
    if bz2_path.exists():
        return bz2.open(bz2_path, "rt", encoding="utf-8")
    return None


def load_tatoeba(words_in_db: set[str], already_covered: set[str]) -> dict[str, str]:
    jpn_path   = TATOEBA_DIR / "jpn_sentences.tsv"
    cmn_path   = TATOEBA_DIR / "cmn_sentences.tsv"
    links_path = TATOEBA_DIR / "links.csv"

    jpn_f   = _open_tsv(jpn_path)
    cmn_f   = _open_tsv(cmn_path)
    links_f = _open_tsv(links_path)

    if jpn_f is None or links_f is None:
        print("[tatoeba] 数据文件不存在，跳过。运行 --download-tatoeba 下载。")
        return {}
    if cmn_f is None:
        print("[tatoeba] cmn_sentences.tsv 不存在，跳过中文翻译过滤。")

    # 1. 收集所有中文句子 ID
    cmn_ids: set[str] = set()
    if cmn_f:
        for line in cmn_f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                cmn_ids.add(parts[0])
        cmn_f.close()
    print(f"[tatoeba] cmn句子数: {len(cmn_ids)}")

    # 2. 从 links 找有中文翻译的日语句子 ID
    jpn_with_cmn: set[str] = set()
    for line in links_f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 2:
            continue
        a, b = parts
        if b in cmn_ids:
            jpn_with_cmn.add(a)
        if a in cmn_ids:
            jpn_with_cmn.add(b)
    links_f.close()
    print(f"[tatoeba] 有中文翻译的日语句子数: {len(jpn_with_cmn)}")

    # 3. 扫描日语句子，匹配未覆盖的词
    need_words = words_in_db - already_covered
    word_to_sent: dict[str, str] = {}

    for line in jpn_f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            continue
        sid, _lang, text = parts[0], parts[1], parts[2]
        if sid not in jpn_with_cmn:
            continue
        for word in need_words:
            if not is_good(text, word):
                continue
            if word not in word_to_sent or len(text) < len(word_to_sent[word]):
                word_to_sent[word] = text
    jpn_f.close()

    return word_to_sent


# ── 下载 Tatoeba ─────────────────────────────────────────────────────────────

def _stream_download(url: str, dest: Path, chunk_size: int = 1024 * 1024) -> None:
    """流式下载，支持断点续传，显示进度。"""
    existing = dest.stat().st_size if dest.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    resp = requests.get(url, headers=headers, stream=True, timeout=60)
    total = int(resp.headers.get("Content-Length", 0)) + existing
    mode = "ab" if existing and resp.status_code == 206 else "wb"
    if resp.status_code not in (200, 206):
        resp.raise_for_status()
    downloaded = existing
    with open(dest, mode) as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r  {downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB  ({pct}%)", end="", flush=True)
    print()


def download_tatoeba() -> None:
    TATOEBA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in TATOEBA_URLS.items():
        dest = TATOEBA_DIR / filename
        if dest.exists():
            print(f"[skip] 已存在: {dest}")
            continue
        is_tar = url.endswith(".tar.bz2")
        tmp_ext = ".tar.bz2" if is_tar else ".bz2"
        tmp = TATOEBA_DIR / (filename + tmp_ext)
        print(f"[下载] {url}")
        _stream_download(url, tmp)
        print(f"[解压] {tmp}")
        if is_tar:
            with tarfile.open(tmp, "r:bz2") as tf:
                member = next(m for m in tf.getmembers() if m.name.endswith(filename))
                with tf.extractfile(member) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
        else:
            with bz2.open(tmp, "rb") as src, open(dest, "wb") as dst:
                dst.write(src.read())
        tmp.unlink()
        print(f"[完成] {dest}  ({dest.stat().st_size // 1024 // 1024} MB)")


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save",              action="store_true", help="写入数据库（默认预览）")
    parser.add_argument("--download-tatoeba",  action="store_true", help="下载 Tatoeba 数据")
    args = parser.parse_args()

    if args.download_tatoeba:
        download_tatoeba()
        return

    conn = sqlite3.connect(str(DB_PATH))
    words_in_db: set[str] = {r[0] for r in conn.execute("SELECT word FROM words").fetchall()}
    word_to_id:  dict[str, int] = {
        r[0]: r[1] for r in conn.execute("SELECT word, id FROM words").fetchall()
    }
    print(f"词库总词数: {len(words_in_db)}")

    # ── 第1源 ──
    print("\n=== 第1源：web crawl ===")
    web_map = load_web_crawl(words_in_db)
    print(f"覆盖词数: {len(web_map)}")

    # ── 第2源 ──
    print("\n=== 第2源：Tatoeba ===")
    tatoeba_map = load_tatoeba(words_in_db, set(web_map.keys()))
    print(f"额外覆盖词数: {len(tatoeba_map)}")

    # ── 合并 ──
    final_map: dict[str, tuple[str, str]] = {}  # word -> (sentence, source)
    for word, sent in web_map.items():
        final_map[word] = (sent, "web_crawl")
    for word, sent in tatoeba_map.items():
        if word not in final_map:
            final_map[word] = (sent, "tatoeba")

    total_new = len(final_map)
    print(f"\n合计可导入: {total_new} 词 ({total_new/len(words_in_db)*100:.1f}%)")
    print("（未覆盖的词保留原有 GPT 句子）")

    # ── 预览 ──
    print("\n=== 预览（前10条）===")
    for word, (sent, src) in list(final_map.items())[:10]:
        print(f"  [{src}][{word}] {sent}")

    if not args.save:
        print("\n预览模式，未写库。加 --save 参数写入。")
        conn.close()
        return

    # ── 写库 ──
    updated = 0
    for word, (sent, src) in final_map.items():
        wid = word_to_id.get(word)
        if not wid:
            continue
        conn.execute(
            """INSERT INTO word_sentences (word_id, sentence, source)
               VALUES (?, ?, ?)
               ON CONFLICT(word_id) DO UPDATE SET
                 sentence = excluded.sentence,
                 source   = excluded.source""",
            (wid, sent, src),
        )
        updated += 1
    conn.commit()
    conn.close()

    print(f"\n已写入 word_sentences 表：{updated} 条")
    print("来源: web_crawl > tatoeba，GPT句子保留作兜底")


if __name__ == "__main__":
    main()
