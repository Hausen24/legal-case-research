---
name: case-research
description: 类案检索与分析工作流。当用户提供一段案情 + 检索要求（案件数量/地域/法院级别等），需要在北大法宝判例库中检索类案、筛查、编码、并产出"类案分析报告 + Excel 清单"时使用本技能。覆盖检索前要素抽取、本主题动态争点体系搭建、关键词分层、多轮迭代检索、普通案例/经典案例双轨处理、相关度筛查、字段加工编码、样本量自适应的六维数据分析与统一主题出图、全文驱动的深度报告写作、以及居中/攻方/辩方三场景报告生成。
---

# 类案研究工作流（北大法宝 MCP）

本技能把一次完整的类案研究拆成三步、两个人工确认点。**严格按顺序执行，不要跳步，不要在未获用户确认前进入检索或下载。**

## 全局铁律（贯穿全程，违反即返工）

- **反幻觉**：禁止凭记忆生成案号、案件、裁判内容；一切来自 MCP。引用案号必带 `CaseFlag`＋审理法院＋链接（链接入脚注）。`search_case` 仅作发现，正式数据以 `get_case_list` 全要素为准。
- **禁止泄露内部产物名与工序词**：成品报告/Excel 中不得出现 `06_analytics.json`、`05_enriched_cases`、`sheet`、`脚本`、`编码列`、`留痕`、`维度一/维度二…`、`焦点立场`、`自动标注`、`depth_mode` 等任何工序词；数据出处统一写"数据来源：本报告样本（N=…）"。报告写**结论体**而非**工序体**。
- **深度由全文驱动**：报告的实质说理须基于裁判文书全文（`scripts/download_fulltext.py` 抓取）重构；缺全文处以〔全文补实：…〕显式占位，不得凭摘要一笔带过、亦不得编造。
- **样本量自适应**：定量强度与定性深度均随样本量自适应——`run_analytics.py` 经 `scripts/common/stats_guard.py` 写入 `深度档`/`定量档`/`地域分歧` 判定；小样本只做描述性、逐争点深挖，大样本由量化承载全景。分组分歧（地域/审级）由 `divergence_gate` 裁定，`report=False` 时不得单设分组分歧小节。

## 前置依赖

**MCP 服务**（须已在 `.mcp.json` 配置并连接）：
- `mcp__pkulaw-case-keyword__get_case_list` — 关键词检索，参数 `title` / `fulltext`（至少填一个），单次返回最多 10 条、每条 25+ 字段。**这是数据骨干。**
- `mcp__pkulaw-case-semantic__search_case` — 语义检索，参数 `text`（自然语言案情）。返回轻量摘要，用于探索和兜底。
- `mcp__pkulaw-case-number__anhao_recognition` — 案号识别验真，参数 `text`。用于反幻觉。

**脚本**（用 `python3` 运行；公共派生函数在 `scripts/common/pkulaw_utils.py`）：
- `scripts/general/normalize_cases.py` — 拍平 MCP 嵌套字段，派生法院层级/地域/年份。
- `scripts/general/run_analytics.py` — 计算六维统计**并接 `stats_guard` 写入样本自适应判定、用 `chart_theme` 出图 + manifest**。
- `scripts/general/generate_excel.py` — 生成 Excel 清单。
- `scripts/download_fulltext.py` — 抓分析池判决全文（**报告深度来源**，与证券专题共用）。
- `scripts/build_report_docx.py` — 报告转 Word（脚注/图表/封面，与证券专题共用）。
- `scripts/verify_report.py` — **反幻觉收尾自检**：扫描成品报告全部案号，逐一比对 `03_raw_cases.json` 样本池，引用了样本池外的案号即报错（与证券专题共用）。
- `scripts/common/stats_guard.py` / `scripts/chart_theme.py` — **共用**：样本量自适应闸门 / 统一图表主题。

**方法论**：`methodology/issue-framework.md`（为本主题动态搭建争点体系）、`methodology/keyword-strategy.md`（三层关键词）、`methodology/relevance-screening.md`（相关度筛查）、`methodology/analysis-dimensions.md`（六维 + 样本自适应）。**模板**：`templates/report-{neutral,plaintiff,defendant}.md`、`templates/excel-schema.md`。

**实践画像**：每次开工前先读 `CLAUDE.md`，应用其中的报告文风、格式、署名等偏好。

## 关键事实（务必牢记）

1. **只有 `CaseGrade` 含 "07"（普通案例）的条目，`Ascertain`/`Identified`/`RefereeBasis`/`RefereeResult` 才有完整正文。** 经典案例（05）、评析案例等只返回 metadata，正文字段为空。
2. 因此采用**双轨制**：普通案例进分析管道；经典/评析案例进"权威案例附录"（仅记录案号+标题+URL）。
3. **关键词策略铁律**：案由/法律关系词放 `title`，方法论/技术性词放 `fulltext`。判决书标题极少含"算法推荐"这类方法论词，硬塞进 title 会命中评析类文章而非判决书。详见 `methodology/keyword-strategy.md`。
4. 单次检索上限 10 条 → 必须多轮迭代累加，靠不同关键词组合扩大样本。

---

## 第一步：检索前准备

### 1.1 接收输入
用户会给：① 一段案情描述；② 检索要求（目标案件数量、地域范围、法院级别、时间范围、文书类型等，可能不全）。把这些原样记入 `research/<主题>_<日期>/00_input.md`。

### 1.2 案情要素抽取
从案情中抽出结构化要素，写入 `01_elements.md`：
- 主体（原告/被告身份及法律地位）
- 行为特征
- 关键情节
- 权利类型 / 法律关系
- 可能的争议焦点（预判，1-3 个）
- 可能的抗辩理由
- 标准化案由（用北大法宝的案由表述，如"侵害作品信息网络传播权纠纷"）

### 1.3 本主题争点体系搭建
按 `methodology/issue-framework.md` 的套路，据案情要素与预研，为**本主题**构造一套争点体系，写入 `01b_issues.md`：3–6 个**争议焦点**（每个给出"争什么/为何重要/两端立场"）、每个焦点的**倾向标签取值集**（离散互斥可穷举）、以及反复出现的**抗辩理由清单**。焦点名/标签/抗辩名一经定稿，全流程（编码 `焦点立场`/`抗辩`、脚本聚合、报告第二章）**逐字沿用**。这是通用技能的脊柱——证券专题用固定五维 14 问，通用主题须在此动态搭建。

### 1.4 三层关键词构建
按 `methodology/keyword-strategy.md` 的方法，构建三层检索表达，写入 `02_keywords.md`。每层给出 `title` 和 `fulltext` 的具体取值，并标注预期收窄/放宽程度。

### 🛑 检查点 1（必须停下）
把 `01_elements.md`、`01b_issues.md`、`02_keywords.md` 的要点呈现给用户，请其作为律师审核：要素抽取是否准确、案由是否对、**争点体系是否齐全、倾向标签是否合理**、关键词分层是否合理。**得到明确确认（如"可以""开搜"）后才进入第二步。** 若用户要改，改完再确认。

---

## 第二步：检索

### 2.1 迭代检索
从第一层关键词开始调用 `get_case_list`。每轮后判断：
- 若返回 0 条或普通案例过少 → 进入下一层（更宽）关键词。
- 每一轮的结果都累加到样本池，不丢弃。
- 持续迭代直到普通案例数量达到用户目标（或达到上限轮次，见 `methodology/keyword-strategy.md` 的停止条件）。
- 对自然语言难以转关键词、或关键词搜不到的情况，用 `search_case` 语义检索兜底探索，再据其结果反推关键词。

把每一轮的原始返回累加写入 `03_raw_cases.json`（数组，每条**原样保留完整 MCP 字段**，额外加一个 `_query` 字段记录命中它的关键词）。

> ⚠️ **字段保全铁律**：从本步开始，03 → 04 → 05 的每一步都必须**原样保留每条记录的全部 MCP 原始字段**（`Gid`/`Title`/`CaseFlag`/`Ascertain`/`Identified`/`RefereeBasis`/`RefereeResult`/`DefenseViewpoint`/`ControversialFocus`/`Category`/`LastInstanceCourt`/`CaseGrade`/`Url` 等），**只允许追加新字段，绝不可改写或删除原始字段**。下游脚本依赖这些字段名生成 Excel；若被改名或丢弃，Excel 实质内容列会变空。脚本虽有按 `Gid` 回退到 `03_raw_cases.json` 的保护，但仍应从源头保全。

### 2.2 去重
按 `Gid` 去重（同一案件可能被多层关键词命中）。

### 2.3 双轨分流
- `CaseGrade` 含 "07"（普通案例）且 `Ascertain` 非空 → **分析池**。
- 其余（经典/评析等，正文字段空）→ **权威案例附录池**，仅保留 `CaseFlag`/`Title`/`CaseGrade`/`Url`。

### 2.4 相关度筛查
对分析池逐条按 `methodology/relevance-screening.md` 的高/中/低标准与基准案情比对，保留高+中，剔除低。写入 `04_screened_cases.json`。

### 🛑 检查点 2（必须停下）
向用户报告检索情况：用了哪些关键词、各层命中多少、去重后多少、普通案例多少、筛查后保留多少、权威案例附录多少。请用户确认是否对样本量做调整（放宽/收窄/增删）。**得到确认后才进入第三步。**

---

## 第三步：检索后分析

### 3.1 字段加工与编码
对分析池每条普通案例，做两类加工，结果写入 `05_enriched_cases.json`：

**确定性派生**（运行 `python3 scripts/general/normalize_cases.py <research_dir>`）：法院层级、地域、裁判年份、拍平 Category/CaseGrade/LastInstanceCourt。

**判断性编码**（你来推理，逐条标注，**追加**到记录上，保留原始字段）：
- `基本案情摘要`：把 `Ascertain` 浓缩为 150 字内的中立案情概括（Excel 用这个，而非原文照搬）。
- `抗辩要点摘要`：把 `DefenseViewpoint` 浓缩为 100 字内要点。
- `裁判要点摘要`：把 `Identified` 浓缩为 150 字内核心裁判逻辑。
- `判赔金额` / `维权开支`：从 `RefereeResult` 抽取数字（无则填 null）。
- `裁判结果分类`：从 `RefereeResult` 归类为 驳回/全部支持/部分支持/撤销改判 之一。
- 每个争议焦点的 `立场`：从 `Identified` + `RefereeResult` 按 `01b_issues.md` 该焦点的**倾向标签取值集**判断，存入 `焦点立场` 对象 `{"<焦点名>": {"立场": "<倾向标签>", "理由": "..."}}`。**焦点名须与 `01b_issues.md` 一字不差**，否则脚本聚合不到、图表残缺。
- 各抗辩理由 `是否被采纳`：比对 `DefenseViewpoint` 与 `Identified` 的实际采信结果，存入 `抗辩` 数组 `[{"理由": "<与 01b 抗辩清单一致>", "是否被采纳": true/false}]`。
- 连续量（判赔金额、责任/扣除比例等）单列数值字段，勿塞进倾向标签。
- `相关度`：高/中（已在筛查阶段定）。

> 编码产出的 `基本案情摘要`/`抗辩要点摘要`/`裁判要点摘要` 是给 Excel 的"浓缩汇总"列；原始长文本仍保留在记录里，脚本会优先用摘要、缺失时回退原文。

### 3.2 六维统计分析（样本自适应 + 出图）
运行 `python3 scripts/general/run_analytics.py <research_dir>`，按 `methodology/analysis-dimensions.md` 计算六维（交叉关联、抗辩有效性、判赔金额、演进拐点、分歧地图、要素-结果影响度），输出 `06_analytics.json`。脚本同时：
- 接 `stats_guard` 写入 `深度档`（定性深挖/量化主导）、`定量档`（描述→卡方/Fisher→建模）、`地域分歧`/`审级分歧`（分组样本够不够才能下分歧结论），并为主交叉表附带 `检验.phrasing` 措辞。
- 用 `chart_theme` 出三张统一主题图到 `output/_charts/`（`overview`/`issue_freq`/`result_year`）+ `manifest.json`，供报告以 `![chart:key]` 占位插图。matplotlib 缺失时优雅降级，仅跳过出图。

> 写报告前先看 `深度档`/`定量档`/`地域分歧`：它们决定本次报告写多深、能否做显著性检验、要不要写分组分歧。**绝不为凑差异而编造分歧。**

### 3.2b 抓分析池判决全文（报告深度来源，强烈建议）
运行 `python3 scripts/download_fulltext.py <research_dir> [--docx]`，把分析池每条普通案例的 MCP 全要素（`Ascertain/Identified/RefereeBasis/RefereeResult/PlaintiffClaims/DefenseViewpoint/TrialAfter`）按判决书结构拼成每案一份原文，写入 `output/原文/`（+ `00_索引.md`）。**这是报告第二章深度说理的全文来源**——3.3 写作时据此重构法院论证链条、填实〔全文补实〕占位。正文要素全部来自 MCP、不抓 pkulaw 网页，每份附法宝链接溯源。

### 3.3 报告生成（三场景，v2 深度）
**先问用户选哪个场景**：居中 / 攻方（权利人）/ 辩方（平台）。加载对应模板——`templates/report-neutral.md`（居中，做满研报级深度）/ `report-plaintiff.md`（攻方）/ `report-defendant.md`（辩方，后两者复用居中深度内核 + 各加一张策略表）。严格按模板的结构与笔法：
- **结构**：封面 → 执行摘要与核心发现 → 一、研究范围与方法（简版）→ **二、裁判规则全景（按 `01b_issues.md` 的争议焦点逐节，节内"①争点界定 ②主流规则含代表案 ③例外与反向 ④小结"四段）** → 三、综合分析（裁判规则地图表 + 控辩/攻/辩策略表）→ 四、结论 → 附录（权威案例索引 + 方法论）。
- **深度由 `深度档` 与全文驱动**：`qualitative_deep`（小样本）时每焦点 500–1500 字真实说理，据 `output/原文/` 重构法院论证链条、代表案细读、正反对称（2 正 + 2 反）；`quantitative_lead`（大样本）时定性收敛、量化承载全景。缺全文处以〔全文补实：…〕占位。
- **引注入脚注**：正文只出现「案件简称（案号·法院）」，案件全称/链接/法条条款入脚注；正文不得出现裸链接。
- **图表占位符**：用 `![chart:overview]`/`![chart:issue_freq]`/`![chart:result_year]` 控制位置。
- **遵守全局铁律**：禁工序词、结论体、分组分歧受闸门、推断措辞带 `检验.phrasing`。

报告写入 `output/类案分析报告_<场景>.md`。Markdown 开头须含封面元信息行（每行 `**键**：值`），**务必含一行 `**报告主题**：<简洁主题>`**（用作 Word 封面主标题，简洁凝练，如"算法推荐短视频侵权案件的类案检索"，而非冗长全称），随后 `报告人`/`报告日期`/`检索地域`/`分析样本` 署名行（排在封面底部，默认取 `CLAUDE.md`）。

### 3.4 报告转 Word（排版精美的 .docx）
运行 `python3 scripts/build_report_docx.py <research_dir> 类案分析报告_<场景>.md`（**第二个参数是报告文件名，不可省略**），把上一步的 Markdown 报告渲染成中文法律文书排版的 Word：封面、目录、分级标题（黑体）、正文（宋体 1.5 倍行距首行缩进）、表格、`[案名（案号·法院）](链接)` 转脚注、在 `![chart:key]` 占位符处插入 §3.2 生成的图表（读 `output/_charts/manifest.json`）、页码。输出 `output/类案分析报告_<场景>.docx`。Markdown 作为草稿保留，Word 是最终交付物。

### 3.5 Excel 生成
运行 `python3 scripts/general/generate_excel.py <research_dir>`，按 `templates/excel-schema.md` 定义（固定字段 + 浓缩摘要列 + 动态争议焦点列）生成 `output/案件清单.xlsx`。脚本会按 `Gid` 从 `03_raw_cases.json` 回退补全任何缺失的实质字段。

> 分析案件判决原文已在 §3.2b 抓取到 `output/原文/`，作为报告深度来源；此处不再重复。

### 3.6 反幻觉收尾自检（强制，不可跳过）
报告与 Excel 生成后，运行 `python3 scripts/verify_report.py <research_dir>`：脚本扫描成品报告里的每一个案号，逐一比对本次样本池（`03_raw_cases.json`/04/05），凡引用了样本池中不存在的案号即报错并非零退出。**必须通过后才交付**；若报错，逐条核对是来源遗漏（补检索）还是笔误/幻觉（订正），不得带着 FAIL 交付。这是"反幻觉铁律"的机器化兜底。

---

## 反幻觉铁律（贯穿全程）

- **禁止凭记忆或想象生成案号、案件、裁判内容。** 一切案件数据必须来自 MCP 返回。
- 报告/Excel 引用任何案号时，必须带 `CaseFlag`（标准化案号）+ 审理法院 + `Url`（pkulaw 链接）以便溯源。
- 输出案号用 MCP 的 `CaseFlag`，不要用可能不规范的原文写法。
- 对用户提供或不确定的案号，用 `anhao_recognition` 验真；验不到要明确告知"该案号未在北大法宝库验证到"。
- 区分判例权威性：`CaseGrade` 为指导案例/公报案例的判例具参照效力，应优先引用并标注；普通案例不具强制力，引用时注明"参考类案"。
- 不同法院/不同年份判决可能不一致，多条引用时标注差异并给出主流裁判倾向。

## 本次研究产出文件清单

```
research/<主题>_<日期>/
├── 00_input.md            用户输入
├── 01_elements.md         案情要素
├── 01b_issues.md          本主题争点体系（焦点/倾向标签/抗辩清单，检查点1）
├── 02_keywords.md         三层关键词（检查点1）
├── 03_raw_cases.json      检索原始累加
├── 04_screened_cases.json 去重+筛查后（检查点2）
├── 05_enriched_cases.json 加工编码后
├── 06_analytics.json      六维统计 + 样本自适应判定（不在成品中提及其文件名）
└── output/
    ├── _charts/                   统一主题图表 + manifest.json（报告占位符插图）
    ├── 类案分析报告_<场景>.md     工作草稿
    ├── 类案分析报告_<场景>.docx   最终交付（封面/目录/脚注/图表/页码）
    ├── 案件清单.xlsx
    └── 原文/                      分析案件判决原文，每案一份 + 00_索引.md（报告深度来源）
```
