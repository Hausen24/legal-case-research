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

def col_widths(ncol):
    if ncol <= 1:
        return [CONTENT_W]
    first = int(CONTENT_W * 0.18)
    rest = (CONTENT_W - first) // (ncol - 1)
    return [first] + [rest] * (ncol - 1)

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
                if "——" in v:
                    cover["title"], cover["subtitle"] = v.split("——", 1)
                    cover["subtitle"] = "——" + cover["subtitle"]
                else:
                    cover["title"] = v
                cover["runningTitle"] = cover.get("title", v)
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
            header = [c.strip() for c in s.strip("|").split("|")]
            j += 2; rows = []
            while j < len(body) and body[j].strip().startswith("|"):
                rows.append([c.strip() for c in body[j].strip().strip("|").split("|")])
                j += 1
            blocks.append({"type": "table", "header": header, "rows": rows,
                           "widths": col_widths(len(header))})
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
