#!/usr/bin/env python3
"""
apply_coding.py —— 判断性编码落盘标准化（收编"每次研究手写脚本"的手工环节）
─────────────────────────────────────────────
用法：python3 scripts/general/apply_coding.py <research_dir> <coding.json>

AI 的判断性编码以**纯 JSON** 产出（无需再为每次研究手写 _build_05.py），本脚本负责：
  1. 按 CaseFlag（或 Gid）在 04（core 优先）/03 中找到原始记录；
  2. 把编码字段**追加**到原始记录上（字段保全铁律：原始 MCP 字段只增不改）；
  3. 与已有 05 按 Gid 合并（同案编码字段覆盖更新），写回 05_enriched_cases.json。

coding.json 两种形态皆可：
  [{"CaseFlag": "(2025)沪74民初33号", "裁判结果分类": "部分支持", "问题观点": {...}, ...}, ...]
  {"(2025)沪74民初33号": {"裁判结果分类": ...}, ...}

落盘后照常：normalize → spot_check_coding（抽检复核）→ validate_pipeline → 分析出图。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import normalize_caseno  # noqa: E402

PROTECTED = ("Gid", "Title", "CaseFlag", "Ascertain", "Identified", "RefereeBasis",
             "RefereeResult", "DefenseViewpoint", "ControversialFocus", "Category",
             "LastInstanceCourt", "CaseGrade", "Url", "LastInstanceDate",
             "CaseClassName", "DocumentAttr", "PlaintiffClaims", "TrialAfter")


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def flat(data):
    if isinstance(data, dict):
        out = []
        for v in data.values():
            if isinstance(v, list):
                out.extend(v)
        return out
    return data if isinstance(data, list) else []


def main():
    if len(sys.argv) < 3:
        sys.exit("用法：python3 scripts/general/apply_coding.py <research_dir> <coding.json>")
    rd = Path(sys.argv[1])
    coding_raw = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    coding = ([{"CaseFlag": k, **v} for k, v in coding_raw.items()]
              if isinstance(coding_raw, dict) else coding_raw)

    # 原始记录索引：04 core 优先（含折叠标注），回退 03
    pool = {}
    for r in flat(load(rd / "03_raw_cases.json")):
        if isinstance(r, dict) and r.get("Gid"):
            pool[r["Gid"]] = r
    for r in flat(load(rd / "04_screened_cases.json")):
        if isinstance(r, dict) and r.get("Gid") and r.get("_track") != "parallel":
            pool[r["Gid"]] = r
    by_flag = {normalize_caseno(r.get("CaseFlag") or ""): g for g, r in pool.items()
               if r.get("CaseFlag")}

    enriched = {e.get("Gid"): e for e in load(rd / "05_enriched_cases.json")
                if isinstance(e, dict) and e.get("Gid")}

    applied, missed, refused = 0, [], []
    for item in coding:
        gid = item.get("Gid") or by_flag.get(normalize_caseno(item.get("CaseFlag") or ""))
        if not gid or gid not in pool:
            missed.append(item.get("CaseFlag") or item.get("Gid") or "?")
            continue
        rec = enriched.get(gid) or dict(pool[gid])
        for k, v in item.items():
            if k in ("Gid", "CaseFlag"):
                continue
            if k in PROTECTED:
                refused.append(f"{item.get('CaseFlag','?')}.{k}")
                continue
            rec[k] = v
        rec.setdefault("相关度", "高")
        enriched[gid] = rec
        applied += 1

    out = rd / "05_enriched_cases.json"
    out.write_text(json.dumps(list(enriched.values()), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"已应用编码 {applied} 件 → {out}（05 现共 {len(enriched)} 件）")
    if missed:
        print(f"⚠️ 未在 03/04 中匹配到（检查案号）：{missed}")
    if refused:
        print(f"⚠️ 拒绝改写受保护的 MCP 原始字段（字段保全铁律）：{refused[:6]}")
    print("▸ 下一步：normalize → spot_check_coding（抽检复核）→ validate_pipeline。")


if __name__ == "__main__":
    main()
