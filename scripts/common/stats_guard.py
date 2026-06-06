"""
stats_guard.py — 样本量自适应闸门（定量强度）＋ 深度律（定性强度）

解决两类毛病：小样本硬套检验（如京沪 2 件就做卡方→伪差异）、大样本却只堆叙述。
两条规则方向相反，随样本量自适应：
  · 定量：样本越大，解锁越强的统计（描述→关联检验→建模）。
  · 定性：样本越小，单案/单争点的论证越要深入展开（深度律）。

依赖：numpy、scipy（缺失时关联检验降级为"不可用"，描述性与深度律不受影响）。
"""
from __future__ import annotations
import math

try:
    import numpy as np
    from scipy import stats as _sps
    _HAS_SCIPY = True
except Exception:                       # 优雅降级
    _HAS_SCIPY = False

# ---------- 阈值（可在 CLAUDE.md / 配置中覆盖）----------
MIN_GROUP        = 5     # 分组比较中，任一组样本下限（如京沪各自的件数）
MIN_EXPECTED     = 5     # 卡方期望频数下限；任一格 <5 则改用 Fisher 或不检验
MIN_N_INFERENTIAL = 30   # 解锁关联检验的总样本下限
MIN_N_MODEL      = 100   # 解锁回归建模的总样本下限
MIN_EPV          = 10    # 建模时每自变量对应的事件数下限（events per variable）
DEEP_DIVE_MAX_N  = 30    # 独立事件数 <= 此值时，报告走"定性深挖"模式

# ---------- 深度律（定性强度）----------
def depth_mode(n_events: int) -> dict:
    """
    返回报告的定性/定量侧重。
      qualitative_deep：案少→每个争点的抗辩逻辑与裁判逻辑充分展开（500–1500字/争点），
                        量化仅做描述性，代表案几乎全部细读。
      quantitative_lead：案多→量化分析（交叉/检验/建模，按下方闸门解锁）承载全景，
                        定性深挖只选标杆/分歧案例。
    """
    if n_events <= DEEP_DIVE_MAX_N:
        return {"mode": "qualitative_deep",
                "per_issue_words": (500, 1500),
                "read_fulltext": "all_representative",
                "note": f"独立事件 {n_events} 件（≤{DEEP_DIVE_MAX_N}），以定性深挖为主，量化仅描述性。"}
    return {"mode": "quantitative_lead",
            "per_issue_words": (200, 600),
            "read_fulltext": "landmark_and_divergent",
            "note": f"独立事件 {n_events} 件（>{DEEP_DIVE_MAX_N}），以量化分析承载全景，定性深挖选标杆/分歧案。"}

# ---------- 定量闸门 ----------
def stat_tier(n_obs: int) -> str:
    """根据样本量返回可用的最高统计档：'T0_descriptive' / 'T1_association' / 'T2_model'。"""
    if n_obs >= MIN_N_MODEL:
        return "T2_model"
    if n_obs >= MIN_N_INFERENTIAL:
        return "T1_association"
    return "T0_descriptive"

def crosstab_test(table) -> dict:
    """
    对二维列联表做关联检验，并自带前提校验与对外措辞。
    table: 2D 序列（行=组，列=类别）。返回 dict：
      usable(bool), method, statistic, p_value, cramers_v, n, min_expected, caveat, phrasing
    规则：n>=MIN_N_INFERENTIAL 且 期望频数全部>=MIN_EXPECTED → 卡方；
          期望不足但规模尚可 → Fisher（2x2）/ 不检验；样本过小 → 仅描述。
    """
    out = {"usable": False, "method": None, "statistic": None, "p_value": None,
           "cramers_v": None, "n": None, "min_expected": None, "caveat": None, "phrasing": None}
    if not _HAS_SCIPY:
        out["caveat"] = "scipy 不可用，未做关联检验，仅呈现描述性分布。"
        out["phrasing"] = "（仅描述性分布）"
        return out
    arr = np.asarray(table, dtype=float)
    n = arr.sum()
    out["n"] = int(n)
    if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 2 or n == 0:
        out["caveat"] = "列联表维度不足，无法检验。"; out["phrasing"] = "（样本不足，不作推断）"; return out
    chi2, p, dof, expected = _sps.chi2_contingency(arr, correction=False)
    min_exp = float(expected.min()); out["min_expected"] = round(min_exp, 2)
    if n < MIN_N_INFERENTIAL or min_exp < MIN_EXPECTED:
        # 2x2 且总量尚可时用 Fisher 兜底；否则不作推断
        if arr.shape == (2, 2) and n >= 10:
            odds, pf = _sps.fisher_exact(arr)
            out.update(usable=True, method="Fisher 精确检验", statistic=round(float(odds), 3),
                       p_value=round(float(pf), 4),
                       caveat=f"期望频数偏低（min={min_exp:.1f}），采用 Fisher 精确检验。",
                       phrasing=("提示性关联（Fisher p=%.3f），样本有限，结论从严" % pf))
            return out
        out["caveat"] = (f"样本量 n={int(n)} 或期望频数 min={min_exp:.1f} 未达阈值"
                         f"（n≥{MIN_N_INFERENTIAL}、期望≥{MIN_EXPECTED}），不作显著性推断。")
        out["phrasing"] = "（小样本，示取向非占比定论，不作显著性推断）"
        return out
    k = min(arr.shape) - 1
    cramers = math.sqrt(chi2 / (n * k)) if k > 0 else None
    out.update(usable=True, method="卡方检验", statistic=round(float(chi2), 3),
               p_value=round(float(p), 4), cramers_v=(round(cramers, 3) if cramers is not None else None),
               caveat=None,
               phrasing=("统计显著（χ²={:.2f}, p={:.3f}, Cramér's V={:.2f}）".format(chi2, p, cramers)
                         if p < 0.05 else
                         "未见显著关联（χ²={:.2f}, p={:.3f}）".format(chi2, p)))
    return out

# ---------- 京沪（地域）分歧闸门 ----------
def divergence_gate(group_counts: dict, min_group: int = MIN_GROUP) -> dict:
    """
    判断是否应输出"地域分歧"结论（修复"京沪 2 件就逐问题伪差异"的根因）。
    group_counts: {'上海': 17, '北京': 2}。
    返回 dict：report(bool), reason, phrasing。report=False 时模板不得设地域分歧小节。
    """
    if not group_counts:
        return {"report": False, "reason": "无分组数据", "phrasing": ""}
    small = {g: c for g, c in group_counts.items() if c < min_group}
    if small:
        names = "、".join(f"{g}{c}件" for g, c in group_counts.items())
        return {"report": False,
                "reason": f"存在样本不足分组（{small}），低于阈值 {min_group}。",
                "phrasing": f"两地样本悬殊（{names}），不作地域差异的统计推断；"
                            f"如确有个案取向不同，仅在相关争点处一句话点出。"}
    return {"report": True, "reason": "各分组样本均达阈值，可做地域比较。", "phrasing": None}

# ---------- 建模可行性 ----------
def model_feasible(n_obs: int, n_predictors: int) -> dict:
    epv = (n_obs / n_predictors) if n_predictors else 0
    ok = n_obs >= MIN_N_MODEL and epv >= MIN_EPV
    return {"feasible": ok, "n": n_obs, "epv": round(epv, 1),
            "caveat": None if ok else f"样本/EPV 不足（n={n_obs}, EPV={epv:.1f}；需 n≥{MIN_N_MODEL}、EPV≥{MIN_EPV}），不建模。"}


if __name__ == "__main__":   # 自测
    print("depth_mode(19) ->", depth_mode(19)["mode"], "|", depth_mode(19)["note"])
    print("depth_mode(420) ->", depth_mode(420)["mode"])
    print("divergence_gate(沪17/京2) ->", divergence_gate({"上海": 17, "北京": 2}))
    print("divergence_gate(沪40/京35) ->", divergence_gate({"上海": 40, "北京": 35})["report"])
    print("crosstab(小样本 京沪×结果) ->", crosstab_test([[5, 7, 5], [1, 0, 1]])["phrasing"])
    print("crosstab(大样本) ->", crosstab_test([[40, 60, 50], [55, 45, 60]])["phrasing"])
