#!/usr/bin/env python3
"""
fetch_guiding_cases.py —— 最高人民法院指导性案例数据集（官网合规抓取）
─────────────────────────────────────────────
用途：实案模式顺位①（法发〔2020〕24号第四条）需要指导性案例全文做深度比对，但北大法宝
MCP 对非普通案例不返回正文。指导性案例由最高法官网公开发布、数量有限、更新缓慢，故建
本地静态数据集，定期重跑本脚本增量更新。

来源：https://www.court.gov.cn/shenpan/gengduo/77.html （审判业务→指导性案例栏目）
合规说明：指导性案例属官方发布的司法文书性质材料（《著作权法》第五条不适用情形）；
本脚本仅限速（默认 ≥1.2s/请求）抓取公开栏目页，UA 如实标识，用于类案检索参照。

用法：
    python3 scripts/fetch_guiding_cases.py            # 增量：已抓过的编号跳过
    python3 scripts/fetch_guiding_cases.py --full     # 全量重抓
    python3 scripts/fetch_guiding_cases.py --limit 5  # 只抓前 5 个（联调用）

输出：
    data/guiding_cases/index.json     [{编号,标题,url,发布时间,本地文件}]
    data/guiding_cases/cases/<编号>.json
        {编号,标题,url,来源,发布时间,关键词,裁判要点,基本案情,裁判结果,裁判理由,
         相关法条,全文}   —— 结构化解析失败的字段为空串，全文一定保留
注意：个别指导性案例已被最高法公告废止/替代（第九条"为新的指导性案例所取代"情形）。
本数据集不含效力状态；实案模式引用前须按第九条核查效力（SKILL 已有该步）。
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://www.court.gov.cn"
LIST_FIRST = "/shenpan/gengduo/77.html"
UA = ("Mozilla/5.0 (compatible; legal-case-research/1.0; "
      "+https://github.com/silvrblt/legal-case-research)")
OUT = Path(__file__).resolve().parent.parent / "data" / "guiding_cases"
DELAY = 1.2

# 兼容两代标题写法："指导性案例N号"（新）与"指导案例N号"（早期）
TITLE_RE = re.compile(
    r'<a\s+title="(指导性?案例\s*(\d+)\s*号[：:][^"]*)"[^>]*href="(/shenpan/xiangqing/\d+\.html)"')
PAGE_RE = re.compile(r'href="[^"]*?77_(\d+)\.html"')
SECTIONS = ["关键词", "裁判要点", "基本案情", "裁判结果", "裁判理由", "相关法条"]


def get(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(BASE + url if url.startswith("/") else url,
                                 headers={"User-Agent": UA})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            time.sleep(DELAY)
            return body.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001  网络抖动重试
            last = e
            time.sleep(DELAY * (attempt + 2))
    raise last


def strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&ldquo;", "“") \
               .replace("&rdquo;", "”").replace("&middot;", "·")
    text = re.sub(r"[ \t　]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_detail(html: str) -> dict:
    """详情页解析：取 txt_txt 容器正文，按六要素切块（失败则字段空、全文兜底）。"""
    m = re.search(r'<div[^>]*class="txt_txt"[^>]*>(.*?)<div[^>]*class="txt_etr"',
                  html, flags=re.S)
    body = strip_html(m.group(1)) if m else strip_html(html)
    src = re.search(r"来源[：:]\s*([^\n<&]{2,40})", html)
    pub = re.search(r"发布时间[：:]\s*([\d\-: ]{8,20})", html)

    out = {"来源": src.group(1).strip() if src else "",
           "发布时间": pub.group(1).strip() if pub else "",
           "全文": body}
    # 六要素切块：定位各小节标题行，取到下一小节为止
    positions = []
    for sec in SECTIONS:
        mm = re.search(rf"(?:^|\n)\s*{sec}\s*(?:\n|[：:])", body)
        if mm:
            positions.append((mm.start(), sec, mm.end()))
    positions.sort()
    for i, (start, sec, content_start) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
        out[sec] = body[content_start:end].strip()
    for sec in SECTIONS:
        out.setdefault(sec, "")
    return out


def collect_list(limit_pages=None):
    """翻列表页收集 (编号, 标题, 详情url)。"""
    first = get(LIST_FIRST)
    pages = sorted({int(n) for n in PAGE_RE.findall(first)})
    last = max(pages) if pages else 1
    if limit_pages:
        last = min(last, limit_pages)
    items = {}
    for title, no, href in TITLE_RE.findall(first):
        items[int(no)] = (title.strip(), href)
    for p in range(2, last + 1):
        html = get(f"/shenpan/gengduo/77_{p}.html")
        for title, no, href in TITLE_RE.findall(html):
            items.setdefault(int(no), (title.strip(), href))
        print(f"  列表页 {p}/{last}：累计 {len(items)} 案")
    return items


def main():
    full = "--full" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    cases_dir = OUT / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    existing = {int(p.stem) for p in cases_dir.glob("*.json")} if not full else set()

    print("收集列表页…")
    items = collect_list()
    todo = sorted((no for no in items if no not in existing), reverse=True)
    if limit:
        todo = todo[:limit]
    print(f"共 {len(items)} 案，已有 {len(existing)}，本次抓取 {len(todo)}。")

    index = []
    fails = []
    for k, no in enumerate(todo, 1):
        title, href = items[no]
        try:
            detail = parse_detail(get(href))
        except Exception as e:  # noqa: BLE001
            fails.append((no, str(e)))
            print(f"  ✗ {no}号 抓取失败：{e}")
            continue
        rec = {"编号": no, "标题": title, "url": BASE + href, **detail}
        (cases_dir / f"{no}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        if k % 10 == 0 or k == len(todo):
            print(f"  进度 {k}/{len(todo)}（最新：{no}号）")

    # 重建 index（含历史已抓）
    for p in sorted(cases_dir.glob("*.json"), key=lambda x: -int(x.stem)):
        rec = json.loads(p.read_text(encoding="utf-8"))
        index.append({"编号": rec["编号"], "标题": rec["标题"], "url": rec["url"],
                      "发布时间": rec.get("发布时间", ""), "本地文件": f"cases/{p.name}"})
    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：数据集共 {len(index)} 案 → {OUT}")
    if fails:
        print(f"⚠️ 失败 {len(fails)} 案（可重跑增量补抓）：{[n for n, _ in fails]}")


if __name__ == "__main__":
    main()
