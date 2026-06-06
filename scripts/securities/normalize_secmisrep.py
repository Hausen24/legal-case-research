"""
normalize_secmisrep.py —— 拍平 MCP 字段 + 派生确定性字段（证券虚假陈述版）
─────────────────────────────────────────────
用法：python3 scripts/securities/normalize_secmisrep.py <research_dir>
输入：<research_dir>/05_enriched_cases.json （Claude Code 已做完按问题编码）
输出：就地补全每条记录的确定性派生字段——
  · 扁平中文键（下游 run_analytics_secmisrep / generate_excel_secmisrep 直接读取）：
    序号 / 案号 / 案件名称 / 审理法院 / 审级 / 裁判日期 / 法院地 / 裁判年份 / 北大法宝链接 / 涉案上市公司(兜底)
  · `_norm`（法院层级含"金融法院"档 / 文书类型 / 案由 / 案件等级 等附加派生，保留兼容）

只做规则可定的派生；按问题的判断性编码（基本案情/问题观点/裁判结果分类等）由 Claude Code 完成。
派生不覆盖 Claude 已写入的同名值（仅在缺失时补）。公共派生函数集中在 scripts/common/pkulaw_utils.py。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import (  # noqa: E402
    derive_court_level, derive_region, flatten_court, flatten_leaf,
    derive_year, derive_issuer, clean_url,
)


def normalize_one(case: dict, raw_idx: dict, seq: int) -> dict:
    raw = raw_idx.get(case.get("Gid"), {})

    def pick(key):
        v = case.get(key)
        if v not in (None, "", [], {}):
            return v
        return raw.get(key)

    def fill(cnkey, value):
        """仅在该中文键缺失时写入派生值，绝不覆盖 Claude 已编码内容。"""
        if case.get(cnkey) in (None, "", [], {}) and value not in (None, "", [], {}):
            case[cnkey] = value

    province, court = flatten_court(pick("LastInstanceCourt"))
    region = derive_region(court) or derive_region(province)

    # 扁平中文键（下游 v2 脚本直接读取）
    fill("序号", seq)
    fill("案号", pick("CaseFlag"))
    fill("案件名称", pick("Title"))
    fill("审理法院", court)
    fill("审级", pick("CaseClassName"))
    fill("裁判日期", pick("LastInstanceDate"))
    fill("法院地", region)
    fill("裁判年份", derive_year(pick("LastInstanceDate") or ""))
    fill("北大法宝链接", clean_url(pick("Url")))
    fill("涉案上市公司", derive_issuer(pick("Title") or ""))
    # 旧 schema 兜底：基本案情摘要 → 基本案情（v2 长表读"基本案情"）
    fill("基本案情", case.get("基本案情摘要"))

    # _norm（保留兼容：附加派生）
    case["_norm"] = {
        "法院全称": court,
        "法院层级": derive_court_level(court),
        "法院地": region,
        "地域": province,
        "裁判年份": derive_year(pick("LastInstanceDate") or ""),
        "文书类型": flatten_leaf(pick("DocumentAttr")),
        "案由": flatten_leaf(pick("Category")),
        "案件等级": flatten_leaf(pick("CaseGrade")) or "普通案例",
        "涉案公司": case.get("涉案上市公司") or derive_issuer(pick("Title") or ""),
    }
    return case


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/securities/normalize_secmisrep.py <research_dir>")
    rd = Path(sys.argv[1])
    path = rd / "05_enriched_cases.json"
    if not path.exists():
        sys.exit(f"未找到 {path}")

    raw_idx = {}
    raw_path = rd / "03_raw_cases.json"
    if raw_path.exists():
        for r in json.loads(raw_path.read_text(encoding="utf-8")):
            if r.get("Gid") and r["Gid"] not in raw_idx:
                raw_idx[r["Gid"]] = r

    cases = json.loads(path.read_text(encoding="utf-8"))
    for i, c in enumerate(cases, 1):
        normalize_one(c, raw_idx, i)
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已规范化 {len(cases)} 条核心判决，写回 {path}")


if __name__ == "__main__":
    main()
