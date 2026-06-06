---
name: securities-misrep-research
description: 证券虚假陈述责任纠纷的裁判规则研究工作流（北大法宝 MCP）。当用户要在特定法院（如北京金融法院、上海金融法院及对应高院）、特定时间范围内，就"证券虚假陈述责任纠纷"案由系统检索核心判决、识别并剔除示范判决之外的平行判决、沿侵权构成要件五维体系逐问题深度梳理裁判规则、交叉核对典型案例名录、核验裁判依据法规时效、最终产出"可对外的投研级裁判规则研究报告 + 长表核心判决清单 Excel"时使用本技能。覆盖问题体系搭建、关键词轮替检索（绕开 MCP 无法院过滤/无翻页/每查询前10条的限制）、核心判决识别去重、相关度筛查、按问题编码、样本量自适应的定量分析与定性深挖、法条原文溯源、典型案例联网交叉核对、居中学术口径报告生成。
---

# 证券虚假陈述类案裁判规则研究（北大法宝 MCP）

本技能与通用 `case-research` 的区别：① 去重不靠 Gid，而是按"涉案上市公司＋虚假陈述事件"分组、组内只留**核心判决**（示范判决/代表人诉讼/说理最完整者），剔除海量平行判决；② 分析沿**虚假陈述侵权构成要件五维一条线（主体→行为→损害后果→因果关系→主观过错，程序事项作补充）**逐问题深度梳理；③ 目标是"四家法院该案由下的全部核心判决"，而非凑 N 件；④ 联网交叉核对**典型案例名录**，并核验裁判依据法规真伪与时效。默认**居中学术口径**。

> **分析重心**：以五维构成要件逐问题**深度展开**为唯一主线。**地域（京沪）差异不单设章节、不逐问题设小节**；是否指出地域分歧由 `scripts/common/stats_guard.py` 的 `divergence_gate` 依样本量裁定——样本不足时不作地域比较，仅在确有个案取向不同处于相关问题内一句话点出。

严格按三步、两个人工确认点执行，未获确认前不进入检索或分析。每次开工先读 `CLAUDE.md` 套用文风/署名偏好。

## 全局铁律（贯穿全程，违反即返工）

- **反幻觉**：禁止凭记忆生成案号、案件、裁判内容、法规文号；一切来自 MCP。引用案号必带 `CaseFlag`＋审理法院＋裸链接。`search_case` 仅作发现，正式数据以 `get_case_list` 全要素为准。
- **禁止泄露内部产物名与工序词**：成品报告/Excel 中不得出现 `06_analytics.json`、`sheet`、`脚本`、`编码列`、`留痕`、`引 xxx`、`自动标注` 等任何工序词；数据出处统一写"数据来源：本报告样本（N=…）"。
- **深度由全文驱动**：报告的实质说理须基于裁判文书全文（`scripts/download_fulltext.py` 抓取）重构；缺全文处以〔全文补实：…〕显式占位，不得凭摘要一笔带过、亦不得编造。
- **样本自适应**：定量强度与定性深度均随样本量自适应（见 §3.3、`stats_guard.py`）。

## 前置依赖

**MCP 服务/工具**（须已在 `.mcp.json` 配置并连接；工具服务标识符以你 `.mcp.json` 的 key 为准；Claude Code 下 `type` 写 `"http"`，`Bearer` 后留一个空格）：
- **检索司法案例-关键词** → `get_case_list`（`title` / `fulltext`，至少填一个）。硬约束：无法院/时间过滤、无翻页、每唯一查询仅前 10 条；单条返回 25+ 字段含完整判决书要素。数据骨干。URL `mcp-case`。
- **检索司法案例-语义** → `search_case`（`text`）。只返回轻量摘要（snake_case），不含完整要素；仅作发现/兜底，命中后用 `title`/`case_number` 回查 `get_case_list` 取全要素再入池。不可直接当 `get_case_list` 记录写入 03。URL `mcp-case-search-service`。
- **案号识别** → `anhao_recognition`（`text`）。案号验真反幻觉，仅校验不入管道。
- **法律法规（关键词/语义/精准）** → `get_law_list`（含 `TimelinessDic` 时效：01现行/02废止/03已修改）、`search_article`/`get_article`（中文条号）、`get_law_item_content`（`tiao_num` 为阿拉伯数字整数）。用于核验裁判依据法规真伪、时效、文号、逐条原文。三个法规服务可选；未配置则 3.1 法规核对降级人工/跳过，不阻断主流程。

**脚本**（`python3` 运行；公共派生函数在 `scripts/common/pkulaw_utils.py`）：
- `scripts/securities/normalize_secmisrep.py` — 确定性派生：法院层级（含金融法院档）、法院地（京/沪）、年份、文书类型、涉案公司兜底。
- `scripts/securities/run_analytics_secmisrep.py` — 样本概况 + 各问题倾向整体分布 + 责任主体/形态/系统风险分布；**调用 `stats_guard` 决定定量档与地域分歧闸门**；产出供 `chart_theme` 出图的数据键。
- `scripts/securities/generate_excel_secmisrep.py` — 三 sheet 长表：判决要点（长表，案件级合并、按争点分叉）/ 争点编码（tidy，供统计）/ 案例索引（平行＋典型）。
- `scripts/build_report_docx.py` — **共用渲染层**（薄包装，内部调用 `render_report.mjs`）：解析报告 Markdown，链接转脚注、`![chart:key]` 占位符插图、封面单页垂直居中、套设计系统出 .docx。
- `scripts/chart_theme.py` — **共用**图表主题（冷色渐变＋深红强调、small-multiples、去框线、数值标注）。
- `scripts/common/stats_guard.py` — **共用**样本量自适应闸门（`depth_mode` 定性强度、`crosstab_test` 定量检验、`divergence_gate` 地域分歧）。

**方法论**：`methodology/issue-framework.md`（五维问题体系）、`methodology/core-judgment-and-comparison.md`（核心判决识别 + 典型案例交叉核对）。**模板**：`templates/report-secmisrep.md`。

## 关键事实（务必牢记）

1. **核心判决远少于判决总量**：一个事件派生几十上百份平行判决，只核心判决（示范/代表人/二审）有完整说理。只分析核心判决；平行判决仅留痕。
2. **只有 `CaseGrade` 含 "07"（普通案例）的条目有完整正文**（`Ascertain`/`Identified`/`RefereeBasis`/`RefereeResult`）；经典/公报/指导案例正文空，进典型案例索引。
3. **`get_case_list` 限制**：title/fulltext、前 10 条、无翻页、无法院过滤；靠 `fulltext` 关键词轮替"翻面"，结果按 `LastInstanceCourt` 后过滤。`Url` 取裸链接（`clean_url` 已处理）。
4. **完整性不可保证**：以关键词轮替 + `search_case` 发现 + 典型案例名录交叉核对逼近，缺口在检查点 2 如实报告。

---

## 第一步：检索前准备

### 1.1 接收输入
记入 `research/<主题>_<日期>/00_input.md`：案由（证券虚假陈述责任纠纷）、目标法院、时间锚（上海金融法院 2018-08 起、北京金融法院 2021-03 起；两家高院按其受理对应金融法院上诉/再审时间；成立前判决不纳入）。

### 1.2 问题体系搭建
按 `methodology/issue-framework.md` 列出五维下的 14 项问题清单写入 `01_issues.md`，每项给出定义、争点、待提取的倾向标签取值集合。

### 1.3 检索方案
按 `methodology/core-judgment-and-comparison.md` + 关键词约定写入 `02_keywords.md`：固定 `title="证券虚假陈述责任纠纷"`；`fulltext` 轮替清单（问题词、年份、预研得到的京沪重大事件公司名）；过滤规则（`LastInstanceCourt` 四家法院之一、`DocumentAttr` 只留判决书）；典型案例名录交叉核对计划。

### 🛑 检查点 1（必须停下）
把 `01_issues.md` 与 `02_keywords.md` 呈给用户作律师审核（问题是否齐全、案由写法、轮替策略、时间锚）。**获明确确认后才进入第二步。**

---

## 第二步：检索与核心判决识别

### 2.1 轮替检索（绕开 MCP 限制）
对每个 `fulltext` 轮替词调一次 `get_case_list`（title 固定为案由），靠变换 fulltext 取不同前 10 条；`search_case` 仅作语义发现，命中后回查 `get_case_list` 取全要素再入池。每轮按 `LastInstanceCourt` 过滤四家法院、按 `DocumentAttr` 只留判决书；累加写 `03_raw_cases.json`（原样保留全部 MCP 字段，加 `_query`）。

> ⚠️ **字段保全铁律**：03→04→05 每步原样保留每条记录全部 MCP 原始字段（`Gid/Title/CaseFlag/Ascertain/Identified/RefereeBasis/RefereeResult/DefenseViewpoint/ControversialFocus/Category/LastInstanceCourt/CaseGrade/Url/LastInstanceDate/CaseClassName/DocumentAttr/TrialStep/TrialAfter` 等），只追加不改写。下游脚本依赖这些字段名。**`DefenseViewpoint`（抗辩意见）与 `ControversialFocus`（争议焦点）尤为关键——它们是 Excel 长表"各方抗辩主张及理由""争议焦点"列、以及报告④段抗辩逻辑的数据源，务必保全。**

### 2.2 核心判决识别（去重核心）
按 `methodology/core-judgment-and-comparison.md`：① 按 `Gid` 去重；② 从 `Title`+`Ascertain` 分组（公司＋事件）；③ 组内识别核心判决（命中"示范判决/代表人诉讼"优先，否则取说理最完整者），标 `核心判决类型`；④ 其余为平行判决（仅留 `CaseFlag/Title/涉案公司/Url/所属核心Gid`）；⑤ `CaseGrade` 非 07 的正文空记录→典型案例池。

### 2.3 相关度筛查
逐条与案由基准比对剔除无关项，标 `相关度`，保留高+中。三池写入 `04_screened_cases.json`（`_track`: core/parallel/typical）。

### 🛑 检查点 2（必须停下）
报告：轮替词与各轮命中数、过滤后数、分组数（**列出覆盖的事件/公司清单**）、核心判决数、平行留痕数、典型案例数、**覆盖缺口**。请用户校核分组与核心判决判定。获确认后进入第三步。

---

## 第三步：分析与产出

### 3.1 按问题编码（写入 `05_enriched_cases.json`，仅核心判决）
**确定性派生**：`python3 scripts/securities/normalize_secmisrep.py <research_dir>`。
**判断性编码**（逐条追加，保留原始字段）：
- `涉案上市公司` / `虚假陈述事件`（一句话）/ `核心判决类型`。
- `基本案情（六要素）`：按"时间·地点·主体—起因·经过·结果"写成完整叙事（供 Excel 长表"基本案情"列），不得用"同事件群后续个案"等黑话。
- `裁判结果分类`（驳回/全部支持/部分支持/撤销改判）/ `判赔金额` / `系统风险扣除比例`（0–1，无则 null）。
- `是否典型案例`（入选名录则填名录名）。
- `问题观点`：对 framework 的 14 问题逐一编码（未涉及则略），`{ "<问题名>": {"倾向标签":"...","争议焦点":"...","各方抗辩":"...（取自 DefenseViewpoint/ControversialFocus）","裁判观点":"..."} }`。问题名须与 framework 一字不差。
- `法规核对`（可选，需法规 MCP）：对 `RefereeBasis` 关键法规逐部核对存在性与时效（`TimelinessDic`）；引用已废止/修订法规须标注。逐条原文用 `get_law_item_content`/`get_article` 核验。
- `相关度`。

### 3.2 联网交叉核对典型案例
联网核对四家法院历年典型/十大/参考案例中的虚假陈述案，命中者标名录；名录中有而样本缺的列缺口补检。**红线**：名录可联网，裁判事实/观点/案号仍以 MCP 为准，不得据网络编造。

### 3.3 数据分析（样本量自适应）
`python3 scripts/securities/run_analytics_secmisrep.py <research_dir>` → 分析数据：样本概况、法院×审级×年份×结果分布、**各问题倾向整体分布（报告主线数据）**、责任主体/形态/系统风险分布、法规时效、年度趋势。脚本调用 `stats_guard`：
- **定量档**：`stat_tier(n)` 决定只做描述性（小样本）还是解锁卡方/Fisher/Cramér's V/相关。每个推断结论须带其 `phrasing` 措辞与样本警示；小样本一律标"示取向非占比定论"。
- **地域分歧**：`divergence_gate({地:件数})`；`report=False` 时分析数据中地域分歧列表为空，报告据此**不写任何地域分歧小节**，至多按其 `phrasing` 在结论一句话交代。
- **深度档**：`depth_mode(独立事件数)` 写入分析数据，指示报告写作的定性/定量侧重（见 3.4）。

### 3.4 报告生成（居中学术口径，投研级深度）
加载 `templates/report-secmisrep.md`，严格按其结构与笔法。要点复述：
- 结构：封面 → 执行摘要与核心发现 → 一、研究范围与方法 → **二、裁判规则全景（五维构成要件各一节，节内"①争点界定 ②主流裁判规则(代表案例) ③例外与反向 ④评析要点"四段）** → 三、综合分析（裁判规则地图表＋控辩指引表）→ 四、结论 → 附录（案例索引＋方法论）。
- **深度**：`depth_mode=qualitative_deep`（本批小样本）时，每个具体争点展开 500–1500 字真实说理，把法院论证链条（请求权基础与司法解释条款→各方抗辩→法院说理与取舍→结论）如实重构，代表案细读；样本大时转 `quantitative_lead`，定性收敛、量化承载全景。
- **引注**：正文"案名（案号·法院）"+脚注；司法解释精确到条/款/项入脚注；网址只入脚注。每个子问题配 1–2 代表案。
- **图表**：用占位符 `![chart:overview]`/`![chart:issue_freq]`/`![chart:result_year]` 控制位置。
- 报告 Markdown 开头含 front-matter 封面信息（`**报告主题**：证券虚假陈述裁判规则研究——以京沪金融法院核心判决为样本`，及报告人/日期/检索法院/样本行）。写入 `output/类案分析报告_证券虚假陈述.md`。

### 3.5 报告转 Word
`python3 scripts/build_report_docx.py <research_dir> 类案分析报告_证券虚假陈述.md` → 封面/目录/脚注/图表/页码的 .docx。

### 3.6 Excel 生成（长表）
`python3 scripts/securities/generate_excel_secmisrep.py <research_dir>` → `output/核心判决清单.xlsx`（三 sheet，schema 见 `case-research/templates/excel-schema.md`）：判决要点（长表，案件级合并、按争点分叉、含六要素基本案情）/ 争点编码（tidy）/ 案例索引。

### 3.7 导出核心判决原文（供深度写作）
`python3 scripts/download_fulltext.py <research_dir> [--docx]` → 每案一份原文写入 `output/原文/`（+ `00_索引.md`）。**这是报告深度的全文来源**：3.4 写作时据此重构法院论证、填实〔全文补实〕占位。

---

## 产出文件清单
```
research/<主题>_<日期>/
├── 00_input.md / 01_issues.md / 02_keywords.md     （检查点1）
├── 03_raw_cases.json / 04_screened_cases.json       （检查点2）
├── 05_enriched_cases.json                            按问题编码（含基本案情/抗辩/争点）
├── <分析数据>                                         样本量自适应分析（不在成品中提及其文件名）
└── output/
    ├── 类案分析报告_证券虚假陈述.md / .docx
    ├── 核心判决清单.xlsx
    └── 原文/                                          核心判决原文 + 00_索引.md
```
