#!/usr/bin/env python3
"""
tag_tiers.py —— 实案模式：判决书过滤 + 四顺位标注（就地补字段）
─────────────────────────────────────────────
用法：python3 scripts/general/tag_tiers.py <research_dir>
读 <research_dir>/{03_raw_cases.json, 顺位法院.json}，对 03 每条**追加**：
  · `_文书类型`：DocumentAttr 末级（判决书/裁定书/调解书…）
  · `_顺位`：命中 顺位法院.json 的最高（最权威）顺位号（2/3/4），未命中为 null
不删除任何记录（裁定书等仍留痕于 03，由筛查阶段决定是否入分析池）。
打印：判决书/裁定书分布、顺位命中分布、上海金融法院判决书数、年份跨度。

法律依据：法发〔2020〕24号第四条四顺位；专门法院（如上海金融法院）顺位③④高院重合属正常。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import flatten_court, flatten_leaf, derive_year  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/general/tag_tiers.py <research_dir>")
    rd = Path(sys.argv[1])
    raw_path = rd / "03_raw_cases.json"
    tiers_path = rd / "顺位法院.json"
    if not raw_path.exists():
        sys.exit(f"未找到 {raw_path}")
    cases = json.loads(raw_path.read_text(encoding="utf-8"))
    tiers = json.loads(tiers_path.read_text(encoding="utf-8")) if tiers_path.exists() else {}
    # 顺位号 → 法院名列表（顺位键形如 顺位2_最高法）
    tier_courts = {}
    for k, v in tiers.items():
        if isinstance(v, list):
            n = "".join(ch for ch in k if ch.isdigit())
            if n:
                tier_courts[int(n)] = v

    doc_dist, tier_dist, years = Counter(), Counter(), []
    sfc_judgments = 0
    for c in cases:
        doctype = flatten_leaf(c.get("DocumentAttr")) or "未标"
        c["_文书类型"] = doctype
        _, court = flatten_court(c.get("LastInstanceCourt"))
        hit = None
        for n in sorted(tier_courts):           # 取最高（数字最小）顺位
            if any(tc and (tc in court or court in tc) for tc in tier_courts[n]):
                hit = n
                break
        c["_顺位"] = hit
        doc_dist[doctype] += 1
        tier_dist[f"顺位{hit}" if hit else "顺位外"] += 1
        y = derive_year(c.get("LastInstanceDate") or "")
        if y:
            years.append(y)
        if "上海金融法院" in court and doctype == "判决书":
            sfc_judgments += 1

    raw_path.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已标注 {len(cases)} 条 → {raw_path}")
    print(f"  文书类型：{dict(doc_dist)}")
    print(f"  顺位分布：{dict(tier_dist)}")
    print(f"  上海金融法院·判决书：{sfc_judgments} 条")
    if years:
        print(f"  年份跨度：{min(years)}–{max(years)}（{dict(sorted(Counter(years).items()))}）")


if __name__ == "__main__":
    main()
