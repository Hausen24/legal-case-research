#!/usr/bin/env python3
"""
fold_group_cases.py —— 集团案自动检测阀门 + 平行判决折叠（两模式通用）
─────────────────────────────────────────────
用法：
    python3 scripts/general/fold_group_cases.py <research_dir> --detect   # 只检测，不改文件
    python3 scripts/general/fold_group_cases.py <research_dir>            # 检测+折叠，落盘 04

**阀门规则（项目定版）**：案件形态（散案/集团案）不由用户指定，由本阀门自动判断——
检索后若发现「同一被告 × 同一法院」存在成串相似判决（组规模 ≥ GROUP_TRIGGER，默认 4），
即判定存在集团性诉讼形态，启动折叠：每串相似判决仅保留说理最完整的**核心判决**，
其余作平行判决留痕（_track=parallel，记所属核心案）。检测结果在检查点 2 呈报用户校核。

分组三级键（宁可少折、不可误折）：
  ① 标题公司名（derive_issuer，排除"某"匿名与伪公司名黑名单）
  ② 正文公司名 + 法院（body_issuer：Ascertain/Identified 高频公司名）
  ③ 说理指纹（前 120 字去数字/空白归一——匿名化判决的兜底）

同时做学理模式基础筛查（仅留实体判决书；案由不符/程序裁定/汇编条目剔除留痕），
并给核心判决补规则化 `_结果分类_规则`（深度编码时人工复核覆盖）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import (  # noqa: E402
    flatten_leaf, flatten_court, normalize_province, derive_year, derive_issuer, COMPANY_RE,
)

GROUP_TRIGGER = 4   # 阀门：同被告×同法院组规模达到此值 → 判定集团案形态

# 伪公司名黑名单（法条/机构名易被 COMPANY_RE 误抓）
BLACK = ("中华人民共和国", "国务院", "证券交易所", "社会保险", "人民法院", "证监",
         "事务所", "律师", "证券登记", "结算", "监督管理")


def body_issuer(c):
    text = ((c.get("Ascertain") or "")[:600] + (c.get("Identified") or "")[:600])
    cands = [m for m in COMPANY_RE.findall(text)
             if not any(b in m for b in BLACK) and len(m) >= 5]
    return Counter(cands).most_common(1)[0][0] if cands else ""


def fingerprint(c):
    base = (c.get("Identified") or c.get("Ascertain") or "")[:120]
    return re.sub(r"[一二三四五六七八九十百0-9\s]", "", base)


def classify(c):
    r = (c.get("RefereeResult") or "")
    if re.search(r"驳回.{0,6}(全部)?诉讼请求", r):
        return "驳回"
    if "撤销" in r and ("改判" in r or "原判" in r or "一审" in r):
        return "撤销改判"
    if "驳回上诉" in r and "维持" in r:
        return "维持原判"
    if re.search(r"赔偿|支付", r):
        return "部分支持"
    return "其他/未明"


def screen(raw, cause_kw):
    """基础筛查：仅留实体判决书（案由含主题词或标题含）。"""
    kept, dropped = [], Counter()
    for c in raw:
        doc = flatten_leaf(c.get("DocumentAttr")) or ""
        cause = flatten_leaf(c.get("Category")) or ""
        title = c.get("Title") or ""
        if doc != "判决书":
            dropped["非判决书(程序裁定等)"] += 1; continue
        if cause_kw and cause_kw not in cause and cause_kw not in title:
            dropped["案由不符"] += 1; continue
        if any(h in title for h in ("发布", "十大", "典型案例", "汇编")):
            dropped["汇编报道条目"] += 1; continue
        if len((c.get("Identified") or "")) < 150 and len((c.get("Ascertain") or "")) < 150:
            dropped["正文过短"] += 1; continue
        kept.append(c)
    return kept, dropped


def group(kept):
    groups = defaultdict(list)
    for c in kept:
        issuer = body_issuer(c)
        t_issuer = derive_issuer(c.get("Title") or "")
        if t_issuer and "某" not in t_issuer and not any(b in t_issuer for b in BLACK):
            issuer = issuer or t_issuer
        _, court = flatten_court(c.get("LastInstanceCourt"))
        key = (issuer, court) if issuer else ("FP", fingerprint(c))
        groups[key].append(c)
    return groups


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/general/fold_group_cases.py <research_dir> "
                 "[--detect] [--cause <案由关键词>]")
    rd = Path(sys.argv[1])
    detect_only = "--detect" in sys.argv
    cause_kw = ""
    if "--cause" in sys.argv:
        cause_kw = sys.argv[sys.argv.index("--cause") + 1]

    raw = json.loads((rd / "03_raw_cases.json").read_text(encoding="utf-8"))
    kept, dropped = screen(raw, cause_kw)
    groups = group(kept)

    big = sorted(((k, len(v)) for k, v in groups.items() if len(v) >= GROUP_TRIGGER),
                 key=lambda x: -x[1])
    is_group_case = bool(big)
    print(f"筛查：保留实体判决 {len(kept)} 件（剔除 {dict(dropped)}）")
    print(f"阀门检测：{'⚠️ 检出集团性诉讼形态' if is_group_case else '散案形态'}"
          f"（组规模≥{GROUP_TRIGGER} 的事件组 {len(big)} 个）")
    for k, n in big[:10]:
        name = k[0] if k[0] != "FP" else "(匿名·说理指纹组)"
        print(f"  [{n:>2} 案成串] {name[:28]}")

    if detect_only:
        return
    if not is_group_case:
        print("未触发折叠（散案按 Gid 去重即可）；如仍需折叠请人工确认后去掉 --detect 重跑。")

    core, parallel = [], []
    for key, cs in groups.items():
        cs.sort(key=lambda x: -len(x.get("Identified") or ""))
        head = dict(cs[0])
        head["_track"] = "core"
        head["_组规模"] = len(cs)
        head["_涉案公司"] = key[0] if key[0] != "FP" else ""
        head["_结果分类_规则"] = classify(head)
        core.append(head)
        for p in cs[1:]:
            parallel.append({"_track": "parallel", "Gid": p.get("Gid"), "Title": p.get("Title"),
                             "CaseFlag": p.get("CaseFlag"), "Url": p.get("Url"),
                             "所属核心案": head.get("CaseFlag")})

    core.sort(key=lambda x: -len(x.get("Identified") or ""))
    (rd / "04_screened_cases.json").write_text(
        json.dumps(core + parallel, ensure_ascii=False, indent=1), encoding="utf-8")

    region, era = Counter(), Counter()
    for c in core:
        p, court = flatten_court(c.get("LastInstanceCourt"))
        p = normalize_province(p, court)
        if p:
            region[p] += 1
        y = derive_year(c.get("LastInstanceDate") or "")
        if y:
            era["新规(2022+)" if y >= "2022" else "旧规"] += 1
    print(f"折叠落盘 04：核心判决 {len(core)} 件 / 平行留痕 {len(parallel)} 件")
    print(f"  核心池地域: {dict(region.most_common(10))}")
    print(f"  新旧规: {dict(era)}")
    print("▸ 阀门检测与折叠结果须在检查点 2 呈报用户校核分组。")


if __name__ == "__main__":
    main()
