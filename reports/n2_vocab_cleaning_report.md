# n2_vocab CSV Cleaning Report

## 输出文件
- 备份文件：`data/n2_vocab.backup.csv`
- 清洗文件：`data/n2_vocab.cleaned.csv`

## 已修改项

| 行号 | 字段 | 修改前 | 修改后 |
|---:|---|---|---|
| 5595 | `word` | `溺れる` | `溺れる` |
| 5595 | `reading` | `溺れる` | `おぼれる` |
| 5644 | `word` | `double` | `ダブる` |
| 5644 | `reading` | `double` | `だぶる` |

说明：第 5644 行 `reading` 按当前 CSV 习惯使用平假名，因此写为 `だぶる`。

## Unicode 规范化检查

- 兼容汉字：原文件发现 3 处；其中 word/reading 的 2 处已修复，剩余 1 处未修改。

| 行号 | 字段 | 词条 | 字符 | 位置 | NFKC 建议 |
|---:|---|---|---|---:|---|
| 5595 | `collocation` | `溺れる` | `溺` (U+F9EC CJK COMPATIBILITY IDEOGRAPH-F9EC) | 3 | `溺` |

- 半角片假名：38 处。
- 全角英数字：0 处。
- 不可见控制字符：0 处。
- 其他 NFKC 会变化且未列入保留标点的字符：25415 处。

### Unicode 其他疑点明细

| 类型 | 行号 | 字段 | 词条 | 字符 | 位置 | NFKC 建议 |
|---|---:|---|---|---|---:|---|
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 15 | `・` |
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 16 | `・` |
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 17 | `・` |
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 18 | `・` |
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 19 | `・` |
| 半角片假名 | 261 | `examples` | `思い` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 20 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 15 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 16 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 17 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 18 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 19 | `・` |
| 半角片假名 | 1871 | `examples` | `悔しい` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 20 | `・` |
| 半角片假名 | 2153 | `examples` | `赤ちゃん` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 81 | `・` |
| 半角片假名 | 2318 | `examples` | `マニュアル` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 62 | `・` |
| 半角片假名 | 2318 | `examples` | `マニュアル` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 86 | `・` |
| 半角片假名 | 2343 | `examples` | `セラピー` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 9 | `・` |
| 半角片假名 | 2343 | `examples` | `セラピー` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 76 | `・` |
| 半角片假名 | 2343 | `examples` | `セラピー` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 100 | `・` |
| 半角片假名 | 3590 | `examples` | `こもる` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 39 | `・` |
| 半角片假名 | 3590 | `examples` | `こもる` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 40 | `・` |
| 半角片假名 | 3590 | `examples` | `こもる` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 41 | `・` |
| 半角片假名 | 3591 | `examples` | `従事` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 56 | `・` |
| 半角片假名 | 3591 | `examples` | `従事` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 57 | `・` |
| 半角片假名 | 3591 | `examples` | `従事` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 58 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 39 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 40 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 41 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 42 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 43 | `・` |
| 半角片假名 | 3808 | `examples` | `長引く` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 44 | `・` |
| 半角片假名 | 3816 | `examples` | `もたれる` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 12 | `・` |
| 半角片假名 | 3816 | `examples` | `もたれる` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 13 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 27 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 28 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 29 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 30 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 31 | `・` |
| 半角片假名 | 4453 | `examples` | `リゾート` | `･` (U+FF65 HALFWIDTH KATAKANA MIDDLE DOT) | 32 | `・` |
| 其他 NFKC | 2 | `meaning_detail` | `言う` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 2 | `meaning_detail` | `言う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 14 | `\|` |
| 其他 NFKC | 2 | `meaning_detail` | `言う` | `②` (U+2461 CIRCLED DIGIT TWO) | 22 | `2` |
| 其他 NFKC | 2 | `meaning_detail` | `言う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 38 | `\|` |
| 其他 NFKC | 3 | `meaning_detail` | `自分` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 3 | `meaning_detail` | `自分` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 3 | `meaning_detail` | `自分` | `②` (U+2461 CIRCLED DIGIT TWO) | 23 | `2` |
| 其他 NFKC | 3 | `meaning_detail` | `自分` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 38 | `\|` |
| 其他 NFKC | 4 | `meaning_detail` | `ほう` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 4 | `meaning_detail` | `ほう` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 18 | `\|` |
| 其他 NFKC | 4 | `meaning_detail` | `ほう` | `②` (U+2461 CIRCLED DIGIT TWO) | 25 | `2` |
| 其他 NFKC | 4 | `meaning_detail` | `ほう` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 41 | `\|` |
| 其他 NFKC | 5 | `meaning_detail` | `聞く` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 5 | `meaning_detail` | `聞く` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 5 | `meaning_detail` | `聞く` | `②` (U+2461 CIRCLED DIGIT TWO) | 19 | `2` |
| 其他 NFKC | 5 | `meaning_detail` | `聞く` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 32 | `\|` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `②` (U+2461 CIRCLED DIGIT TWO) | 23 | `2` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `？` (U+FF1F FULLWIDTH QUESTION MARK) | 37 | `?` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 38 | `\|` |
| 其他 NFKC | 6 | `meaning_detail` | `思う` | `？` (U+FF1F FULLWIDTH QUESTION MARK) | 44 | `?` |
| 其他 NFKC | 7 | `meaning_detail` | `考える` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 7 | `meaning_detail` | `考える` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 18 | `\|` |
| 其他 NFKC | 7 | `meaning_detail` | `考える` | `②` (U+2461 CIRCLED DIGIT TWO) | 26 | `2` |
| 其他 NFKC | 7 | `meaning_detail` | `考える` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 40 | `\|` |
| 其他 NFKC | 8 | `meaning_detail` | `仕事` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 8 | `meaning_detail` | `仕事` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 8 | `meaning_detail` | `仕事` | `②` (U+2461 CIRCLED DIGIT TWO) | 22 | `2` |
| 其他 NFKC | 8 | `meaning_detail` | `仕事` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 37 | `\|` |
| 其他 NFKC | 9 | `meaning_detail` | `持つ` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 9 | `meaning_detail` | `持つ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 17 | `\|` |
| 其他 NFKC | 9 | `meaning_detail` | `持つ` | `②` (U+2461 CIRCLED DIGIT TWO) | 23 | `2` |
| 其他 NFKC | 9 | `meaning_detail` | `持つ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 35 | `\|` |
| 其他 NFKC | 10 | `meaning_detail` | `話` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 10 | `meaning_detail` | `話` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 16 | `\|` |
| 其他 NFKC | 10 | `meaning_detail` | `話` | `②` (U+2461 CIRCLED DIGIT TWO) | 25 | `2` |
| 其他 NFKC | 10 | `meaning_detail` | `話` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 37 | `\|` |
| 其他 NFKC | 11 | `meaning_detail` | `書く` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 11 | `meaning_detail` | `書く` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 11 | `meaning_detail` | `書く` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 11 | `meaning_detail` | `書く` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 31 | `\|` |
| 其他 NFKC | 12 | `meaning_detail` | `必要` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 12 | `meaning_detail` | `必要` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 12 | `meaning_detail` | `必要` | `②` (U+2461 CIRCLED DIGIT TWO) | 20 | `2` |
| 其他 NFKC | 12 | `meaning_detail` | `必要` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 30 | `\|` |
| 其他 NFKC | 13 | `meaning_detail` | `わかる` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 13 | `meaning_detail` | `わかる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 11 | `\|` |
| 其他 NFKC | 13 | `meaning_detail` | `わかる` | `②` (U+2461 CIRCLED DIGIT TWO) | 17 | `2` |
| 其他 NFKC | 13 | `meaning_detail` | `わかる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 27 | `\|` |
| 其他 NFKC | 14 | `meaning_detail` | `子ども` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 14 | `meaning_detail` | `子ども` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 14 | `\|` |
| 其他 NFKC | 14 | `meaning_detail` | `子ども` | `②` (U+2461 CIRCLED DIGIT TWO) | 20 | `2` |
| 其他 NFKC | 14 | `meaning_detail` | `子ども` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 31 | `\|` |
| 其他 NFKC | 15 | `meaning_detail` | `読む` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 15 | `meaning_detail` | `読む` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 9 | `\|` |
| 其他 NFKC | 15 | `meaning_detail` | `読む` | `②` (U+2461 CIRCLED DIGIT TWO) | 15 | `2` |
| 其他 NFKC | 15 | `meaning_detail` | `読む` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 24 | `\|` |
| 其他 NFKC | 16 | `meaning_detail` | `使う` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 16 | `meaning_detail` | `使う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 10 | `\|` |
| 其他 NFKC | 16 | `meaning_detail` | `使う` | `②` (U+2461 CIRCLED DIGIT TWO) | 16 | `2` |
| 其他 NFKC | 16 | `meaning_detail` | `使う` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 25 | `\|` |
| 其他 NFKC | 17 | `meaning_detail` | `述べる` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 17 | `meaning_detail` | `述べる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 11 | `\|` |
| 其他 NFKC | 17 | `meaning_detail` | `述べる` | `②` (U+2461 CIRCLED DIGIT TWO) | 17 | `2` |
| 其他 NFKC | 17 | `meaning_detail` | `述べる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 27 | `\|` |
| 其他 NFKC | 18 | `meaning_detail` | `質問` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 18 | `meaning_detail` | `質問` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 18 | `meaning_detail` | `質問` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 18 | `meaning_detail` | `質問` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 27 | `\|` |
| 其他 NFKC | 19 | `meaning_detail` | `作る` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 19 | `meaning_detail` | `作る` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 10 | `\|` |
| 其他 NFKC | 19 | `meaning_detail` | `作る` | `②` (U+2461 CIRCLED DIGIT TWO) | 14 | `2` |
| 其他 NFKC | 19 | `meaning_detail` | `作る` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 23 | `\|` |
| 其他 NFKC | 20 | `meaning_detail` | `人間` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 20 | `meaning_detail` | `人間` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 10 | `\|` |
| 其他 NFKC | 20 | `meaning_detail` | `人間` | `②` (U+2461 CIRCLED DIGIT TWO) | 16 | `2` |
| 其他 NFKC | 20 | `meaning_detail` | `人間` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 23 | `\|` |
| 其他 NFKC | 21 | `meaning_detail` | `利用` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 21 | `meaning_detail` | `利用` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 21 | `meaning_detail` | `利用` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 21 | `meaning_detail` | `利用` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 31 | `\|` |
| 其他 NFKC | 22 | `meaning_detail` | `場合` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 22 | `meaning_detail` | `場合` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 16 | `\|` |
| 其他 NFKC | 22 | `meaning_detail` | `場合` | `②` (U+2461 CIRCLED DIGIT TWO) | 26 | `2` |
| 其他 NFKC | 22 | `meaning_detail` | `場合` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 40 | `\|` |
| 其他 NFKC | 23 | `meaning_detail` | `知る` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 23 | `meaning_detail` | `知る` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 16 | `\|` |
| 其他 NFKC | 23 | `meaning_detail` | `知る` | `②` (U+2461 CIRCLED DIGIT TWO) | 23 | `2` |
| 其他 NFKC | 23 | `meaning_detail` | `知る` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 36 | `\|` |
| 其他 NFKC | 24 | `meaning_detail` | `相手` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 24 | `meaning_detail` | `相手` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 24 | `meaning_detail` | `相手` | `②` (U+2461 CIRCLED DIGIT TWO) | 22 | `2` |
| 其他 NFKC | 24 | `meaning_detail` | `相手` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 36 | `\|` |
| 其他 NFKC | 25 | `meaning_detail` | `まず` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 25 | `meaning_detail` | `まず` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 25 | `meaning_detail` | `まず` | `②` (U+2461 CIRCLED DIGIT TWO) | 23 | `2` |
| 其他 NFKC | 25 | `meaning_detail` | `まず` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 37 | `\|` |
| 其他 NFKC | 26 | `meaning_detail` | `同じ` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 26 | `meaning_detail` | `同じ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 26 | `meaning_detail` | `同じ` | `②` (U+2461 CIRCLED DIGIT TWO) | 21 | `2` |
| 其他 NFKC | 26 | `meaning_detail` | `同じ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 36 | `\|` |
| 其他 NFKC | 27 | `meaning_detail` | `多い` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 27 | `meaning_detail` | `多い` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 27 | `meaning_detail` | `多い` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 27 | `meaning_detail` | `多い` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 30 | `\|` |
| 其他 NFKC | 28 | `meaning_detail` | `情報` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 28 | `meaning_detail` | `情報` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 28 | `meaning_detail` | `情報` | `②` (U+2461 CIRCLED DIGIT TWO) | 21 | `2` |
| 其他 NFKC | 28 | `meaning_detail` | `情報` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 32 | `\|` |
| 其他 NFKC | 29 | `meaning_detail` | `商品` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 29 | `meaning_detail` | `商品` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 14 | `\|` |
| 其他 NFKC | 29 | `meaning_detail` | `商品` | `②` (U+2461 CIRCLED DIGIT TWO) | 24 | `2` |
| 其他 NFKC | 29 | `meaning_detail` | `商品` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 40 | `\|` |
| 其他 NFKC | 30 | `meaning_detail` | `よく` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 30 | `meaning_detail` | `よく` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 11 | `\|` |
| 其他 NFKC | 30 | `meaning_detail` | `よく` | `②` (U+2461 CIRCLED DIGIT TWO) | 16 | `2` |
| 其他 NFKC | 30 | `meaning_detail` | `よく` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 30 | `\|` |
| 其他 NFKC | 31 | `meaning_detail` | `選ぶ` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 31 | `meaning_detail` | `選ぶ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 31 | `meaning_detail` | `選ぶ` | `②` (U+2461 CIRCLED DIGIT TWO) | 20 | `2` |
| 其他 NFKC | 31 | `meaning_detail` | `選ぶ` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 31 | `\|` |
| 其他 NFKC | 32 | `meaning_detail` | `感ずる` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 32 | `meaning_detail` | `感ずる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 15 | `\|` |
| 其他 NFKC | 32 | `meaning_detail` | `感ずる` | `②` (U+2461 CIRCLED DIGIT TWO) | 24 | `2` |
| 其他 NFKC | 32 | `meaning_detail` | `感ずる` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 34 | `\|` |
| 其他 NFKC | 33 | `meaning_detail` | `理解` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 33 | `meaning_detail` | `理解` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 14 | `\|` |
| 其他 NFKC | 34 | `meaning_detail` | `大切` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 34 | `meaning_detail` | `大切` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 9 | `\|` |
| 其他 NFKC | 34 | `meaning_detail` | `大切` | `②` (U+2461 CIRCLED DIGIT TWO) | 15 | `2` |
| 其他 NFKC | 34 | `meaning_detail` | `大切` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 25 | `\|` |
| 其他 NFKC | 35 | `meaning_detail` | `力` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 35 | `meaning_detail` | `力` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 10 | `\|` |
| 其他 NFKC | 35 | `meaning_detail` | `力` | `②` (U+2461 CIRCLED DIGIT TWO) | 16 | `2` |
| 其他 NFKC | 35 | `meaning_detail` | `力` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 26 | `\|` |
| 其他 NFKC | 36 | `meaning_detail` | `生活` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 36 | `meaning_detail` | `生活` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 13 | `\|` |
| 其他 NFKC | 36 | `meaning_detail` | `生活` | `②` (U+2461 CIRCLED DIGIT TWO) | 20 | `2` |
| 其他 NFKC | 36 | `meaning_detail` | `生活` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 30 | `\|` |
| 其他 NFKC | 37 | `meaning_detail` | `社会` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 37 | `meaning_detail` | `社会` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 37 | `meaning_detail` | `社会` | `②` (U+2461 CIRCLED DIGIT TWO) | 19 | `2` |
| 其他 NFKC | 37 | `meaning_detail` | `社会` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 29 | `\|` |
| 其他 NFKC | 38 | `meaning_detail` | `生` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 38 | `meaning_detail` | `生` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 38 | `meaning_detail` | `生` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 38 | `meaning_detail` | `生` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 27 | `\|` |
| 其他 NFKC | 39 | `examples` | `文章` | `①` (U+2460 CIRCLED DIGIT ONE) | 18 | `1` |
| 其他 NFKC | 39 | `meaning_detail` | `文章` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 39 | `meaning_detail` | `文章` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 10 | `\|` |
| 其他 NFKC | 39 | `meaning_detail` | `文章` | `②` (U+2461 CIRCLED DIGIT TWO) | 15 | `2` |
| 其他 NFKC | 39 | `meaning_detail` | `文章` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 26 | `\|` |
| 其他 NFKC | 40 | `meaning_detail` | `内容` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 40 | `meaning_detail` | `内容` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 11 | `\|` |
| 其他 NFKC | 40 | `meaning_detail` | `内容` | `②` (U+2461 CIRCLED DIGIT TWO) | 17 | `2` |
| 其他 NFKC | 40 | `meaning_detail` | `内容` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 28 | `\|` |
| 其他 NFKC | 41 | `meaning_detail` | `気持ち` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |
| 其他 NFKC | 41 | `meaning_detail` | `気持ち` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 12 | `\|` |
| 其他 NFKC | 41 | `meaning_detail` | `気持ち` | `②` (U+2461 CIRCLED DIGIT TWO) | 18 | `2` |
| 其他 NFKC | 41 | `meaning_detail` | `気持ち` | `｜` (U+FF5C FULLWIDTH VERTICAL LINE) | 29 | `\|` |
| 其他 NFKC | 42 | `meaning_detail` | `生きる` | `①` (U+2460 CIRCLED DIGIT ONE) | 1 | `1` |

> 仅显示前 200 条 Unicode 其他疑点；总数 25453。

## 未修改的格式清洗建议

### word 包含 `（する）` / `（と）` / `（も）` / `（て）`：10 条

| 行号 | word | reading | meaning |
|---:|---|---|---|
| 5111 | `浮気（する）` | `うわき（する）` | 见异思迁；花心 |
| 5255 | `考慮（する）` | `こうりょ（する）` | 考虑 |
| 5395 | `手当（て）` | `てあて（て）` | 津贴 |
| 5486 | `返品（する）` | `へんぴん（する）` | 退货 |
| 5495 | `訪問（する）` | `ほうもん（する）` | 访问 |
| 5508 | `万引き（する）` | `まんびき（する）` | 扒窃 |
| 5536 | `優勝（する）` | `ゆうしょう（する）` | 冠军 |
| 5847 | `あくまで（も）` | `あくまで（も）` | 彻底；始终 |
| 5861 | `きっぱり（と）` | `きっぱり（と）` | 断然，干脆 |
| 5862 | `ぐずぐず（と）` | `ぐずぐず（と）` | 慢腾腾；嘟囔 |

### word 包含 `～`：17 条

| 行号 | word | reading | meaning |
|---:|---|---|---|
| 5360 | `～対` | `～たい` | 对，比 |
| 5844 | `我が～` | `わがから` | 我们 |
| 5921 | `現～` | `げん～` | 现在的 |
| 5922 | `諸～` | `しょ～` | 诸~ |
| 5923 | `低～` | `てい～` | 低~ |
| 5924 | `同～` | `どう～` | 同~ |
| 5925 | `初～` | `はつから` | 最初，首次~ |
| 5926 | `無～` | `む～` | 无~ |
| 5927 | `和～` | `わ～` | 日式 |
| 5928 | `～感` | `～かん` | ~感 |
| 5929 | `～号` | `～ごう` | ~号 |
| 5930 | `～だらけ` | `～だらけ` | 满是~ |
| 5931 | `～足らず` | `～たるず` | 不足，少于~ |
| 5932 | `～付き` | `～つき` | 附带~ |
| 5933 | `～風` | `～かぜ` | ~风格 |
| 5934 | `～向け` | `～むけ` | 向，对~ |
| 5935 | `～率` | `～りつ` | ~率 |

### word 包含 `／`：1 条

| 行号 | word | reading | meaning |
|---:|---|---|---|
| 5665 | `捉える／捕らえる` | `とらえる／とらえる` | 捕捉 |

### word 包含英文中点 `·`：1 条

| 行号 | word | reading | meaning |
|---:|---|---|---|
| 5480 | `故郷·古里` | `こきょう·ふるさと` | 故乡 |

## 明确不判定为错误

- `々` 是合法重复符号，本次不判定为错误；原文件 word 列发现 25 条。
- 示例：様々、人々、日々、我々、次々、時々、木々、堂々、徐々、方々、薄々、嫌々、少々、着々、数々、軽々、隅々、白々しい、騒々しい、様々な

## 校验

- 原 CSV 数据行：5975
- 清洗 CSV 数据行：5975
- 已确认只存在 4 个字段级差异，且均为本次指定修复项。
