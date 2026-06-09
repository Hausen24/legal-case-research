# AGENTS.md —— 给 AI 智能体的运行指南（工具无关）

> 本文件是 [AGENTS.md 约定](https://agents.md)，很多 AI 编程工具会自动读取。
> 它说明：**任何**有能力读取仓库文件、调用 Python/Node、（可选）调用 MCP 的 AI 智能体，
> 都能驱动本项目产出"类案检索研究报告 + 清单 Excel"——不限于 Claude。

## 这个项目是什么

把"一段案情/一个检索要求"跑成**可溯源、带图表、研报级排版的类案研究报告（Word）+ 案件清单（Excel）**。
两套工作流（技能）：

- `skills/case-research/SKILL.md` —— **标准类案检索**：一段案情 → 找相似类案 → 分析。
- `skills/group-litigation-research/SKILL.md` —— **集团/群体性诉讼**：一个共同事件派生大量平行判决，
  从中按"主体+事件"分组筛出核心实质判决（内置证券虚假陈述为示范样例）。

每套技能都是**自包含的 SOP**（三步、两个人工确认点）。智能体的任务就是：读对应 SKILL.md，
严格照它执行，在两个检查点停下等用户确认。

## 数据从哪来（两种，二选一）

1. **北大法宝 MCP（默认）**：在 `.mcp.json` 配置法宝订阅（见 `.mcp.json.example`），由技能第二步实时检索。
   需要宿主支持 MCP（见下表）。
2. **自带数据（无需法宝/无需 MCP）**：你用任意途径拿到判决，按 `examples/输入数据契约.md` 整理成扁平
   CSV/JSON，用 `python3 scripts/general/import_cases.py <dir> --json/--csv <file>` 转成 `03_raw_cases.json`，
   再从技能的"筛查/编码"步接入。分析与产出链路完全相同。

## 一个智能体应当怎么跑

1. **读** 对应的 `SKILL.md`（以及它引用的 `methodology/`、`templates/`）。若用户有个人偏好，读 `CLAUDE.md`
   （从 `CLAUDE.example.md` 复制而来）。
2. **取数据**：走 MCP 检索，或走自带数据导入（上节）。
3. **守纪律**：严格遵守 SKILL 的**反幻觉铁律**（不编案号/案件/裁判内容；引用必带案号+法院+链接）与
   **两个检查点**（关键词确认、检索情况确认——必须停下等人工确认）。
4. **跑脚本**（纯 Python/Node，任何环境可运行）：
   ```bash
   pip install -r requirements.txt && npm install
   python3 scripts/general/normalize_cases.py <dir>        # 确定性派生
   python3 scripts/general/run_analytics.py   <dir>        # 统计 + 出图
   python3 scripts/general/generate_excel.py  <dir> --name "<案件类别>" --date <YYYYMMDD>
   python3 scripts/build_report_docx.py <dir> "<案件类别>-类案检索报告-<YYYYMMDD>.md"
   python3 scripts/verify_report.py <dir>                  # 反幻觉收尾自检（必须通过）
   ```
   （集团诉讼工作流用 `scripts/securities/*` 对应脚本，见其 SKILL。）
5. **写报告**：报告正文（法律说理）由智能体撰写，质量取决于模型能力——建议用强推理模型。
6. **交付前**必须跑 `scripts/verify_report.py` 通过：它机器校验报告里每个案号都能在数据池中溯源。

## 哪些 AI 能跑完这套工作流

| 能力档 | 工具举例 | 能做到 |
|---|---|---|
| **MCP + 读文件 + 跑命令（全自动）** | Claude Code（原生）、Claude Desktop、Cline、Cursor、Windsurf 等支持 MCP 的宿主 | 法宝检索 + 全链路产出，端到端 |
| **读文件 + 跑命令（自带数据模式）** | 上述工具 + Continue、Roo Code、Aider、OpenAI Codex CLI、Gemini CLI、GitHub Copilot 智能体 | 不走 MCP，用 `import_cases.py` 导入自备数据后全链路产出 |
| **能写并运行代码（半自动）** | ChatGPT（代码解释器）等 | 你贴入数据，模型按 SKILL 编码、调脚本，产出报告/Excel（检索与 MCP 部分需你在外部完成） |

> 说明：脚本层（normalize / run_analytics / generate_excel / build_report_docx / verify_report）是**纯确定性
> 程序**，`python3`/`node` 即可运行，不依赖任何特定 AI。AI 负责的是 SKILL 里的**判断性**部分
> （争点编码、法律说理、检索策略）——这部分换任何强模型都能做，只是说理深度随模型而异。

## 反幻觉是硬约束

无论用哪个 AI、哪种数据源：报告引用的每个案号都必须能在 `03/04/05_*.json` 数据池中找到。
`scripts/verify_report.py` 会强制校验；CI 也会跑它。这条不因换工具而豁免。
