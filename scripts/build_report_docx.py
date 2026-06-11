#!/usr/bin/env python3
"""
build_report_docx.py —— 报告 Markdown → Word（薄包装）
用法：python3 build_report_docx.py <research_dir> <report_md_filename>

职责：解析 output/<report_md> 的 Markdown 为干净 JSON 块模型（封面元信息、分级标题、
正文/要点、`[案名（案号·法院）](裸链接)` 转脚注、`[^id]`+定义 转脚注、`![chart:key]` 按
图表清单插图、Markdown 表格），交由共用渲染器 render_report.mjs（docx-js）产出 .docx。
解析放在 Python 端（稳健），Node 端只做渲染原语。
"""
import sys, os, re, json, subprocess

NAVY = "1F3864"
CONTENT_W = 8306  # A4 去左右各 1800 twips 后的正文宽

def load_chart_manifest(research_dir):
    p = os.path.join(research_dir, "output", "_charts", "manifest.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}

def _cell_text(cell):
    """从单元格（字符串或行内 runs 数组）取纯文本，用于表头识别。"""
    if isinstance(cell, str):
        return cell
    return "".join(r.get("t", "") for r in (cell or []))

def _disp_len(cell):
    """单元格显示宽度估算（中日韩宽字符计 2，半角计 1）。"""
    t = _cell_text(cell)
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in t)

def col_widths(header, rows=None):
    """内容感知的列宽分配：按各列实际内容的最大显示宽度加权分配，
    短列（序号/相似度/档位等数值列）自然收窄、长文列拿到更多宽度并允许换行，
    目标是表格尽可能少占行数。规则：
    - 每列取 max(表头, 各行单元格) 显示宽度，下限 4、上限 36（超长靠换行消化）；
    - 按比例分配正文宽；末列吸收取整余数，合计精确等于正文宽。
    兼容旧调用：传入整数列数时均分。
    """
    if isinstance(header, int):
        n = header
        widths = [CONTENT_W // n] * n
        widths[-1] += CONTENT_W - sum(widths)
        return widths
    ncol = len(header)
    if ncol <= 1:
        return [CONTENT_W]
    maxlens = []
    for ci in range(ncol):
        m = _disp_len(header[ci])
        for r in (rows or []):
            if ci < len(r):
                m = max(m, _disp_len(r[ci]))
        maxlens.append(min(max(m, 4), 36))
    total = sum(maxlens)
    widths = [max(560, int(CONTENT_W * m / total)) for m in maxlens]
    widths[-1] += CONTENT_W - sum(widths)
    return widths

class FN:
    """脚注编号与内容管理（文档顺序分配序号）。

    每个引用占用一个**独立**脚注号——Word 要求"一个脚注定义对应一个引用标记"，
    同一脚注被多处引用会被 Word 判为损坏并自动修复（并注入空段落）。故同一 `[^id]`
    第二次及以后出现时，生成"同前引"短引而非复用同一脚注号。
    """
    def __init__(self, defs):
        self.defs = defs            # markdown footnote 定义 {id: text}
        self.seen = {}              # 已首次引用的 id -> 首个脚注号
        self.items = {}             # 序号 -> {text,url}
        self.n = 0
    def _next(self):
        self.n += 1; return self.n
    def ref(self, mid):             # [^id] 标记：每次出现都分配新脚注号
        num = self._next()
        text = self.defs.get(mid, "")
        if mid in self.seen:
            short = (text.split("，")[0] or text)[:40]
            self.items[num] = {"text": f"{short}，前引注〔{self.seen[mid]}〕。"}
        else:
            self.seen[mid] = num
            self.items[num] = {"text": text}
        return num
    def link(self, text, url):      # [text](url) 案例脚注
        num = self._next()
        if url.startswith("http"):
            self.items[num] = {"text": text, "url": url}
        else:
            self.items[num] = {"text": text}
        return num

INLINE = re.compile(r'\[\^(\w+)\]|\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*')

def parse_inline(text, fn):
    runs, pos = [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            runs.append({"t": text[pos:m.start()]})
        if m.group(1) is not None:
            runs.append({"fn": fn.ref(m.group(1))})
        elif m.group(2) is not None:
            runs.append({"t": m.group(2), "fn": fn.link(m.group(2), m.group(3))})
        elif m.group(4) is not None:
            runs.append({"t": m.group(4), "b": True})
        pos = m.end()
    if pos < len(text):
        runs.append({"t": text[pos:]})
    # 导语标签：段首加粗且以冒号结尾 → 藏蓝
    if runs and runs[0].get("b") and runs[0].get("t", "").rstrip().endswith(("：", ":")):
        runs[0]["color"] = NAVY
    return runs or [{"t": ""}]

def parse(md, manifest):
    lines = md.split("\n")
    # 1) 收集脚注定义并剔除
    defs, body = {}, []
    for ln in lines:
        m = re.match(r'^\[\^(\w+)\]:\s*(.*)$', ln)
        if m:
            defs[m.group(1)] = m.group(2)
        else:
            body.append(ln)
    fn = FN(defs)
    # 2) 封面元信息（首个标题前的 **k**：v 行）
    cover = {"kind": "分析报告", "meta": []}
    i = 0
    while i < len(body) and not re.match(r'^#{1,3}\s', body[i]):
        m = re.match(r'^\*\*(.+?)\*\*\s*[：:]\s*(.*)$', body[i].strip())
        if m:
            k, v = m.group(1), m.group(2)
            if k in ("报告主题", "标题", "title"):
                # 封面标题净化：去掉尾部括注（括号仅作行内必要说明，不上封面）
                v_clean = re.sub(r"[（(][^（）()]*[)）]\s*$", "", v).strip()
                if "——" in v_clean:
                    main_t, sub = v_clean.split("——", 1)
                    cover["subtitle"] = "——" + sub
                else:
                    main_t = v_clean
                # 「xx纠纷/案件 + 报告类型」拆两行：类型词单独一行
                mt = re.match(r"^(.{4,})(类案检索报告|裁判规则研究报告|类案分析报告|研究报告)$",
                              main_t)
                cover["titleLines"] = [mt.group(1).strip(), mt.group(2)] if mt else [main_t]
                cover["title"] = main_t
                cover["runningTitle"] = main_t
            else:
                cover["meta"].append(f"{k}：{v}")
        i += 1
    # 3) 块解析
    blocks = [{"type": "toc"}, {"type": "pagebreak"}]
    j = i
    while j < len(body):
        ln = body[j]
        s = ln.strip()
        if not s:
            j += 1; continue
        mh = re.match(r'^(#{1,3})\s+(.*)$', s)
        mc = re.match(r'^!\[chart:(\w+)\]\s*$', s)
        if mh:
            blocks.append({"type": "h", "level": len(mh.group(1)), "text": mh.group(2).strip()})
            j += 1
        elif mc:
            key = mc.group(1); info = manifest.get(key)
            if info:
                blocks.append({"type": "image", "path": info["path"],
                               "w": info.get("w", 540), "h": info.get("h", 340),
                               "caption": info.get("caption", "")})
            j += 1
        elif re.match(r'^[-*]\s+', s):
            blocks.append({"type": "bullet", "runs": parse_inline(re.sub(r'^[-*]\s+', '', s), fn)})
            j += 1
        elif s.startswith("|") and j + 1 < len(body) and re.match(r'^\|[\s:|-]+\|', body[j+1].strip()):
            header = [parse_inline(c.strip(), fn) for c in s.strip("|").split("|")]
            j += 2; rows = []
            while j < len(body) and body[j].strip().startswith("|"):
                rows.append([parse_inline(c.strip(), fn)
                             for c in body[j].strip().strip("|").split("|")])
                j += 1
            blocks.append({"type": "table", "header": header, "rows": rows,
                           "widths": col_widths(header, rows)})
        else:
            blocks.append({"type": "p", "runs": parse_inline(s, fn)})
            j += 1
    return {"cover": cover, "blocks": blocks, "footnotes": fn.items}

def main():
    research_dir, md_name = sys.argv[1], sys.argv[2]
    md_path = os.path.join(research_dir, "output", md_name)
    md = open(md_path, encoding="utf-8").read()
    model = parse(md, load_chart_manifest(research_dir))
    out_dir = os.path.join(research_dir, "output")
    model_path = os.path.join(out_dir, "_report_model.json")
    json.dump(model, open(model_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out_docx = os.path.join(out_dir, os.path.splitext(md_name)[0] + ".docx")
    renderer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_report.mjs")
    subprocess.run(["node", renderer, model_path, out_docx], check=True)
    print("报告已生成：", out_docx)

if __name__ == "__main__":
    main()
