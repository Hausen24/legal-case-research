#!/usr/bin/env python3
"""
verify_report.py —— 反幻觉校验（把"承诺不编案号"升级为"机器证明没编")
─────────────────────────────────────────────
用法：
    python3 scripts/verify_report.py <research_dir> [报告文件名.md ...] [--strict-quotes]
    # 省略文件名时自动校验 output/ 下所有 `*类案检索报告*.md`（兼容旧名 类案分析报告*.md）

做什么：
  第一层【案号溯源｜硬校验】：
  1. 从 03/04/05 汇总真实检索到的案号全集（CaseFlag）与链接全集。
  2. 报告中引用、但样本池里没有的案号 → 疑似编造（FAIL，退出码 1）。
  第二层【引文核验｜内容抽检】：
  3. 提取报告中引号内的**直接引文**（≥10 个 CJK 字符），在全池判决正文字段
     （Identified/Ascertain/RefereeResult 等）与 output/原文/ 语料中归一化匹配：
     精确命中 / 分块模糊命中 / 未命中。未命中默认 WARNING（直接引文可能是法条或
     司法解释原文，不在判决池），加 --strict-quotes 时升级为 FAIL。

诚实边界（README 同步表述）：本校验证明的是【引用可溯源性】——案号真实存在、
直接引文可在原文找到；**不能证明全部转述内容无误**。转述质量由编码抽检
（spot_check_coding.py）与两个人工检查点把关。
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


# 直接引文样式：中文引号内 10–120 字片段
# 方向性引号（“”「」）开闭可辨，允许较长引文；英文双引号开闭同形，
# 只取不跨行、不含 markdown 标记的短引文，避免把"引号外区间"误当引文。
QUOTE_DIRECTIONAL = re.compile(r'[\u201c\u300c]([^\u201c\u201d\u300c\u300d]{6,120})[\u201d\u300d]')
QUOTE_ASCII = re.compile(r'"([^"\n*|]{4,60})"')


def _has_cjk(t: str) -> bool:
    return any(0x4E00 <= ord(ch) <= 0x9FFF for ch in t)
# 判决正文字段（引文匹配语料）
BODY_FIELDS = ("Identified", "Ascertain", "RefereeResult", "DefenseViewpoint",
               "PlaintiffClaims", "TrialAfter", "ControversialFocus")


def _norm_text(t: str) -> str:
    """\u5f52\u4e00\u5316\uff1a\u53bb\u7a7a\u767d\u4e0e\u5404\u5f0f\u5f15\u53f7\u2014\u2014\u5224\u51b3\u539f\u6587\u5e38\u542b\u5d4c\u5957\u5f15\u53f7\uff08\u5982 \u8ba9\u88c5\u7761\u7684"\u770b\u95e8\u4eba"\u4e0d\u6562\u88c5\u7761\uff09\u3002"""
    return re.sub(r"[\s\u3000\u201c\u201d\u2018\u2019\"'\u300c\u300d]+", "", t or "")


def collect_corpus(research_dir: Path) -> str:
    """全池判决正文 + output/原文/*.md 的归一化语料，供引文匹配。"""
    parts = []
    for name in ("03_raw_cases.json", "04_screened_cases.json", "05_enriched_cases.json"):
        data = load_json(research_dir / name)
        records = []
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    records.extend(v)
        elif isinstance(data, list):
            records = data
        for r in records:
            if isinstance(r, dict):
                for f in BODY_FIELDS:
                    v = r.get(f)
                    if v:
                        parts.append(str(v))
    src_dir = research_dir / "output" / "原文"
    if src_dir.is_dir():
        for fp in src_dir.glob("*.md"):
            parts.append(fp.read_text(encoding="utf-8"))
    return _norm_text("".join(parts))


def check_quotes(md: str, corpus_norm: str) -> list:
    """对报告中的直接引文逐条核验。返回 [(引文, 判定)]；判定∈{精确, 模糊, 未命中}。
    模糊判定：引文切为 ~8 字块，全部块（容忍缺 1 块）在语料中存在——真实引文的
    连续片段必然命中，LLM 改写/拼接的伪引文会丢块。"""
    results = []
    seen = set()
    matches = list(QUOTE_DIRECTIONAL.finditer(md)) + list(QUOTE_ASCII.finditer(md))
    for m in matches:
        q = m.group(1)
        qn = _norm_text(q)
        if len(qn) < 6 or not _has_cjk(qn) or qn in seen:
            continue
        seen.add(qn)
        if qn in corpus_norm:
            results.append((q, "精确"))
            continue
        step = max(8, len(qn) // 3)
        chunks = [qn[i:i + step] for i in range(0, len(qn), step) if len(qn[i:i + step]) >= 6]
        hits = sum(1 for c in chunks if c in corpus_norm)
        results.append((q, "模糊" if chunks and hits >= max(1, len(chunks) - 1) else "未命中"))
    return results


def _prefix_match(cited_no: str, truth_nos: set) -> bool:
    """合并系列案号（如 (2020)湘民终111-113、134号）报告中只引首号；
    若引用案号去掉尾部'号'后是某池内案号的前缀（断点为 - 或 、），视为命中。"""
    stem = cited_no[:-1] if cited_no.endswith("号") else cited_no
    for t in truth_nos:
        if t.startswith(stem) and len(t) > len(stem) and t[len(stem)] in "-、—":
            return True
    return False


def verify_one(report_path: Path, truth_nos: set, truth_urls: set) -> dict:
    md = report_path.read_text(encoding="utf-8")
    cited, urls = extract_from_report(md)
    bad_nos = {k: ctx for k, ctx in cited.items()
               if k not in truth_nos and not _prefix_match(k, truth_nos)}
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
        sys.exit("用法：python3 scripts/verify_report.py <research_dir> [报告文件名.md ...] [--strict-quotes]")
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

    strict_quotes = "--strict-quotes" in sys.argv
    corpus = collect_corpus(research_dir)
    print(f"样本池真实案号 {len(truth_nos)} 个、pkulaw 链接 {len(truth_urls)} 个；"
          f"引文匹配语料 {len(corpus)//1000} 千字。\n")
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
        # 第二层：引文核验
        quotes = check_quotes(rp.read_text(encoding="utf-8"), corpus) if corpus else []
        if quotes:
            n_exact = sum(1 for _, v in quotes if v == "精确")
            n_fuzzy = sum(1 for _, v in quotes if v == "模糊")
            misses = [q for q, v in quotes if v == "未命中"]
            print(f"   引文核验：直接引文 {len(quotes)} 条 → 精确 {n_exact}、模糊 {n_fuzzy}、"
                  f"未命中 {len(misses)}")
            if misses:
                print(f"   {'❌' if strict_quotes else '⚠️ '} 未在判决语料中找到的引文"
                      f"（可能为法条/司法解释原文，请人工核对来源）：")
                for q in misses[:8]:
                    print(f"     « {q[:50]}{'…' if len(q) > 50 else ''} »")
                if strict_quotes:
                    any_fail = True
        print()

    if any_fail:
        print("结论：存在疑似编造案号或缺失报告，校验未通过。请逐条核对来源后再交付。")
        sys.exit(1)
    print("结论：所有被引用案号均可在本次 MCP 检索样本中溯源，反幻觉校验通过。")


if __name__ == "__main__":
    main()
