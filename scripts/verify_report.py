#!/usr/bin/env python3
"""
verify_report.py —— 反幻觉校验（把"承诺不编案号"升级为"机器证明没编")
─────────────────────────────────────────────
用法：
    python3 scripts/verify_report.py <research_dir> [报告文件名.md ...]
    # 省略文件名时自动校验 output/ 下所有 `*类案检索报告*.md`（兼容旧名 类案分析报告*.md）

做什么：
  1. 从 03_raw_cases.json（并入 04/05，若存在）汇总本次研究**真实检索到**的案号全集
     （字段 CaseFlag）与法宝链接全集（字段 Url，clean_url 后）。
  2. 从报告 Markdown 里抽取所有"案号样式"的字符串、以及所有 http(s) 链接。
  3. 逐一比对：
       · 报告引用、但样本池里没有的案号 → 标记为**疑似编造**（FAIL）。
       · 报告出现、但样本池里没有的 pkulaw 链接 → 警示（WARN，可能正文裸链或附录外链）。
  4. 任一疑似编造 → 退出码 1（供 CI / 收尾自检阻断）。全部命中 → 退出码 0。

设计要点：
  · 只做"存在性"核验——证明每个被引用的案号确实来自 MCP 检索结果，不臆造。
  · 案号比对前先规范化（统一全角括号、去空白），避免「（2023）」与「(2023)」误判。
  · 这是确定性校验，不调用任何模型、不需要网络与 Token，可离线/CI 运行。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "common"))
from pkulaw_utils import clean_url, normalize_caseno  # noqa: E402

# 案号样式：（YYYY）+ 法院/类型字 + 数字 + 号。兼容全角/半角括号。
CASE_NO_RE = re.compile(r"[（(]\s*\d{4}\s*[)）][^\s，。；：、,.;:（）()]{1,40}?\d+号")
URL_RE = re.compile(r"https?://[^\s）)\]\"'，。、]+")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def collect_truth(research_dir: Path):
    """汇总样本池里真实存在的案号集合与链接集合（03 为基底，并入 04/05）。"""
    case_nos, urls = set(), set()
    for name in ("03_raw_cases.json", "04_screened_cases.json", "05_enriched_cases.json"):
        data = load_json(research_dir / name)
        # 04 可能是 {core/parallel/typical: [...]} 结构（证券版三池），统一摊平
        records = []
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    records.extend(v)
        elif isinstance(data, list):
            records = data
        for r in records:
            if not isinstance(r, dict):
                continue
            cf = normalize_caseno(r.get("CaseFlag") or "")
            if cf:
                case_nos.add(cf)
            u = clean_url(r.get("Url") or "")
            if u.startswith("http"):
                urls.add(u.rstrip("/"))
    return case_nos, urls


def extract_from_report(md: str):
    """从报告文本提取引用案号集合与链接集合（含出现位置上下文，便于报错定位）。"""
    cited = {}  # 规范化案号 -> 首次出现的原文片段
    for m in CASE_NO_RE.finditer(md):
        raw = m.group(0)
        key = normalize_caseno(raw)
        if key not in cited:
            start = max(0, m.start() - 18)
            cited[key] = md[start:m.end() + 4].replace("\n", " ")
    urls = {u.rstrip("/") for u in URL_RE.findall(md)}
    return cited, urls


def verify_one(report_path: Path, truth_nos: set, truth_urls: set) -> dict:
    md = report_path.read_text(encoding="utf-8")
    cited, urls = extract_from_report(md)
    bad_nos = {k: ctx for k, ctx in cited.items() if k not in truth_nos}
    # pkulaw 链接才纳入存在性校验；其他外链（典型案例联网核对等）不强校验。
    pku_urls = {u for u in urls if "pkulaw" in u}
    bad_urls = {u for u in pku_urls if u not in truth_urls}
    return {
        "report": report_path.name,
        "cited_total": len(cited),
        "matched": len(cited) - len(bad_nos),
        "bad_nos": bad_nos,
        "pku_urls_total": len(pku_urls),
        "bad_urls": bad_urls,
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python3 scripts/verify_report.py <research_dir> [报告文件名.md ...]")
    research_dir = Path(sys.argv[1])
    if not research_dir.exists():
        sys.exit(f"目录不存在：{research_dir}")

    truth_nos, truth_urls = collect_truth(research_dir)
    if not truth_nos:
        print("⚠️  样本池（03/04/05）中未读到任何 CaseFlag，无法校验——请确认检索数据已落盘。")

    out_dir = research_dir / "output"
    if len(sys.argv) > 2:
        reports = [out_dir / a for a in sys.argv[2:]]
    else:
        # 实案=类案检索报告 / 学理=裁判规则研究报告；兼容旧名 类案分析报告*.md
        reports = sorted(set(out_dir.glob("*类案检索报告*.md"))
                         | set(out_dir.glob("*裁判规则研究报告*.md"))
                         | set(out_dir.glob("类案分析报告*.md")))
    if not reports:
        sys.exit(f"未找到待校验报告（{out_dir}/*类案检索报告*.md）。可显式传入文件名。")

    print(f"样本池真实案号 {len(truth_nos)} 个、pkulaw 链接 {len(truth_urls)} 个。\n")
    any_fail = False
    for rp in reports:
        if not rp.exists():
            print(f"✗ 跳过：找不到 {rp}")
            any_fail = True
            continue
        r = verify_one(rp, truth_nos, truth_urls)
        status = "✅ 通过" if not r["bad_nos"] else "❌ 发现疑似编造案号"
        print(f"── {r['report']} ──  {status}")
        print(f"   引用案号 {r['cited_total']} 个，命中样本池 {r['matched']} 个。")
        if r["bad_nos"]:
            any_fail = True
            print("   下列案号未在本次样本池（MCP 检索结果）中找到，疑似编造或笔误：")
            for k, ctx in r["bad_nos"].items():
                print(f"     • {k}    ……{ctx}……")
        if r["bad_urls"]:
            print(f"   ⚠️  {len(r['bad_urls'])} 个 pkulaw 链接不在样本池中（核对是否裸链/外链）：")
            for u in list(r["bad_urls"])[:10]:
                print(f"     - {u}")
        print()

    if any_fail:
        print("结论：存在疑似编造案号或缺失报告，校验未通过。请逐条核对来源后再交付。")
        sys.exit(1)
    print("结论：所有被引用案号均可在本次 MCP 检索样本中溯源，反幻觉校验通过。")


if __name__ == "__main__":
    main()
