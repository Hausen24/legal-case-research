# 类案检索研究工作流（Legal Case-Research Workflow）

[![CI](https://github.com/Hausen24/legal-case-research/actions/workflows/ci.yml/badge.svg)](https://github.com/Hausen24/legal-case-research/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)

> **A reproducible legal case-research workflow** that turns a fact pattern + search brief into a citation-checked, chart-rich Word report and an Excel case list — with sample-size-adaptive statistics and machine-verified anti-hallucination. Works with the Peking University Law (北大法宝) MCP **or your own case data**, and with **any** capable AI agent (not only Claude). See [AGENTS.md](AGENTS.md).

把一段案情 + 检索要求，自动跑成「**类案检索研究报告（Word）+ 案件清单（Excel）**」。数据源默认北大法宝 MCP，**也支持自带数据**（无订阅亦可，见 [AGENTS.md](AGENTS.md) 与 [输入数据契约](examples/输入数据契约.md)）。

本项目内置**两套工作流**，区别不在"行业"，而在**案件的离散程度**：

| 技能 | 适用场景 | 去重逻辑 | 分析口径 |
|------|------|----------|----------|
| **`case-research`**<br>标准类案检索 | 一段案情 → 找相似类案 → 分析 | 按 `Gid` 去重 | 动态争点体系 + 样本自适应六维统计 + 居中/攻方/辩方三场景 |
| **`group-litigation-research`**<br>集团/群体性诉讼 | **一个共同事件派生大量平行、近似判决**（众多当事人就同一被告主体的同一事件分别起诉） | **不靠 Gid，按"主体+事件"分组**，组内只留核心实质判决，平行判决仅留痕 | 沿构成要件/问题体系逐问题深度梳理 + 典型案例交叉核对（内置**证券虚假陈述**为示范样例） |

标准类案检索技能内置**两种研究模式**（开工时选择）：

| 模式 | 检索范围 | 报告特色 |
|---|---|---|
| **学理研究**（默认） | 全国，不限法院 | 地域分布图 + 争点×地域观点热力矩阵（描述性呈现，是否构成地域倾向结论由样本量闸门裁定） |
| **实案研究** | 用户指定**核心法院**，按最高法《类案检索指导意见》（法发〔2020〕24号）**第四条四顺位**检索：指导性案例→最高法→本省高院→上一级及本院 | 「类案规则」专章逐顺位深度比对（三要素相似性+裁判逻辑拆解）、指导性案例标注"应当参照"效力（第九条）、附录满足**第八条**检索报告要素、**可随案归档** |

实案模式顺位①由内置的**最高法指导性案例本地数据集**（[data/guiding_cases/](data/guiding_cases/)，官网合规抓取 263 案全文，`fetch_guiding_cases.py` 定期增量更新）提供裁判要点/基本案情/裁判理由全文；直辖市多中院映射（如朝阳区→北京三中院）由 `court_hierarchy` 解析并在检查点 1 由用户确认。

两套共用 `.mcp.json`、`CLAUDE.md`，以及渲染层 `scripts/build_report_docx.py`、图表主题 `scripts/chart_theme.py`、样本自适应闸门 `scripts/common/stats_guard.py`、公共派生 `scripts/common/pkulaw_utils.py`、反幻觉校验 `scripts/verify_report.py`。

---

## 看一眼产出（Demo，无需法宝 Token）

北大法宝是订阅制，但你**不需要 Token 也能跑通整条管道、看到真实产出形态**——仓库自带[脱敏演示样本](examples/)（案号、当事人、裁判内容均为虚构，见 [DISCLAIMER](examples/DISCLAIMER.md)）。

**示例 · 集团诉讼（证券虚假陈述）** —— `group-litigation-research` 工作流：

```bash
pip install -r requirements.txt && npm install
python3 examples/build_demo_secmisrep.py                                          # 合成演示数据
python3 scripts/securities/normalize_secmisrep.py    "examples/demo_证券虚假陈述集团诉讼"
python3 scripts/securities/run_analytics_secmisrep.py "examples/demo_证券虚假陈述集团诉讼"   # 统计+出图
python3 scripts/securities/generate_excel_secmisrep.py "examples/demo_证券虚假陈述集团诉讼" --name "证券虚假陈述案件" --date 20260609
python3 scripts/build_report_docx.py "examples/demo_证券虚假陈述集团诉讼" "证券虚假陈述案件-类案检索报告-20260609.md"
python3 scripts/verify_report.py "examples/demo_证券虚假陈述集团诉讼"                # 反幻觉校验
```

产出（点开即看）：[📝 报告 Word](examples/demo_证券虚假陈述集团诉讼/output/证券虚假陈述案件-类案检索报告-20260609.docx) · [📄 报告 Markdown](examples/demo_证券虚假陈述集团诉讼/output/证券虚假陈述案件-类案检索报告-20260609.md) · [📊 核心判决清单 Excel](examples/demo_证券虚假陈述集团诉讼/output/证券虚假陈述案件-类案检索清单-20260609.xlsx)

统一主题、样本量自适应的图表（由 `chart_theme` + 分析脚本自动生成）：

| 样本概览 | 争点频次 | 裁判结果年度演进 |
|---|---|---|
| ![样本概览](examples/demo_证券虚假陈述集团诉讼/output/_charts/overview.png) | ![争点频次](examples/demo_证券虚假陈述集团诉讼/output/_charts/issue_freq.png) | ![年度演进](examples/demo_证券虚假陈述集团诉讼/output/_charts/result_year.png) |

> 本样本核心判决 7 件、上海 5/北京 2 → 工作流自动判定为「定性深挖档 / 仅描述性统计 / **不作地域分歧推断**」，
> 报告措辞相应收敛为"示裁判取向、不作占比定论"——这正是 `stats_guard` 闸门的作用（防止"京沪 2 件就编出地域差异"）。

> **关于深度（重要）**：此 demo 是**格式与可复现性样本**，用于证明整条管道（结构 / 脚注 / 图表 / 命名 / 样本量闸门 / 反幻觉校验）无需 Token 即可端到端跑通。它的**分析深度受限于合成演示数据**——demo 没有判决全文。**真实运行时**，工作流会先用 `download_fulltext` 抓取每份判决的完整文书，据此把每个争点重构成 500–1500 字的实证说理（请求权基础→各方抗辩→法院说理与取舍→结论），产出篇幅与深度通常是本 demo 的**数倍**。换言之：demo 展示的是"机器能不能跑通、排版长什么样"，不是"分析能写多深"。

> 另有 **标准类案检索** 示例（短视频侵权，`case-research` 工作流）见 [`examples/demo_算法推荐短视频侵权/`](examples/demo_算法推荐短视频侵权/output/)。

---

## 没有北大法宝？没有 Claude？

- **没有法宝订阅** → **自带数据模式**：把你的判决数据整理成扁平 CSV/JSON（[字段契约](examples/输入数据契约.md)），用 `python3 scripts/general/import_cases.py <dir> --json/--csv <file>` 转成管道输入，分析与产出链路完全相同。
- **不用 Claude** → 本项目的技能是**自包含的 SOP**、脚本是**纯 Python/Node**。任何能读仓库文件、跑命令、（可选）调 MCP 的 AI 智能体都能驱动它（Cline / Cursor / Windsurf / Continue / Aider / Codex CLI / Gemini CLI 等）。详见 [AGENTS.md](AGENTS.md)。

---

## 目录结构

```
legal-case-research/
├── .mcp.json.example         ← MCP 配置模板（复制为 .mcp.json 填 Token；.mcp.json 已 gitignore）
├── CLAUDE.example.md         ← 个人实践画像模板（复制为 CLAUDE.md 填偏好；CLAUDE.md 已 gitignore）
├── AGENTS.md                 ← 工具无关运行指南（任何 AI 智能体怎么跑）
├── skills/
│   ├── case-research/                ← 标准类案检索技能
│   └── group-litigation-research/    ← 集团/群体性诉讼技能（内置证券虚假陈述示范样例）
├── scripts/
│   ├── common/                       ← pkulaw_utils（公共派生）· stats_guard（样本自适应闸门）
│   ├── build_report_docx.py + render_report.mjs   ← 报告转 Word（两技能共用）
│   ├── chart_theme.py                ← 统一图表主题（两技能共用）
│   ├── verify_report.py              ← 反幻觉收尾自检（两技能共用）
│   ├── general/                      ← normalize_cases · run_analytics · generate_excel · import_cases(自带数据)
│   └── securities/                   ← 集团诉讼·证券示例：normalize/run_analytics/generate_excel_secmisrep
├── examples/                 ← 脱敏 demo（无需 Token 可跑）+ 输入数据契约
├── tests/                    ← pytest（CI 运行）
└── research/                 ← 每次研究一个子目录（含当事人信息，默认 gitignore）
```

## 首次使用

1. **填 MCP 配置**（用法宝时）：`cp .mcp.json.example .mcp.json`，把 `你的Token` 换成真实 Token。不用法宝可跳过（走自带数据模式）。
2. **填个人画像**：`cp CLAUDE.example.md CLAUDE.md`，把【】处改成你的偏好（角色、文风、署名等）。`CLAUDE.md` 已 gitignore，不入库。
3. **装依赖**：`pip install -r requirements.txt && npm install`
4. **启动**：在本目录开 Claude Code（或其它 AI 智能体，见 [AGENTS.md](AGENTS.md)）；用法宝时 `/mcp` 确认服务 Connected，建议 `/model` 切 Opus 4.8 做分析。

> ⚠️ 「检索法律法规」服务为**可选**，仅证券示例的法条原文核对会用到；不订阅也能跑通主流程。

## 跑一次研究

### A. 标准类案检索（`case-research`）
> 做一次类案研究。案情：短视频平台通过算法推荐机制推送用户上传的未授权影视剪辑，权利人通知后平台未采取有效措施。检索要求：北京、上海、广州三地法院；二审或再审优先；2021 年至今；目标 50 件普通案例。

抽要素、搭争点体系、构关键词 →（**检查点 1**）→ 多轮检索/去重/筛查 →（**检查点 2**）→ 编码、六维统计出图、抓全文、选场景 → 研报级报告 + Excel。

### B. 集团/群体性诉讼（`group-litigation-research`，内置证券示例）
> 做一次证券虚假陈述类案裁判规则研究，请加载 group-litigation-research 技能。系统检索"证券虚假陈述责任纠纷"案由下京沪金融法院及对应高院的核心判决，按构成要件问题体系逐问题梳理，平行判决仅留痕。

搭问题体系、定轮替策略 →（**检查点 1**）→ 轮替检索、按"主体+事件"分组识别核心判决 →（**检查点 2**）→ 按问题编码、交叉核对典型案例 → 投研级报告 + 长表核心判决清单 Excel。

## 产出

```
research/<主题>_<日期>/output/
├── _charts/                              统一主题图表 + manifest.json（报告占位符插图）
├── <案件类别>-类案检索报告-<YYYYMMDD>.md / .docx
├── <案件类别>-类案检索清单-<YYYYMMDD>.xlsx
└── 原文/                                 分析案件判决原文，每案一份 + 00_索引.md（报告深度来源）
```

> 报告/清单命名固定为 `<案件类别>-类案检索报告/清单-<YYYYMMDD>`（如 `证券虚假陈述案件-类案检索报告-20260609`）。
> 原文导出：`python3 scripts/download_fulltext.py <research_dir> [--docx]`，作为报告深度写作的全文来源。

## 关键设计

- **只有普通案例（CaseGrade=07）有完整判决书要素**，进分析管道；经典/评析/指导案例进附录索引。
- **关键词铁律**：案由词放 title，方法论词放 fulltext（否则命中评析文章而非判决书）。
- **样本量自适应**（`stats_guard`）：小样本只做描述性、逐争点深挖；分组样本不足时不作分组差异推断。
- **反幻觉**：所有案件来自数据源，引用必带案号+法院+链接，不凭记忆编造。

## 可靠性与可复现

- **反幻觉是被机器证明的。** `scripts/verify_report.py` 扫描最终报告每个案号，逐一比对样本池，引用了样本池外的案号即报错、非零退出——把"承诺不编案号"升级为"机器证明每个引用都可溯源"。收尾自检与 CI 都跑它。
- **检索覆盖率是被量化的。** `scripts/check_coverage.py` 输出关键词命中矩阵（含边际贡献）、去重审计与典型案例名录缺口表——把"完整性不可保证"变成可呈报的量化缺口，亦可作为符合最高法类案检索指导意见（法发〔2020〕24号）第八条"方法/结果"要素的检索过程底稿。
- **数据契约是被校验的。** `scripts/validate_pipeline.py` 对管道各阶段做字段类型/枚举/争点名拼写一致性校验，AI 编码的漏填错键当场报错，而不是等成品出现空列。
- **裁判分歧是一等产出。** 同一争点对立立场并存的争点清单、各立场代表案对与地域观察，自动进入分析数据与 Excel「裁判分歧清单」；是否构成地域倾向结论仍由样本量闸门裁定。
- **自动化测试 + CI。** `tests/` 下 pytest 覆盖公共派生、样本量闸门（含"小样本不作分歧推断"回归保护）、Excel 实质列非空、自带数据导入、反幻觉校验正反用例；GitHub Actions 每次推送/PR 跑全套测试 + 演示管道冒烟 + 反幻觉校验（见徽章）。
  ```bash
  pip install -r requirements.txt pytest && python3 -m pytest
  ```

## 调整工作流

- 改报告风格/格式 → 改 `CLAUDE.md`（从 `CLAUDE.example.md` 复制）
- 改标准检索争点体系 → `skills/case-research/methodology/issue-framework.md`
- 改样本自适应阈值 → `scripts/common/stats_guard.py`；改图表样式 → `scripts/chart_theme.py`（两套同时生效）
- 改集团诉讼问题体系 → `skills/group-litigation-research/methodology/issue-framework.md`（问题键名须与脚本 `ISSUES` 一致）
- 换一类集团诉讼（产品责任/消费者集体维权/环境侵权等）→ 保持机制不变，替换问题体系、事件识别口径、典型案例名录三处
- 改公共派生（法院层级/链接清洗等）→ `scripts/common/pkulaw_utils.py`（两套同时生效）

更新历史见 [CHANGELOG.md](CHANGELOG.md)。
