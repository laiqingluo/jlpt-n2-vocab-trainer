"""
网页语料 → 词汇匹配脚本
使用方法：
  python match_sentences.py
"""

import csv
import re
import os
from collections import defaultdict

INPUT_SENTENCES = r"E:\codex\jlpt背单词\data\output\web_crawl_overnight_fixed_20260517_2317\web_sentence_materials.csv"
INPUT_VOCAB     = r"E:\codex\jlpt背单词\data\n2_vocab.csv"
OUTPUT          = r"E:\codex\jlpt背单词\n2_web_matched.csv"

MAX_PER_WORD = 3
MIN_LEN = 15
MAX_LEN = 80

# ============================================================

def load_vocab(path):
    words = {}
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            word = row.get('word', '').strip()
            if not word or len(word) <= 1:
                continue
            words[word] = {
                'reading':     row.get('reading', '').strip(),
                'pos':         row.get('pos', '').strip(),
                'meaning':     row.get('meaning', '').strip(),
                'is_n2_core':  row.get('is_n2_core', '').strip(),
                'quadrant':    row.get('quadrant', '').strip(),
                'count':       row.get('count', '0').strip(),
                'collocation': row.get('collocation', '').strip(),
            }
    return words


def is_good_sentence(sentence):
    if len(sentence) < MIN_LEN or len(sentence) > MAX_LEN:
        return False
    if 'http' in sentence or 'www.' in sentence:
        return False
    if re.search(r'\d{5,}', sentence):
        return False
    jp_chars = len(re.findall(r'[\u3040-\u9fff]', sentence))
    if jp_chars < len(sentence) * 0.4:
        return False
    if re.search(r'とは[、。]|という意味|を意味する', sentence):
        return False
    return True


def main():
    print("=" * 50)
    print("网页语料词汇匹配")
    print("=" * 50)

    for f in [INPUT_SENTENCES, INPUT_VOCAB]:
        if not os.path.exists(f):
            print(f"错误：找不到 {f}")
            return

    print("加载词汇表...")
    vocab = load_vocab(INPUT_VOCAB)
    print(f"词汇数：{len(vocab)}")

    matched = defaultdict(list)

    print("扫描句子文件...")
    total = 0
    hit   = 0

    with open(INPUT_SENTENCES, encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        sent_col = next((c for c in fieldnames if 'sent' in c.lower() or 'text' in c.lower() or '文' in c), None)
        if not sent_col:
            sent_col = fieldnames[-1] if fieldnames else None
        print(f"使用列：{sent_col}，所有列：{fieldnames[:6]}")

        for row in reader:
            total += 1
            if total % 100000 == 0:
                print(f"  已扫描 {total} 行，命中 {hit} 条...")

            sentence = row.get(sent_col, '').strip()
            if not sentence or not is_good_sentence(sentence):
                continue

            for word in vocab:
                if word in sentence:
                    if len(matched[word]) < MAX_PER_WORD:
                        matched[word].append(sentence)
                        hit += 1

    print(f"扫描完成：共 {total} 行，命中 {hit} 条，覆盖词汇 {len(matched)} 个")

    fieldnames_out = ['word','reading','pos','meaning','is_n2_core',
                      'quadrant','count','collocation','sentence','sentence_rank']

    with open(OUTPUT, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_out)
        writer.writeheader()
        for word, sentences in matched.items():
            info = vocab[word]
            for i, sent in enumerate(sentences, 1):
                writer.writerow({**info, 'word': word,
                                  'sentence': sent, 'sentence_rank': i})

    print(f"已保存到：{OUTPUT}")

    covered    = len(matched)
    total_word = len(vocab)
    print(f"\n覆盖率：{covered}/{total_word} = {covered/total_word*100:.1f}%")
    print("=" * 50)


if __name__ == '__main__':
    main()
