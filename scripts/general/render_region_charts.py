#!/usr/bin/env python3
"""
render_region_charts.py —— 地域图表模块（两模式通用，幂等可重跑）
─────────────────────────────────────────────
用法：python3 scripts/general/render_region_charts.py <research_dir>

生成并并入 manifest（不覆盖其他图）：
  region_dist.png   全国样本判决书地域分布（基于 03 全量，专门法院归省）
  issue_region.png  争点×地域观点热力矩阵（基于 05 深度编码池；地域<2 省时自动跳过）

定位：run_analytics*（两版）各自负责 overview/issue_freq/result_year 三图；
本脚本补学理/全景所需的地域两图。analytics 重跑后须重跑本脚本以回填 manifest。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "common")]
from pkulaw_utils import (  # noqa: E402
    load, flatten_court, flatten_leaf, normalize_province,
)
import chart_theme as ct  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/general/render_region_charts.py <research_dir>")
    rd = Path(sys.argv[1])
    charts = rd / "output" / "_charts"
    charts.mkdir(parents=True, exist_ok=True)
    mp = charts / "manifest.json"
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    ct.apply_theme()

    # ── region_dist：03 全量判决书地域分布 ──
    raw = load(rd / "03_raw_cases.json")
    reg = Counter()
    for c in raw:
        if flatten_leaf(c.get("DocumentAttr")) != "判决书":
            continue
        p, court = flatten_court(c.get("LastInstanceCourt"))
        p = normalize_province(p, court)
        if p:
            reg[p] += 1
    if len(reg) >= 2:
        n = sum(reg.values())
        od = OrderedDict(reg.most_common())
        fig, ax = ct.single(figsize=(8.4, max(3, 0.42 * len(od) + 1.2)))
        ct.hbar_panel(ax, od, "", highlight_max=True)
        ax.set_title(f"全国样本判决书地域分布（N={n}）", loc="left",
                     fontsize=13, fontweight="bold", color=ct.NAVY, pad=10)
        ct.save_fig(fig, str(charts / "region_dist.png"))
        manifest["region_dist"] = {"path": str(charts / "region_dist.png"), "w": 520,
                                   "h": 60 + 24 * len(od),
                                   "caption": f"图　全国样本判决书地域分布（N={n}）"}
        print(f"region_dist：{n} 件判决书 / {len(od)} 省级单位")
    else:
        print("region_dist：地域不足 2 省，跳过")

    # ── issue_region：05 深度池 争点×地域 热力矩阵 ──
    enriched = load(rd / "05_enriched_cases.json")
    ir = defaultdict(Counter)
    for c in enriched:
        p = normalize_province(c.get("法院地") or (c.get("_norm") or {}).get("地域") or "",
                               c.get("审理法院") or (c.get("_norm") or {}).get("法院全称") or "")
        if not p:
            continue
        for q in (c.get("问题观点") or c.get("焦点立场") or {}):
            ir[q][p] += 1
    regions = {r for cnt in ir.values() for r in cnt}
    if ir and len(regions) >= 2:
        issues = sorted(ir, key=lambda q: -sum(ir[q].values()))
        order = [r for r, _ in Counter(
            {r: sum(ir[q].get(r, 0) for q in issues) for r in regions}).most_common()]
        matrix = [[ir[q].get(r, 0) for r in order] for q in issues]
        fig, ax = ct.single(figsize=(max(6, 0.9 * len(order) + 2.5),
                                     max(3.5, 0.45 * len(issues) + 1.5)))
        ct.issue_region_heatmap(ax, issues, order, matrix)
        ct.save_fig(fig, str(charts / "issue_region.png"))
        manifest["issue_region"] = {"path": str(charts / "issue_region.png"), "w": 540,
                                    "h": 80 + 26 * len(issues),
                                    "caption": f"图　各争点裁判观点的地域分布（深度样本 N={len(enriched)}·"
                                               f"个案观点分布，不构成地域倾向推断）"}
        print(f"issue_region：{len(issues)} 争点 × {len(order)} 省")
    else:
        print("issue_region：深度池地域不足 2 省，跳过（实案模式单一法院属正常）")

    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"manifest 已并入 → {mp}")


if __name__ == "__main__":
    main()
