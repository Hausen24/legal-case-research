"""
summarize_raw.py —— 从 03_raw_cases.json 产出检查点2素材（证券虚假陈述专题）
─────────────────────────────────────────────
读 03，做：四家法院后过滤 + 文书类型分类 + 时间锚标注 + 涉案公司提取（标题脱敏时回退正文）
+ 按"涉案公司"分组草稿。仅输出精简文本，便于在对话里呈现给用户校核，不改写 03。

用法：python3 scripts/securities/summarize_raw.py <research_dir>
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import flatten_court, flatten_leaf, derive_year  # noqa: E402

TARGET = ["北京金融法院", "上海金融法院", "北京市高级人民法院", "上海市高级人民法院"]

# 时间锚（成立/受理起点）
ANCHOR = {
    "上海金融法院": "2018-08", "上海市高级人民法院": "2018-08",
    "北京金融法院": "2021-03", "北京市高级人民法院": "2021-03",
}

COMPANY_RE = re.compile(
    r"([一-龥（）()A-Za-z0-9·]{2,40}?"
    r"(?:股份有限公司|有限责任公司|有限公司|集团股份有限公司))"
)

GENERIC = ("某某公司", "某公司", "某某有限公司", "某某股份有限公司", "某上市公司", "A公司", "某科技公司")

# 检索用过的公司名查询词（用于对脱敏判决从 _query 反推涉案公司）
COMPANY_WORDS = {
    "方正科技", "中毅达", "中安科", "中安消", "乐视网", "艾格拉斯", "福石控股", "华谊嘉信",
    "京西文化", "数知科技", "神州长城", "数码视讯", "泽达易盛", "紫晶存储", "祥源文化",
    "蓝山科技", "华龙证券", "中兴天恒", "博天环境", "同仁堂", "广东榕泰", "北大医药",
    "飞乐音响", "华信国际", "上海华信", "大智慧", "招商证券", "瑞华会计师事务所",
    "保千里", "绿地控股", "鲜言", "匹凸匹", "普天科技",
}


def extract_company(rec):
    """从 Title 抽公司；脱敏时回退正文；再退而用 _query 命中的公司名查询词反推。"""
    for field in ("Title", "TrialAfter", "Ascertain", "PlaintiffClaims", "Identified", "DefenseViewpoint"):
        txt = rec.get(field) or ""
        for cand in COMPANY_RE.findall(txt):
            if any(g in cand for g in ("会计师事务所", "律师事务所", "证券", "评估")):
                continue  # 跳过中介机构，优先发行人
            if cand in GENERIC:
                continue
            return cand
    # 脱敏：从 _query 反推（命中本案的公司名查询词）
    for q in rec.get("_query", []):
        if q in COMPANY_WORDS:
            return f"{q}（据检索词）"
    cands = COMPANY_RE.findall(rec.get("Title") or "")
    return cands[-1] if cands else "（未识别/脱敏）"


def date_to_anchor_key(date_str):
    """YYYY.MM → YYYY-MM 比较用。"""
    if not date_str:
        return ""
    m = re.match(r"(\d{4})[.\-](\d{1,2})", str(date_str))
    if not m:
        y = derive_year(date_str)
        return f"{y}-01" if y else ""
    return f"{m.group(1)}-{int(m.group(2)):02d}"


def main():
    rd = Path(sys.argv[1])
    records = json.loads((rd / "03_raw_cases.json").read_text(encoding="utf-8"))

    rows = []
    for r in records:
        _, court = flatten_court(r.get("LastInstanceCourt"))
        if not any(c in court for c in TARGET):
            continue
        attr = flatten_leaf(r.get("DocumentAttr"))
        court_key = next((c for c in TARGET if c in court), court)
        anchor = ANCHOR.get(court_key, "")
        dkey = date_to_anchor_key(r.get("LastInstanceDate"))
        in_window = (not anchor) or (dkey >= anchor) if dkey else None
        rows.append({
            "court": court_key, "attr": attr,
            "step": flatten_leaf(r.get("TrialStep")),
            "date": r.get("LastInstanceDate") or "",
            "flag": r.get("CaseFlag") or "",
            "title": r.get("Title") or "",
            "company": extract_company(r),
            "gid": r.get("Gid"),
            "grade": flatten_leaf(r.get("CaseGrade")),
            "in_window": in_window,
            "has_reason": bool((r.get("Identified") or "").strip()) and bool((r.get("RefereeResult") or "").strip()),
            "queries": r.get("_query", []),
        })

    total = len(rows)
    judg = [x for x in rows if x["attr"] == "判决书"]
    ruling = [x for x in rows if x["attr"] == "裁定书"]

    print(f"03 总记录 {len(records)} 条；四家法院命中 {total} 条")
    print(f"  判决书 {len(judg)} | 裁定书 {len(ruling)} | 其他 {total-len(judg)-len(ruling)}")
    print(f"\n按法院×文书类型：")
    for c in TARGET:
        cj = sum(1 for x in judg if x['court'] == c)
        cr = sum(1 for x in ruling if x['court'] == c)
        print(f"  {c}: 判决书 {cj}, 裁定书 {cr}")

    # 时间锚外的判决书（成立前/受理前，应排除）
    out_window = [x for x in judg if x["in_window"] is False]
    if out_window:
        print(f"\n⚠ 时间锚外判决书（成立/受理前，建议排除）{len(out_window)} 条：")
        for x in sorted(out_window, key=lambda x: x["date"]):
            print(f"  [{x['court']}|{x['date']}] {x['flag']} | {x['title'][:40]}")

    print(f"\n=== 窗口内判决书按涉案公司分组（核心判决候选）===")
    groups = {}
    for x in judg:
        if x["in_window"] is False:
            continue
        groups.setdefault(x["company"], []).append(x)
    for comp, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"\n● {comp}（{len(items)} 份判决书）")
        for x in sorted(items, key=lambda x: (x["court"], x["date"])):
            star = "★说理完整" if x["has_reason"] else "·"
            print(f"    [{x['court']}|{x['step']}|{x['date']}] {x['flag']} {star}")
            print(f"      {x['title'][:55]}")


if __name__ == "__main__":
    main()
