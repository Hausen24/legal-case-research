"""
run_analytics.py —— 六维统计分析
─────────────────────────────────────────────
用法：python3 scripts/run_analytics.py <research_dir>
输入：<research_dir>/05_enriched_cases.json （已规范化 + 已编码）
输出：<research_dir>/06_analytics.json

脚本计算"可计算"的统计；法律解读由 Claude Code 基于本结果在报告中完成。
每条 enriched case 约定包含（由 Claude Code 编码写入）：
  _norm: {法院层级, 地域, 裁判年份, 案由, 案件等级}
  编码字段: 裁判结果分类, 判赔金额, 维权开支, 相关度
  焦点立场: { "<焦点名>": {"立场": "支持原告|支持被告|未评述", "理由": "..."} }
  抗辩: [ {"理由": "技术中立", "是否被采纳": true/false}, ... ]
  平台类型: 可选，若已编码
"""

import json
import sys
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def crosstab(cases, row_key_fn, col_key_fn):
    """通用列联表：返回 {row: {col: count}}"""
    table = defaultdict(lambda: defaultdict(int))
    for c in cases:
        r = row_key_fn(c)
        col = col_key_fn(c)
        if r is None or col is None:
            continue
        table[r][col] += 1
    return {r: dict(cols) for r, cols in table.items()}


def safe_norm(c, key):
    return (c.get("_norm") or {}).get(key, "")


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/run_analytics.py <research_dir>")
    research_dir = Path(sys.argv[1])
    path = research_dir / "05_enriched_cases.json"
    if not path.exists():
        sys.exit(f"未找到 {path}")
    cases = json.loads(path.read_text(encoding="utf-8"))
    n = len(cases)

    analytics = {"样本量": n}

    # ── 描述性分布 ──
    analytics["分布"] = {
        "法院层级": dict(Counter(safe_norm(c, "法院层级") for c in cases)),
        "地域": dict(Counter(safe_norm(c, "地域") for c in cases)),
        "审级": dict(Counter(c.get("CaseClassName", "") for c in cases)),
        "裁判年份": dict(Counter(safe_norm(c, "裁判年份") for c in cases)),
        "案由": dict(Counter(safe_norm(c, "案由") for c in cases)),
        "裁判结果分类": dict(Counter(c.get("裁判结果分类", "") for c in cases)),
    }

    # ── 维度一：交叉关联 ──
    analytics["维度一_交叉关联"] = {
        "法院层级×裁判结果": crosstab(
            cases,
            lambda c: safe_norm(c, "法院层级"),
            lambda c: c.get("裁判结果分类"),
        ),
        "审级×裁判结果": crosstab(
            cases,
            lambda c: c.get("CaseClassName"),
            lambda c: c.get("裁判结果分类"),
        ),
        "年份×裁判结果": crosstab(
            cases,
            lambda c: safe_norm(c, "裁判年份"),
            lambda c: c.get("裁判结果分类"),
        ),
    }

    # ── 维度二：抗辩有效性 ──
    defense_stats = defaultdict(lambda: {"提出": 0, "采纳": 0})
    for c in cases:
        for d in c.get("抗辩", []):
            name = d.get("理由", "未命名")
            defense_stats[name]["提出"] += 1
            if d.get("是否被采纳"):
                defense_stats[name]["采纳"] += 1
    for name, s in defense_stats.items():
        s["成功率"] = round(s["采纳"] / s["提出"], 3) if s["提出"] else None
    analytics["维度二_抗辩有效性"] = dict(defense_stats)

    # ── 维度三：判赔金额 ──
    amounts = [c.get("判赔金额") for c in cases if isinstance(c.get("判赔金额"), (int, float))]
    if amounts:
        analytics["维度三_判赔金额"] = {
            "有金额案件数": len(amounts),
            "最低": min(amounts),
            "最高": max(amounts),
            "中位数": statistics.median(amounts),
            "平均": round(statistics.mean(amounts), 2),
        }
    else:
        analytics["维度三_判赔金额"] = {"说明": "无可解析的判赔金额数据"}

    # ── 维度四：演进拐点（按年份的裁判结果倾向序列）──
    year_result = defaultdict(lambda: Counter())
    for c in cases:
        y = safe_norm(c, "裁判年份")
        if y:
            year_result[y][c.get("裁判结果分类", "未知")] += 1
    analytics["维度四_年度趋势"] = {
        y: dict(cnt) for y, cnt in sorted(year_result.items())
    }

    # ── 维度五：各争议焦点的立场分布（分歧地图原料）──
    focus_positions = defaultdict(lambda: Counter())
    for c in cases:
        for focus, info in (c.get("焦点立场") or {}).items():
            focus_positions[focus][info.get("立场", "未评述")] += 1
    analytics["维度五_焦点立场分布"] = {
        f: dict(cnt) for f, cnt in focus_positions.items()
    }

    # 维度六（要素-结果影响度）需法律解读，留给 Claude Code 基于上述结果撰写。
    analytics["维度六_说明"] = "要素-结果影响度排序由报告撰写时综合上述维度做法律解读得出。"

    out = research_dir / "06_analytics.json"
    out.write_text(json.dumps(analytics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"六维统计完成，写入 {out}")


if __name__ == "__main__":
    main()
