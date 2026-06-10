"""
court_hierarchy.py —— 实案模式四顺位法院解析（法发〔2020〕24号第四条）
─────────────────────────────────────────────
输入核心法院（待决案件审理法院），输出四顺位检索范围的法院清单提议：
  顺位① 最高人民法院发布的指导性案例（查 data/guiding_cases/ 本地数据集）
  顺位② 最高人民法院发布的典型案例及裁判生效的案件
  顺位③ 本省（自治区、直辖市）高级人民法院发布的参考性案例及裁判生效的案件
  顺位④ 上一级人民法院及本院裁判生效的案件

直辖市多中院映射查 data/court_hierarchy.json（初值，含"待核"标注）；
非直辖市按通用规则推断（区/县基层 → 设区的市中院 → 省高院）。
**本模块输出的是"提议"——SKILL 要求在检查点 1 把顺位法院清单呈用户确认后才开搜。**
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent.parent / "data" / "court_hierarchy.json"

MUNICIPALITIES = ("北京市", "上海市", "天津市", "重庆市")


def _load():
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}


# 省级行政区短名 → 规范全称（用于"XX金融法院/互联网法院"等不含"省/市"的专门法院）
_PROVINCE_ALIAS = {
    "北京": "北京市", "上海": "上海市", "天津": "天津市", "重庆": "重庆市",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
}
_PROVINCES = ["河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建",
              "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州",
              "云南", "陕西", "甘肃", "青海"]


def _province_of(court: str) -> str:
    """从法院全称取省级行政区（含直辖市）。先按"省/市/自治区"正式后缀，
    再对专门法院（如"上海金融法院"无"市"字）按短名前缀兜底。"""
    if not court:
        return ""
    m = re.match(r"^(北京市|上海市|天津市|重庆市|"
                 r"[^省]{2,8}省|[^区]{2,12}(?:壮族|回族|维吾尔)?自治区)", court)
    if m:
        return m.group(1)
    for short, full in _PROVINCE_ALIAS.items():        # 直辖市/自治区短名前缀
        if court.startswith(short):
            return full
    for p in _PROVINCES:                                # 普通省短名前缀
        if court.startswith(p):
            return p + "省"
    return ""


def resolve_tiers(core_court: str) -> dict:
    """核心法院 → 四顺位提议。返回含 needs_confirmation 的 dict。"""
    data = _load()
    province = _province_of(core_court)
    notes = []
    upper = None

    # 专门法院特例
    special = (data.get("专门法院上诉") or {})
    if core_court in special:
        upper = special[core_court]
        notes.append(f"专门法院上诉关系：{core_court} → {upper}")

    is_basic = bool(re.search(r"(区|县|旗|县级市)?人民法院$", core_court)) and \
        "中级" not in core_court and "高级" not in core_court and "最高" not in core_court
    is_intermediate = "中级人民法院" in core_court or core_court.endswith("金融法院") \
        or "互联网法院" in core_court or "知识产权法院" in core_court

    if upper is None and is_basic and province in MUNICIPALITIES:
        # 直辖市：查多中院辖区表
        table = (data.get("直辖市中院辖区") or {}).get(province) or {}
        district = re.search(r"市([^市]{2,8}?(?:区|县))人民法院", core_court)
        d = district.group(1) if district else ""
        for mid, districts in table.items():
            if mid.startswith("_"):
                continue
            if any(d and d in x for x in districts):
                upper = mid
                if any("待核" in x for x in districts if d in x):
                    notes.append(f"{province} 中院辖区映射标注【待核】，检查点 1 必须核实")
                break
        if upper is None:
            notes.append(f"未在 {province} 中院辖区表中匹配到「{d}」，"
                         f"请在检查点 1 人工确定上一级中院（直辖市存在多个中院）")
    elif upper is None and is_basic and province:
        # 非直辖市通用规则：XX市YY区/县法院 → XX市中院
        m = re.match(r"^.*?省(.{2,10}?市)", core_court) or re.match(r"^(.{2,10}?市)", core_court)
        city = m.group(1) if m else ""
        if city:
            upper = f"{city}中级人民法院"
            notes.append("按通用规则推断（区县基层→设区的市中院），检查点 1 请确认")
    elif upper is None and is_intermediate and province:
        upper = f"{province}高级人民法院"
    elif upper is None and "高级人民法院" in core_court:
        upper = "最高人民法院"

    high_court = f"{province}高级人民法院" if province else "（本省高院，待确认）"

    tiers = {
        "顺位1_指导性案例": {
            "范围": "最高人民法院发布的指导性案例",
            "来源": "data/guiding_cases/（本地数据集）+ 法宝 CaseGrade 标注",
        },
        "顺位2_最高法": {
            "范围": "最高人民法院发布的典型案例及裁判生效的案件",
            "法院": ["最高人民法院"],
        },
        "顺位3_本省高院": {
            "范围": "本省（自治区、直辖市）高院发布的参考性案例及裁判生效的案件",
            "法院": [high_court],
        },
        "顺位4_上一级及本院": {
            "范围": "上一级人民法院及本院裁判生效的案件",
            "法院": [c for c in (upper, core_court) if c],
        },
    }
    return {
        "核心法院": core_court,
        "省级行政区": province,
        "顺位": tiers,
        "needs_confirmation": True,   # 永远需要检查点 1 确认
        "notes": notes or ["按规则解析，无特别提示；检查点 1 仍须用户确认"],
    }


if __name__ == "__main__":   # 自测
    import sys
    court = sys.argv[1] if len(sys.argv) > 1 else "北京市朝阳区人民法院"
    print(json.dumps(resolve_tiers(court), ensure_ascii=False, indent=1))
