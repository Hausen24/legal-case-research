#!/usr/bin/env python3
"""
run_analytics_secmisrep.py —— 样本量自适应分析 + 出图（证券虚假陈述）
用法：python3 run_analytics_secmisrep.py <research_dir>
读 05_enriched_cases.json → 写 06_analytics.json；用 chart_theme 出图到 output/_charts/ +
manifest.json（供报告占位符插图）；用 stats_guard 决定定量档、地域分歧闸门、深度档。
"""
import sys, os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)                      # scripts/
sys.path[:0] = [SCRIPTS, os.path.join(SCRIPTS, "common")]
import chart_theme as ct
import stats_guard as sg
import divergence as dv
import pipeline_schema as ps

ISSUES = ['发行人责任','控股股东与董监高责任','中介机构责任','责任形态','虚假陈述认定','重大性',
          '预测性信息安全港','自愿性披露','损失计算','揭露日认定','交易因果关系','损失因果关系',
          '主观过错与勤勉尽责抗辩','诉讼时效与示范判决机制']
RESULTS = ["全部支持","部分支持","驳回","撤销改判"]

def od_desc(counter):
    return collections.OrderedDict(counter.most_common())

def main():
    rd = sys.argv[1]
    cases = json.load(open(os.path.join(rd, "05_enriched_cases.json"), encoding="utf-8"))
    out_dir = os.path.join(rd, "output"); charts_dir = os.path.join(out_dir, "_charts")
    os.makedirs(charts_dir, exist_ok=True)
    N = len(cases)

    # 编码契约校验（warn 模式；严格校验用 scripts/validate_pipeline.py）
    for m in ps.validate_05(cases).errors:
        print(f"⚠️ [契约] {m}")

    court = collections.Counter(c.get("审理法院") for c in cases)
    level = collections.Counter(c.get("审级") or "—" for c in cases)
    year  = collections.Counter(str(c.get("裁判年份")) for c in cases if c.get("裁判年份"))
    result= collections.Counter(c.get("裁判结果分类") for c in cases if c.get("裁判结果分类"))
    region= collections.Counter(c.get("法院地") for c in cases if c.get("法院地"))

    # 各问题倾向整体分布（报告主线数据）
    issue_dist = {}
    issue_freq = collections.Counter()
    for c in cases:
        for issue, info in (c.get("问题观点") or {}).items():
            issue_freq[issue] += 1
            issue_dist.setdefault(issue, collections.Counter())[info.get("倾向标签") or "—"] += 1
    issue_dist = {k: dict(v) for k, v in issue_dist.items()}

    # 独立事件数 → 深度档
    events = {(c.get("涉案上市公司"), c.get("虚假陈述事件")) for c in cases}
    depth = sg.depth_mode(len(events))

    # 地域分歧闸门
    gate = sg.divergence_gate(dict(region))

    # 系统风险扣除比例
    sysrisk = [c.get("系统风险扣除比例") for c in cases if c.get("系统风险扣除比例") not in (None, "")]

    analytics = {
        "N": N, "独立事件数": len(events),
        "分布": {"审理法院": dict(court), "审级": dict(level), "裁判年份": dict(sorted(year.items())),
                "裁判结果": dict(result), "法院地": dict(region)},
        "各问题倾向整体分布": issue_dist,
        "争点出现频次": dict(issue_freq),
        "系统风险扣除比例": sysrisk,
        "定量档": sg.stat_tier(N),
        "深度档": depth,
        "地域分歧": gate,                      # report=False 时报告不得设地域分歧小节
        # 分歧地图（一等产出）：同问题对立倾向并存清单 + 代表案对（法发〔2020〕24号第十一条情形）
        "分歧地图": dv.build_divergence(
            cases,
            get_positions=lambda c: {q: (i or {}).get("倾向标签")
                                     for q, i in (c.get("问题观点") or {}).items()},
            get_region=lambda c: c.get("法院地") or "",
            get_caseflag=lambda c: c.get("案号") or c.get("CaseFlag", ""),
        ),
    }
    json.dump(analytics, open(os.path.join(rd, "06_analytics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- 出图（chart_theme）----
    ct.apply_theme(); manifest = {}

    fig = ct.overview_2x2([
        ("h", od_desc(court), "审理法院", None),
        ("h", od_desc(level), "审级", None),
        ("v", collections.OrderedDict(sorted(year.items())), "裁判年份", None),
        ("h", collections.OrderedDict((k, result[k]) for k in RESULTS if result.get(k)), "裁判结果",
         {"color": ct.NAVY}),
    ])
    ct.save_fig(fig, os.path.join(charts_dir, "overview.png"))
    manifest["overview"] = {"path": os.path.join(charts_dir, "overview.png"), "w": 540, "h": 372,
                            "caption": f"图 1　样本概览：审理法院、审级、年份与裁判结果分布（N={N}）"}

    freq_desc = collections.OrderedDict(sorted(issue_freq.items(), key=lambda x: -x[1]))
    fig, ax = ct.single(figsize=(8.4, 5))
    ct.hbar_panel(ax, freq_desc, "各构成要件争点在核心判决中的出现频次", highlight_max=True)
    ax.set_title("各构成要件争点在核心判决中的出现频次", loc="left", fontsize=13,
                 fontweight="bold", color=ct.NAVY, pad=10)
    ct.save_fig(fig, os.path.join(charts_dir, "issue_freq.png"))
    manifest["issue_freq"] = {"path": os.path.join(charts_dir, "issue_freq.png"), "w": 540, "h": 321,
                              "caption": "图 2　各构成要件争点在核心判决中的出现频次"}

    years = sorted(year.keys())
    data = {r: [sum(1 for c in cases if str(c.get("裁判年份")) == y and c.get("裁判结果分类") == r)
                for y in years] for r in RESULTS}
    fig, ax = ct.single(figsize=(8.4, 4.2))
    ct.stacked_year(ax, years, data, "裁判结果年度演进")
    ct.save_fig(fig, os.path.join(charts_dir, "result_year.png"))
    manifest["result_year"] = {"path": os.path.join(charts_dir, "result_year.png"), "w": 520, "h": 260,
                               "caption": f"图 3　裁判结果年度演进（N={N}）"}

    json.dump(manifest, open(os.path.join(charts_dir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"分析完成：N={N}，独立事件={len(events)}，深度档={depth['mode']}，"
          f"地域分歧={'报告' if gate['report'] else '不报告(样本不足)'}，"
          f"分歧争点 {len(analytics['分歧地图'])} 个；图表与 manifest 已生成。")

if __name__ == "__main__":
    main()
