"""
chart_theme.py — 类案研究报告统一图表主题（投研级·冷色系＋深红强调）

供 run_analytics*.py 与 build_report_docx.py 共用。设计原则：
  - 冷色系（深浅蓝＋中性灰阶），单点强调用北大深红；不使用黄色。
  - 2D 渐变填充 + 柔投影 + 顶部高光，营造层次感（不使用立体 3D，避免数据失真）。
  - 去顶/右边框、数值直接标注、留白充足、dpi>=200、题注「图N」。
用法：
  from chart_theme import apply_theme, PALETTE, RESULT_COLORS, hbar_panel, vbar_panel, stacked_year, save_fig
  apply_theme()
  fig, ax = plt.subplots(...)
  hbar_panel(ax, {"上海金融法院":14, ...}, "审理法院")
  save_fig(fig, "/path/overview.png")
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, rcParams
import matplotlib.pyplot as plt

# ---------- 调色板 ----------
NAVY = "#1F3864"; BLUE2 = "#2E5A88"; BLUE3 = "#4E7CA8"; STEEL = "#6E93B8"; PALE = "#A9C2DA"
RED  = "#9B1B30"   # 强调（北大红系），仅用于单点高亮
G1 = "#3F4A5A"; G2 = "#8A93A0"; G3 = "#AEB6C0"; G4 = "#E3E7EC"
PALETTE = [NAVY, BLUE3, STEEL, BLUE2, PALE]            # 分类用（同色系递进）
RESULT_COLORS = {"全部支持": NAVY, "部分支持": BLUE3, "驳回": G2, "撤销改判": STEEL}

_CJK_CANDIDATES = ["Noto Sans CJK SC", "Noto Sans CJK HK", "Noto Sans CJK JP",
                   "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", "SimHei",
                   # macOS 系统自带（matplotlib 注册名可能为 HK/TC 变体）
                   "PingFang HK", "PingFang TC", "Hiragino Sans GB", "Heiti SC", "Heiti TC",
                   "STHeiti", "Songti SC", "STSong", "Arial Unicode MS"]

def apply_theme():
    """设置全局 rcParams 与中文字体。每次绘图前调用一次。"""
    avail = {f.name for f in font_manager.fontManager.ttflist}
    for c in _CJK_CANDIDATES:
        if c in avail:
            rcParams["font.sans-serif"] = [c]; break
    rcParams["axes.unicode_minus"] = False
    rcParams["figure.facecolor"] = "white"
    rcParams["savefig.facecolor"] = "white"
    rcParams["axes.titlecolor"] = NAVY

# ---------- 内部工具 ----------
def _hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))

def _lighten(hexc, f=0.5):
    r, g, b = _hex2rgb(hexc); return (r+(1-r)*f, g+(1-g)*f, b+(1-b)*f)

def _grad(c1, c2, horiz=True, n=256):
    a = np.array(_hex2rgb(c1)); b = np.array(_hex2rgb(c2))
    t = (np.linspace(0, 1, n)[None, :] if horiz else np.linspace(0, 1, n)[:, None])
    return a[None, None, :]*(1-t[..., None]) + b[None, None, :]*t[..., None]

def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(G3); ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=G1, labelsize=9, length=0)
    ax.set_axisbelow(True)

def _gbar_h(ax, y, w, base, h=0.6, shadow=True):
    if shadow:
        ax.add_patch(plt.Rectangle((0, y-h/2-0.04), w, h, facecolor="#1b2733", alpha=0.10, zorder=1, lw=0))
    light = "#%02x%02x%02x" % tuple(int(x*255) for x in _lighten(base, 0.5))
    im = ax.imshow(_grad(base, light, True), extent=[0, w, y-h/2, y+h/2], aspect="auto", zorder=2, origin="lower")
    clip = plt.Rectangle((0, y-h/2), w, h, fill=False, lw=0); ax.add_patch(clip); im.set_clip_path(clip)
    ax.add_patch(plt.Rectangle((0, y+h/2-h*0.10), w, h*0.10, facecolor="white", alpha=0.18, zorder=3, lw=0))

def _gbar_v(ax, x, hgt, base, w=0.6, shadow=True):
    if shadow:
        ax.add_patch(plt.Rectangle((x-w/2+0.03, 0), w, hgt, facecolor="#1b2733", alpha=0.10, zorder=1, lw=0))
    light = "#%02x%02x%02x" % tuple(int(v*255) for v in _lighten(base, 0.5))
    im = ax.imshow(_grad(light, base, False), extent=[x-w/2, x+w/2, 0, hgt], aspect="auto", zorder=2, origin="lower")
    clip = plt.Rectangle((x-w/2, 0), w, hgt, fill=False, lw=0); ax.add_patch(clip); im.set_clip_path(clip)

# ---------- 对外绘图原语 ----------
def hbar_panel(ax, counter, title, color=NAVY, highlight_max=False):
    """水平渐变条形（已排序，传入 dict）。highlight_max=True 时最高项用深红。"""
    _style(ax); ax.set_xticks([])
    items = list(counter.items())[::-1]
    labels = [k for k, _ in items]; vals = [v for _, v in items]
    if not vals:
        return
    mx = max(vals)
    ax.set_yticks(range(len(items))); ax.set_yticklabels(labels)
    for i, (k, v) in enumerate(items):
        c = RED if (highlight_max and v == mx) else color
        _gbar_h(ax, i, v, c)
        ax.text(v + mx*0.03, i, str(v), va="center", fontsize=9.5,
                color=(RED if (highlight_max and v == mx) else G1),
                fontweight=("bold" if (highlight_max and v == mx) else "normal"))
    ax.set_xlim(0, mx*1.18); ax.set_ylim(-0.6, len(items)-0.4)
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=G1, pad=6)

def vbar_panel(ax, counter, title, color=NAVY):
    _style(ax); ax.set_yticks([])
    ks = list(counter.keys()); vs = list(counter.values())
    if not vs:
        return
    mx = max(vs)
    ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks)
    for i, v in enumerate(vs):
        _gbar_v(ax, i, v, color)
        ax.text(i, v + mx*0.03, str(v), ha="center", fontsize=9.5, color=G1)
    ax.set_ylim(0, mx*1.18); ax.set_xlim(-0.6, len(ks)-0.4)
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=G1, pad=6)

def stacked_year(ax, years, data, title, cats=("全部支持", "部分支持", "驳回", "撤销改判")):
    """堆叠柱：data = {类别: [各年计数]}。"""
    _style(ax); ax.set_yticks([])
    bottom = [0]*len(years)
    for c in cats:
        vals = data.get(c)
        if not vals or sum(vals) == 0:
            continue
        ax.bar(years, vals, bottom=bottom, label=c, color=RESULT_COLORS.get(c, NAVY),
               width=0.6, edgecolor="white", linewidth=0.8)
        bottom = [b+v for b, v in zip(bottom, vals)]
    if not bottom or max(bottom) == 0:
        return
    mxb = max(bottom); ax.set_ylim(0, mxb*1.22)
    ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.0))
    for i, hh in enumerate(bottom):
        if hh:
            ax.text(i, hh + mxb*0.02, str(int(hh)), ha="center", fontsize=9, color=G1)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=10)

def overview_2x2(panels, suptitle="样本概览", figsize=(9, 6.2)):
    """panels = [(kind, counter, title, opts), ...] 共 4 个；kind∈{'h','v'}。返回 fig。"""
    fig, axs = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle(suptitle, x=0.02, ha="left", fontsize=14, fontweight="bold", color=NAVY)
    flat = [axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]]
    for ax, (kind, counter, title, opts) in zip(flat, panels):
        if kind == "h":
            hbar_panel(ax, counter, title, **(opts or {}))
        else:
            vbar_panel(ax, counter, title, **(opts or {}))
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig

def single(figsize=(8.4, 5)):
    return plt.subplots(figsize=figsize)

def save_fig(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
