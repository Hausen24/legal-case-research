# 类案研究工作流（北大法宝 MCP × Claude Code）

把一段案情 + 检索要求，自动跑成「类案分析报告 + Excel 清单」。本项目内置两套工作流：

| 技能 | 适用 | 去重逻辑 | 分析口径 | 产出 |
|------|------|----------|----------|------|
| **case-research**（通用类案研究） | 任意案情 + 数量/地域/法院级别要求 | 按 Gid 去重 | 六维统计 + 居中/攻方/辩方三场景 | 报告 + 案件清单 Excel |
| **securities-misrep-research**（证券虚假陈述专题） | 京沪金融法院等证券虚假陈述责任纠纷 | 按"公司+事件"分组、组内留核心判决，平行判决仅留痕 | 13 问题体系逐问梳理 + 京沪比较 | 比较研究报告 + 核心判决清单 Excel |

两套共用同一份 `.mcp.json`、`CLAUDE.md`、`scripts/build_report_docx.py` 和 `scripts/common/` 公共层。

---

## 目录结构

```
case-research/
├── .mcp.json                 ← 你的真实 MCP 配置（从 .mcp.json.example 改，填 Token；已 gitignore）
├── .mcp.json.example         ← 配置模板（3 个必备服务 + 1 个可选法律法规服务）
├── CLAUDE.md                 ← 实践画像（先填你的偏好）
├── README.md
├── skills/
│   ├── case-research/                ← 通用类案研究技能
│   │   ├── SKILL.md
│   │   ├── methodology/              ← 关键词策略 / 六维分析 / 相关度筛查
│   │   └── templates/                ← 三场景报告模板 + Excel schema
│   └── securities-misrep-research/   ← 证券虚假陈述专题技能
│       ├── SKILL.md
│       ├── methodology/              ← 13 问题体系 / 核心判决识别+京沪比较
│       └── templates/                ← 证券比较研究报告模板
├── scripts/
│   ├── common/pkulaw_utils.py        ← 公共派生函数（clean_url / 法院层级含金融法院 / 字段回退…）
│   ├── build_report_docx.py          ← 报告转 Word（两技能共用）
│   ├── general/                      ← normalize_cases · run_analytics · generate_excel
│   └── securities/                   ← normalize_secmisrep · run_analytics_secmisrep · generate_excel_secmisrep
└── research/                 ← 每次研究一个子目录（自动生成，默认 gitignore）
```

## 首次使用

1. **填 MCP 配置**：把 `.mcp.json.example` 复制为 `.mcp.json`，两处 `你的Token` 替换为你的真实 Token。
   ```bash
   cp .mcp.json.example .mcp.json
   open -e .mcp.json   # 改 Token
   ```
2. **填实践画像**：打开 `CLAUDE.md`，把【待填】处改成你的偏好（角色、文风、报告格式、署名等）。
3. **装依赖**：`pip3 install pandas openpyxl`
4. **在本目录启动 Claude Code**：
   ```bash
   cd ~/Documents/case-research
   claude
   ```
   建议 `/model` 切到 Opus 4.8 做分析。输入 `/mcp` 确认三个服务都 Connected。

> ⚠️ 第 4 个「检索法律法规」服务为**可选**，仅证券专题的法条原文核对会用到；不订阅也能跑通主流程（详见 `.mcp.json.example` 里的说明）。

## 跑一次研究

### A. 通用类案研究（case-research）
在 Claude Code 里直接说，例如：

> 做一次类案研究。案情：短视频平台通过算法推荐机制，向用户推送了其他用户上传的未经授权的影视作品剪辑片段；权利人多次通知平台后，平台未采取有效措施。检索要求：北京、上海、广州三地法院；二审或再审优先；2021 年至今；目标 50 件普通案例。

Claude Code 会：
1. 抽取案情要素、构建三层关键词 → **停下让你确认（检查点 1）**
2. 多轮检索北大法宝、去重、双轨分流、相关度筛查 → **报告检索情况让你确认（检查点 2）**
3. 字段编码 → 六维统计 → 问你选场景（居中/攻方/辩方）→ 生成报告 + Excel

### B. 证券虚假陈述专题（securities-misrep-research）
> 做一次证券虚假陈述类案裁判规则研究，请加载 securities-misrep-research 技能。系统检索"证券虚假陈述责任纠纷"案由下北京/上海金融法院及对应高院的核心判决，按 13 问题体系逐问题梳理裁判观点、做京沪比较，平行判决仅留痕。

Claude Code 会：
1. 搭 13 问题体系、定关键词轮替与事件清单 → **停下让你确认（检查点 1）**
2. 关键词轮替检索 + 后过滤、按"公司+事件"分组识别核心判决 → **交你校核分组（检查点 2）**
3. 按问题编码 → 京沪交叉分析 → 联网核对典型案例名录 → 生成比较研究报告 + 核心判决清单 Excel

## 产出

```
research/<主题>_<日期>/output/
├── 类案分析报告_<场景>.md / .docx
├── 案件清单.xlsx（证券专题为 核心判决清单.xlsx）
└── 原文/              （可选）分析案件判决原文，每案一份 + 00_索引.md
```

> 原文导出：`python3 scripts/download_fulltext.py <research_dir> [--docx]`。读分析池 `05_enriched_cases.json`——通用工作流导出全部普通案例原文；证券专题因 05 已折叠为核心判决，**批量同案只导出示范判决/核心判决**。正文要素来自北大法宝 MCP（非网页抓取），每份附法宝链接溯源；非普通案例正文为空，仅导出元数据+链接。

## 关键设计

- **只有普通案例（CaseGrade=07）有完整判决书要素**，进分析管道；经典/评析案例进 Excel 第二个 sheet「权威案例附录」。
- **关键词铁律**：案由词放 title，方法论词放 fulltext（否则会命中评析文章而非判决书）。
- **反幻觉**：所有案件来自 MCP，引用必带案号+法院+pkulaw 链接，不凭记忆编造。

## 调整工作流

- 改报告风格/格式 → 改 `CLAUDE.md`
- 改通用六维分析 → 改 `skills/case-research/methodology/analysis-dimensions.md` 和 `scripts/general/run_analytics.py`
- 改通用 Excel 字段 → 改 `skills/case-research/templates/excel-schema.md` 和 `scripts/general/generate_excel.py`
- 改证券问题体系 → 改 `skills/securities-misrep-research/methodology/issue-framework.md`（13 问题键名须与脚本 `ISSUES` 一致）
- 改公共派生（法院层级/链接清洗等）→ 改 `scripts/common/pkulaw_utils.py`（两套工作流同时生效）

> v0.2：在通用版基础上新增证券虚假陈述专题；公共派生函数已抽到 `scripts/common/`，两套工作流共享一处维护。
