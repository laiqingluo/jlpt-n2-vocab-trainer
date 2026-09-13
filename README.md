# JLPT N2 背单词系统

基于 2010–2025 JLPT N2 真题词频数据构建的背单词 Web 应用。核心是"五步沉浸式"单词学习流程（听音 → 眼耳同步 → AI 联想故事记忆 → 跟读 → 例句），配合间隔重复复习（SRS）、磨耳朵听力和能力测验。

## 功能

- **五步单词学习流程**：TTS 听音、词形+读音+释义同步呈现、AI 生成的中文联想记忆故事、跟读练习、真实例句
- **间隔复习（SRS）**：四档评分（again/hard/good/known），按记忆曲线安排复习
- **磨耳朵**：弱词优先，日语音频 → 中文提示循环
- **能力测验 / 快速筛词**：批量标记已掌握的词，跳过已知内容
- **账号系统**：注册/登录，也支持访客模式（数据不落账号）
- **6464 个 N2 词条**，所有字段（读音、释义、搭配、例句、四象限分类、联想故事）100% 覆盖

## 技术栈

- 后端：FastAPI + SQLite
- 前端：原生 JS 单页应用
- TTS：Azure Cognitive Services Speech
- 联想故事 / 释义补全：OpenAI GPT

## 快速开始

```powershell
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 配置密钥（TTS 需要 Azure；批量生成联想故事/释义需要 OpenAI）
Copy-Item .env.example .env
# 编辑 .env 填入你自己的 AZURE_SPEECH_KEY / OPENAI_API_KEY

# 3. 用种子数据初始化数据库（首次运行）
cd ..
Copy-Item data/n2_seed.db data/n2.db

# 4. 启动
./start_server.ps1
```

访问 `http://localhost:8000`，可以直接选择"以访客身份继续"体验，无需配置密钥即可看到词卡界面（TTS 发音功能需要 Azure 密钥）。

## 目录结构

```
backend/        FastAPI 服务（词卡 API、SRS 调度、TTS、听力、鉴权）
frontend/       单页应用前端
data/           词表数据（n2_seed.db 种子库、n2_vocab.csv 源表）
tools/          数据清洗 / 导入 / 词表构建脚本
reports/        数据清洗过程报告
```

## 数据来源与处理

词表基于 2010–2025 年 JLPT N2 真题词频统计，经过多轮清洗、四象限分类（黄金词/隐藏考点/社区推荐/边缘词）、字段补全（GPT 批量生成释义、搭配、例句、联想记忆故事）。详细过程见 `reports/n2_vocab_cleaning_report.md` 和 `PROJECT_HANDOFF.md`。

`data/n2_seed.db` 是不含任何真实用户账号/登录态的干净种子数据库，可放心用于本地开发；`tools/migrate_to_sqlite.py` 可从 `data/n2_vocab.csv` 重新同步词表到数据库。
