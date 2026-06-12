#!/usr/bin/env python3
"""
spot_check_coding.py —— 判断性编码质量抽检（内容分析信度的工程化替代）
─────────────────────────────────────────────
用法：python3 scripts/general/spot_check_coding.py <research_dir> [--rate 0.15] [--min 3] [--seed 42] [--all]

背景：焦点立场/问题观点/抗辩采纳等核心编码由 LLM 判断产生，单跑无信度指标。
本脚本随机抽取编码池的一部分（默认 15%、至少 3 件，--seed 可复现），把每件的
**编码结论与判决原文关键段并排**生成对照文档 `<research_dir>/编码复核.md`，
供检查点呈报用户逐件复核；复核结论（确认/更正）由用户批注留痕，更正项须写回 05 并重跑
validate_pipeline。这一步是 SKILL 的强制工序，不得跳过。

（编码者信度的完整方案——同案双跑比对 Kappa——见 ROADMAP 三期候选。）
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/general/spot_check_coding.py <research_dir> "
                 "[--rate 0.15] [--min 3] [--seed 42] [--all]")
    rd = Path(sys.argv[1])
    rate = float(sys.argv[sys.argv.index("--rate") + 1]) if "--rate" in sys.argv else 0.15
    n_min = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 3
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 42

    cases = json.loads((rd / "05_enriched_cases.json").read_text(encoding="utf-8"))
    if "--all" in sys.argv:
        sample = cases
    else:
        k = min(len(cases), max(n_min, round(len(cases) * rate)))
        sample = random.Random(seed).sample(cases, k)

    lines = [f"# 编码抽检复核单（{date.today().isoformat()}）", "",
             f"> 编码池 {len(cases)} 件，抽检 {len(sample)} 件（seed={seed}）。请逐件比对"
             f"【编码结论】与【原文摘录】，在复核栏勾选；更正项写回 05 后重跑 validate_pipeline。", ""]
    for i, c in enumerate(sample, 1):
        flag = c.get("CaseFlag") or c.get("案号", "?")
        lines += [f"## {i}. {flag}　{(c.get('Title') or c.get('案件名称') or '')[:36]}", "",
                  f"**编码结论**：结果分类＝{c.get('裁判结果分类','—')}；判赔＝{c.get('判赔金额','—')}"]
        qv = c.get("问题观点") or {}
        fp = c.get("焦点立场") or {}
        for q, info in (qv or {k: {"倾向标签": v.get("立场"), "裁判观点": v.get("理由")}
                              for k, v in fp.items()}).items():
            lines.append(f"- {q} → **{info.get('倾向标签','')}**（{(info.get('裁判观点') or '')[:60]}）")
        for d in (c.get("抗辩") or []):
            lines.append(f"- 抗辩「{d.get('理由')}」→ {'采纳' if d.get('是否被采纳') else '未采纳'}")
        idf = (c.get("Identified") or "")[:500]
        res = (c.get("RefereeResult") or "")[:220]
        lines += ["", "**原文摘录（本院认为·前 500 字）**：", f"> {idf}", "",
                  "**原文摘录（裁判结果·前 220 字）**：", f"> {res}", "",
                  "**复核**：□ 确认无误　□ 更正（说明：＿＿＿＿＿＿）", "", "---", ""]

    out = rd / "编码复核.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"抽检 {len(sample)}/{len(cases)} 件 → {out}")
    print("▸ 请将复核单随检查点呈报用户逐件确认；更正写回 05 并重跑 validate_pipeline。")


if __name__ == "__main__":
    main()
