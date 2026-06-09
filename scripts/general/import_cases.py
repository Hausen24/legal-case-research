#!/usr/bin/env python3
"""
import_cases.py —— 自带数据 → 管道契约（无北大法宝也能跑）
─────────────────────────────────────────────
把用户自备的"扁平表"判决数据（CSV / JSON）映射成与北大法宝 get_case_list 一致的记录结构，
写入 <research_dir>/03_raw_cases.json，从而无需法宝订阅即可接入本工作流的分析与产出链路。
字段契约见 examples/输入数据契约.md。

用法：
    python3 scripts/general/import_cases.py <research_dir> --json my_cases.json
    python3 scripts/general/import_cases.py <research_dir> --csv  my_cases.csv

设计：只做"结构搬运"，不臆造任何内容；缺列留空。反幻觉由 verify_report.py 在产出端兜底。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import derive_region  # noqa: E402

# 案件等级中文 → CaseGrade 码（仅"普通案例(07)"进分析池，其余进权威/典型案例附录）
GRADE_CODE = {
    "普通案例": "07", "公报案例": "05", "指导案例": "06", "典型案例": "08", "参考案例": "08",
}

REQUIRED = ["案件id", "案件名称", "案号", "审理法院", "链接"]


def to_record(row: dict) -> dict:
    """扁平行 → MCP 形态记录。"""
    def g(k):
        v = row.get(k, "")
        return v.strip() if isinstance(v, str) else (v or "")

    court = g("审理法院")
    region = g("地域") or derive_region(court)
    grade_cn = g("案件等级") or "普通案例"
    grade_code = GRADE_CODE.get(grade_cn, "07")

    rec = {
        "Gid": g("案件id"),
        "Title": g("案件名称"),
        "CaseFlag": g("案号"),
        "CaseGrade": {grade_code: grade_cn},
        # 键长度不同：短键→省级地域，长键→法院全称（flatten_court 依此拆分）
        "LastInstanceCourt": {"p": region, "court": court} if court else {},
        "Category": {"c": g("案由")} if g("案由") else {},
        "CaseClassName": g("审级"),
        "LastInstanceDate": g("裁判日期"),
        "DocumentAttr": {"01": "判决书"},
        "PlaintiffClaims": g("原告诉求"),
        "Ascertain": g("本院查明"),
        "DefenseViewpoint": g("抗辩意见"),
        "ControversialFocus": g("争议焦点"),
        "Identified": g("本院认为"),
        "RefereeBasis": g("裁判依据"),
        "RefereeResult": g("裁判结果"),
        "Url": g("链接"),
        "_query": ["自带数据"],
        "_source": "import_cases",
    }
    return rec


def load_rows(args) -> list:
    if "--json" in args:
        p = Path(args[args.index("--json") + 1])
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            sys.exit("JSON 顶层必须是数组（每个元素一条判决）。")
        return data
    if "--csv" in args:
        p = Path(args[args.index("--csv") + 1])
        with p.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    sys.exit("请用 --json <file> 或 --csv <file> 指定输入。")


def main():
    if len(sys.argv) < 4:
        sys.exit("用法：python3 scripts/general/import_cases.py <research_dir> "
                 "(--json file | --csv file)")
    rd = Path(sys.argv[1])
    rd.mkdir(parents=True, exist_ok=True)
    rows = load_rows(sys.argv[2:])

    records, seen, skipped = [], set(), []
    for i, row in enumerate(rows, 1):
        missing = [k for k in REQUIRED if not str(row.get(k, "")).strip()]
        if missing:
            skipped.append((i, missing))
            continue
        rec = to_record(row)
        if rec["Gid"] in seen:
            continue
        seen.add(rec["Gid"])
        records.append(rec)

    out = rd / "03_raw_cases.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    grade = {}
    for r in records:
        k = next(iter(r["CaseGrade"]), "")
        grade[k] = grade.get(k, 0) + 1
    print(f"已导入 {len(records)} 条 → {out}")
    print(f"  CaseGrade 分布: {grade}（仅 07 普通案例进分析池）")
    if skipped:
        print(f"  ⚠️ 跳过 {len(skipped)} 行（缺必填列）：")
        for i, miss in skipped[:10]:
            print(f"     第 {i} 行缺 {miss}")
    print("  下一步：按对应 SKILL 做筛查→编码(05)→ normalize/run_analytics/generate_excel → 报告。")


if __name__ == "__main__":
    main()
