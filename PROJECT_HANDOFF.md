# PROJECT_HANDOFF.md
# JLPT N2 背单词系统 — 项目交接文档
> 最后更新：2026-05-14（本次会话结束时）

---

## 1. 当前项目目标

基于 2010–2025 JLPT N2 真题词频数据，构建一套背单词 Web 应用。
核心功能：间隔复习（SRS）、磨耳朵、AI 联想故事记忆。
当前阶段：**数据清洗已完成**，下一步是联想故事（memory_hint）批量生成。

---

## 2. 已实现的功能（后端/前端）

- FastAPI 后端：词卡 API、复习提交、进度统计
- 前端：单页应用，词卡翻转、四档评分（again/hard/good/known）
- 间隔复习调度（scheduler.py，简化 SRS）
- 磨耳朵模块（listening.py）
- TTS 语音合成（tts_provider.py，带本地缓存）
- 进度持久化（progress/default.json）

---

## 3. 数据操作历史（按时间顺序）

### 2026-05-13 会话
- **任务一**：补充 collocation 字段（`tools/task1_collocation.py`，14词）
- **任务二**：清洗 examples 字段（`tools/task2_examples.py`，3537行）
- **任务三**：新增 quadrant 字段（`tools/task3_quadrant.py`）
- **导出联想故事待处理词表**：`data/memory_hints_todo.csv`（601词，count≥20 的黄金词/隐藏考点）
- **数据源差异审计**：`tools/audit_source.py`、`tools/audit_detail.py`

### 2026-05-13 深夜 ~ 2026-05-14 凌晨（前一会话续）
- **gen_missing_candidates_v3**：从 PDF 源文件挑选 442 个漏导入的高质量词，分类为 `import_candidate_high`/`count≥10_not_in_vocab`
- **staged import**：442 词追加进 n2_vocab.csv（quadrant 临时标记为 `pending_meaning`）
- **enrich_meaning.py**：GPT 填充这 442 词的 meaning 字段
- **fix_reading_conjugated.py**：修正若干活用形 reading 问题
- **enrich_fields.py**：GPT 批量填充全部词表的 meaning_detail / collocation / examples（所有字段达到 100% 覆盖）

### 2026-05-14 本次会话
- **修复 pending_meaning quadrant**：重跑 `tools/task3_quadrant.py`，442 词从 `pending_meaning` 正确分配到四象限
- **修正 走れる reading**：`はしる` → `はしれる`（数据质量问题）
- **导入 16 个高频缺失词**：脚本 `tools/import_missing_final.py`
  - 完全缺失：家、学校、始める、そして、上げる、どこ、彼女、コンピューター
  - 词表仅有异形/词干：早い、店、少ない、あまり、走る、忘れる、止める、地
  - GPT 已补全 meaning_detail / collocation / examples

---

## 4. 当前词表状态（2026-05-14）

| 项目 | 数值 |
|------|------|
| 总词数 | **6464 条** |
| 所有字段填充率 | **100%** |
| 黄金词（count≥10，is_n2_core=是） | 148 |
| 隐藏考点（count≥10，is_n2_core=否） | 1336 |
| 社区推荐（count<10，is_n2_core=是） | 1337 |
| 边缘词（count<10，is_n2_core=否） | 3643 |

count≥10 的源文件缺失词已清零（剩余 44 个均为感動詞语气词或固有名词，属有意排除噪音）。

---

## 5. 关键文件路径

```
E:\codex\jlpt背单词\
├── backend/
│   ├── app.py              # 主 API 路由
│   ├── scheduler.py        # SRS 调度算法
│   ├── vocab_store.py      # 词库加载
│   ├── progress_store.py   # 进度读写
│   ├── audio.py            # 音频 API
│   ├── listening.py        # 磨耳朵 API
│   └── tts_provider.py     # TTS 合成
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── n2_vocab.csv                  # 主词表（6464条，全字段100%覆盖）
│   ├── memory_hints_todo.csv         # 联想故事待处理（601条，count≥20高频词）
│   └── _import_missing_final_report.json  # 本次导入报告
├── tools/
│   ├── task1_collocation.py          # 补充搭配
│   ├── task2_examples.py             # 清洗例句
│   ├── task3_quadrant.py             # 四象限分类（幂等，可重复运行）
│   ├── export_memory_hints_todo.py   # 导出联想故事待处理词表
│   ├── import_missing_final.py       # 本次：修正+补充缺失词（已运行）
│   ├── enrich_fields.py              # GPT 批量填充字段（已运行）
│   ├── import_jlpt_words.py          # 原始导入脚本（[:100] bug 未删，不再需要）
│   └── gen_missing_candidates_v3.py  # 从源文件生成候选导入列表
├── progress/
│   └── default.json        # 用户学习进度
└── PROJECT_HANDOFF.md      # 本文件

PDF 解析源文件：
E:\codex\PDF解析\output\content_lemma_import_cards.csv   # 7088条原始词（已完成利用）
```

---

## 6. 启动命令

```powershell
# 启动后端（在 backend/ 目录下）
cd E:\codex\jlpt背单词\backend
uvicorn app:app --reload --port 8000

# 访问前端
http://localhost:8000
```

> **PowerShell 测试 TTS 注意**：`Invoke-WebRequest -Body '日文字符串'` 会用系统 ANSI 编码发送请求，导致日文变成 `??`。
> 必须用字节方式：`[System.Text.Encoding]::UTF8.GetBytes('{"word":"言う"}')` 作为 Body。
> 前端 JS 的 fetch 自动 UTF-8，实际用户不受影响。

---

## 7. 当前已知问题

### 问题一：import_jlpt_words.py 的 [:100] bug（已过时，不影响现状）
- 文件：`tools/import_jlpt_words.py` 第 200 行仍有 `source_rows[:100]`
- **现状**：缺失词已通过 gen_missing_candidates_v3 + import_missing_final 补入，该 bug 不再影响词表质量
- **处置建议**：保留脚本不动，或删除 `[:100]` 做存档修复，低优先级

### 问题二：联想故事（memory_hint）尚未生成（最高优先级）
- `data/memory_hints_todo.csv` 已导出（601词，count≥20 的黄金词/隐藏考点）
- 已测试前 50 词：模型强行拼凑谐音效果差
- **最佳策略**：整词映射优先（相手→艾特、よく→优酷、利用→理由），无法整词映射则改用场景联想法，放弃谐音
- **提示词未定稿**，批量写入 n2_vocab.csv 的 memory_hint 字段（该字段尚不存在，需新增）

---

## 8. 下一步任务（唯一优先级）

### 联想故事批量生成

1. 优化 system prompt：
   - 第一步：判断词是否能整词映射中文已有词/品牌/成语（如 利用→理由、相手→艾特）
   - 第二步：无法整词映射则用"场景联想"（具体画面、动作、情境），不强求谐音
   - 禁止：强行分拆字音拼凑、无意义谐音
   - 输出：不超过 20 字的一句中文联想

2. 测试集：先跑 `memory_hints_todo.csv` 前 20 词，人工验收质量

3. 批量生成：全部 601 词，每批 30 词调用 gpt-4o-mini

4. 写回词表：在 n2_vocab.csv 新增 `memory_hint` 字段，写入结果

---

## 9. 数据字段说明（n2_vocab.csv）

| 字段 | 说明 |
|------|------|
| word | 日文词 |
| reading | 假名读音 |
| pos | 词性（日文标准：動詞、名詞、形容詞、副詞 等） |
| meaning | 核心中文意思（1-4字，短） |
| collocation | 常见搭配（2-3个，/ 分隔） |
| count | 在真题中出现次数（0=来自N2核心词表，无频次数据） |
| source | 数据来源（真题 / jlpt_exam_frequency 等） |
| is_n2_core | 是/否（是否 N2 官方核心词表收录） |
| examples | 例句（1-2 句，/ 分隔） |
| meaning_detail | 详细释义（带例句，①②格式） |
| quadrant | 四象限：黄金词/隐藏考点/社区推荐/边缘词 |
| memory_hint | 联想记忆故事（**尚未生成**，字段也尚未存在） |
