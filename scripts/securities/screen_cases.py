"""
screen_cases.py —— 核心判决识别 + 去重 + 分池（证券虚假陈述专题，2.2/2.3 步）
─────────────────────────────────────────────
读 03_raw_cases.json → 四家法院 + 时间锚过滤 → 按"涉案公司/事件"分组 → 组内选核心判决
→ 写 04_screened_cases.json（每条 _track: core/parallel/typical/procedural）+ 打印检查点2分组报告。

核心判决判定（组内优先级）：示范判决 > 二审/再审 > 说理完整一审。
平行判决：同组其他投资者判决书（多含"本案事实与生效判决一致"），仅留痕。
程序裁定：管辖/合并/撤诉等裁定书，不入分析。
典型案例：CaseGrade 非 07 或正文空（述评/公报），入典型案例池。

启发式必有误差，检查点2交用户校核。
用法：python3 scripts/securities/screen_cases.py <research_dir>
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))
from pkulaw_utils import flatten_court, flatten_leaf, clean_url  # noqa: E402

TARGET = ["北京金融法院", "上海金融法院", "北京市高级人民法院", "上海市高级人民法院"]
ANCHOR = {"上海金融法院": "2018-08", "上海市高级人民法院": "2018-08",
          "北京金融法院": "2021-03", "北京市高级人民法院": "2021-03"}

# 已联网/正文核实的身份映射：CaseFlag → (涉案公司, 虚假陈述事件标签)
IDENTITY = {
    "(2019)沪74民初2509号": ("中安科股份有限公司", "中安消/中安科重大资产重组虚假陈述（招商证券、瑞华）"),
    "（2020）沪民终666号": ("中安科股份有限公司", "中安消/中安科重大资产重组虚假陈述"),
    "(2020)沪民终666号": ("中安科股份有限公司", "中安消/中安科重大资产重组虚假陈述"),
    "（2021）沪民终870号": ("中安科股份有限公司", "中安科虚假陈述·董事责任认定（2022典型案例之四）"),
    "(2018)沪74民初330号": ("方正科技集团股份有限公司", "方正科技虚假陈述"),
    "(2019)沪民终263号": ("方正科技集团股份有限公司", "方正科技虚假陈述"),
    "（2020）沪民终550号": ("上海中毅达股份有限公司", "中毅达虚假陈述"),
    "(2020)沪民终550号": ("上海中毅达股份有限公司", "中毅达虚假陈述"),
    "(2023)沪74民初1621号": ("上海飞乐音响股份有限公司", "飞乐音响虚增营收利润（揭露日2018.4.13·首例普通代表人诉讼示范案2402号后续）"),
    "(2024)京74民初10号": ("博天环境集团股份有限公司", "博天环境2017-2021年报虚假记载（自我更正/退市）"),
    "(2024)京74民初26号": ("（北京）某建筑设计股份有限公司", "建筑设计公司年报虚假记载（2023退市，待确认全称）"),
    "（2022）沪74民初2814号": ("某软件/科技公司", "预测性信息重大差异（2023典型案例之四·安全港）"),
    "(2023)沪民终699号": ("新三板做市标的公司", "全国首例新三板做市交易证券虚假陈述"),
}


def norm_flag(f):
    return (f or "").replace("（", "(").replace("）", ")").strip()


def signature(rec):
    """(揭露日, 基准价) 指纹，用于脱敏平行判决聚类。"""
    txt = (rec.get("Ascertain") or "") + (rec.get("Identified") or "")
    d = re.search(r"揭露日为?(\d{4}年\d{1,2}月\d{1,2}日)", txt)
    b = re.search(r"基准价为?([\d.]+)元", txt)
    return (d.group(1) if d else "", b.group(1) if b else "")


def case_prefix(flag):
    """去掉末尾流水号的案号前缀，如 (2025)沪74民初182号 → (2025)沪74民初。"""
    f = norm_flag(flag)
    m = re.match(r"(.*[^\d])(\d+)号$", f)
    return m.group(1) if m else f


def main():
    rd = Path(sys.argv[1])
    records = json.loads((rd / "03_raw_cases.json").read_text(encoding="utf-8"))

    pool = []       # 四家法院窗口内
    excluded = []   # 时间锚外
    for r in records:
        _, court = flatten_court(r.get("LastInstanceCourt"))
        court_key = next((c for c in TARGET if c in court), None)
        if not court_key:
            continue
        date = r.get("LastInstanceDate") or ""
        m = re.match(r"(\d{4})[.\-](\d{1,2})", date)
        dkey = f"{m.group(1)}-{int(m.group(2)):02d}" if m else ""
        attr = flatten_leaf(r.get("DocumentAttr"))
        grade = flatten_leaf(r.get("CaseGrade"))
        has_text = bool((r.get("Identified") or "").strip())
        rec = {**r, "_court": court_key, "_attr": attr, "_step": flatten_leaf(r.get("TrialStep")),
               "_grade": grade, "_date": date, "_dkey": dkey, "_has_text": has_text,
               "_url": clean_url(r.get("Url"))}
        if dkey and dkey < ANCHOR[court_key]:
            rec["_track"] = "excluded_time"
            excluded.append(rec)
        else:
            pool.append(rec)

    # 分池
    typical, procedural, judgments = [], [], []
    for r in pool:
        if "07" not in str(r.get("CaseGrade")) or not r["_has_text"]:
            if r["_attr"] != "判决书" and not r["_has_text"]:
                pass
        if r["_attr"] == "判决书" and r["_has_text"]:
            judgments.append(r)
        elif r["_attr"] == "判决书" and not r["_has_text"]:
            r["_track"] = "typical"; typical.append(r)   # 判决书但正文空（公报/述评）
        else:
            r["_track"] = "procedural"; procedural.append(r)  # 裁定书等

    # 判决书分组
    def group_key(r):
        f = norm_flag(r.get("CaseFlag"))
        if f in IDENTITY:
            return IDENTITY[f][0]
        sig = signature(r)
        if sig[0] or sig[1]:
            return f"指纹:{sig[0]}|{sig[1]}"
        # 同案号前缀 + 同裁判日 → 同批平行判决
        return f"批次:{case_prefix(f)}@{r.get('_date','')}"

    groups = {}
    for r in judgments:
        groups.setdefault(group_key(r), []).append(r)

    # 组内选核心
    def core_score(r):
        s = 0
        blob = (r.get("Ascertain") or "") + (r.get("TrialAfter") or "") + (r.get("Identified") or "")
        if "示范" in blob or "示范" in (r.get("Title") or ""):
            s += 100
        if r["_step"] == "二审":
            s += 50
        if r["_step"] == "再审":
            s += 30
        s += len((r.get("Identified") or "")) // 200  # 说理长度
        s += len((r.get("RefereeBasis") or "")) // 100
        return s

    core, parallel = [], []
    for gk, items in groups.items():
        items_sorted = sorted(items, key=core_score, reverse=True)
        chosen = items_sorted[0]
        comp, event = IDENTITY.get(norm_flag(chosen.get("CaseFlag")), (None, None))
        for i, r in enumerate(items_sorted):
            f = norm_flag(r.get("CaseFlag"))
            r["涉案上市公司"] = (IDENTITY.get(f, (None,))[0] or comp or "")
            r["虚假陈述事件"] = (IDENTITY.get(f, (None, None))[1] or event or "")
            r["_group"] = gk
            if i == 0:
                blob = (r.get("Ascertain") or "") + (r.get("Title") or "")
                r["核心判决类型"] = "示范判决" if "示范" in blob else ("代表人诉讼" if "代表人" in blob else "普通核心")
                r["_track"] = "core"; core.append(r)
            else:
                r["_track"] = "parallel"; parallel.append(r)

    # 写 04（core 全字段 + 标注；parallel/typical/procedural 留痕精简但保字段）
    out = core + parallel + typical + procedural + excluded
    (rd / "04_screened_cases.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # 报告
    print(f"四家法院窗口内 {len(pool)} 条；时间锚外排除 {len(excluded)} 条")
    print(f"  核心判决 {len(core)} | 平行判决 {len(parallel)} | 典型/述评(正文空判决书) {len(typical)} | 程序裁定 {len(procedural)}")
    print(f"\n=== 核心判决分组（{len(groups)} 组，检查点2请校核）===")
    for gk, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        chosen = sorted(items, key=core_score, reverse=True)[0]
        comp = chosen.get("涉案上市公司") or gk
        n_par = len(items) - 1
        print(f"\n● [{comp}] 组内{len(items)}份判决书 → 核心1 + 平行{n_par}")
        print(f"   核心: [{chosen['_court']}|{chosen['_step']}|{chosen['_date']}] {chosen.get('CaseFlag')} ({chosen.get('核心判决类型')})")
        if n_par:
            flags = [norm_flag(x.get('CaseFlag')) for x in items if x is not chosen]
            print(f"   平行: {', '.join(flags[:8])}{' …' if len(flags)>8 else ''}")


if __name__ == "__main__":
    main()
