#!/usr/bin/env python3
"""
validate_pipeline.py —— 管道数据契约校验 CLI
─────────────────────────────────────────────
用法：python3 scripts/validate_pipeline.py <research_dir> [--strict]

对 <research_dir> 下存在的 03/04/05/06 JSON 逐段校验（契约见
scripts/common/pipeline_schema.py），打印分段结果：
  · error   —— 数据契约被破坏（类型错/枚举外/必填缺/焦点名拼写漂移），退出码 1。
  · warning —— 可疑但不阻断（如 07 案例正文为空、缺 Url）；--strict 时升级为失败。

工作流位置：编码写完 05 之后、跑分析/出 Excel 之前运行；CI 对 demo 全量跑。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "common"))
import pipeline_schema as ps  # noqa: E402

STAGES = [
    ("03_raw_cases.json", ps.validate_03),
    ("04_screened_cases.json", ps.validate_04),
    ("05_enriched_cases.json", ps.validate_05),
    ("06_analytics.json", ps.validate_06),
]


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/validate_pipeline.py <research_dir> [--strict]")
    rd = Path(sys.argv[1])
    strict = "--strict" in sys.argv
    if not rd.exists():
        sys.exit(f"目录不存在：{rd}")

    total_err = total_warn = 0
    ran = 0
    for name, fn in STAGES:
        p = rd / name
        if not p.exists():
            continue
        ran += 1
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"── {name} ──  ❌ JSON 解析失败：{e}")
            total_err += 1
            continue
        rep = fn(data)
        status = "✅" if rep.ok and not (strict and rep.warnings) else ("❌" if not rep.ok else "⚠️")
        print(f"── {name} ──  {status}  error {len(rep.errors)} / warning {len(rep.warnings)}")
        for m in rep.errors:
            print(f"   ✗ {m}")
        for m in rep.warnings:
            print(f"   ⚠ {m}")
        for m in rep.info:
            print(f"   · {m}")
        total_err += len(rep.errors)
        total_warn += len(rep.warnings)
        print()

    if ran == 0:
        sys.exit(f"{rd} 下未找到任何管道文件（03/04/05/06）。")
    if total_err or (strict and total_warn):
        print(f"结论：校验未通过（error {total_err}，warning {total_warn}"
              f"{'，--strict 模式下 warning 亦失败' if strict and total_warn else ''}）。"
              f"请修复后再进入下一步。")
        sys.exit(1)
    print(f"结论：数据契约校验通过（{ran} 个阶段，warning {total_warn}）。")


if __name__ == "__main__":
    main()
