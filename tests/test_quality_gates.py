"""一期质量门测试：Schema 校验（正反例）、覆盖率自检、分歧检测数据层。"""
import json
import subprocess
import sys

import pipeline_schema as ps


# ── Schema 校验 ──
def test_validate_05_passes_on_demo(demo_dir):
    cases = json.loads((demo_dir / "05_enriched_cases.json").read_text(encoding="utf-8"))
    rep = ps.validate_05(cases)
    assert rep.ok, f"demo 05 应通过契约校验：{rep.errors}"


def test_validate_05_catches_type_and_enum_errors(demo_dir):
    cases = json.loads((demo_dir / "05_enriched_cases.json").read_text(encoding="utf-8"))
    cases[0]["判赔金额"] = "二十八万"          # 类型错
    cases[1]["裁判结果分类"] = "基本支持"       # 枚举外
    rep = ps.validate_05(cases)
    assert any("判赔金额" in e for e in rep.errors)
    assert any("裁判结果分类" in e for e in rep.errors)


def test_validate_05_catches_focus_name_drift(demo_dir):
    """焦点名拼写漂移（全半角括号不一致）会导致聚合分裂 → 必须报错。"""
    cases = json.loads((demo_dir / "05_enriched_cases.json").read_text(encoding="utf-8"))
    fp = cases[0]["焦点立场"]
    key = next(k for k in fp if "（" in k or "）" in k or True)
    drifted = key.replace("（", "(").replace("）", ")") + " "
    if drifted == key:
        drifted = key + "　"
    fp[drifted] = fp.pop(key)
    rep = ps.validate_05(cases)
    assert any("拼写不一致" in e for e in rep.errors)


def test_validate_03_catches_duplicate_gid(demo_dir):
    raw = json.loads((demo_dir / "03_raw_cases.json").read_text(encoding="utf-8"))
    raw.append(dict(raw[0]))
    rep = ps.validate_03(raw)
    assert any("Gid 重复" in e for e in rep.errors)


def test_validate_unknown_fields_tolerated(demo_dir):
    """宽松白名单：二期新增字段（_顺位/参照效力/相关度依据）不得报错。"""
    cases = json.loads((demo_dir / "05_enriched_cases.json").read_text(encoding="utf-8"))
    cases[0]["_顺位"] = 4
    cases[0]["参照效力"] = "可以参考"
    cases[0]["相关度依据"] = "基本事实与争议焦点均高度吻合"
    rep = ps.validate_05(cases)
    assert rep.ok, f"未知新字段不应报错：{rep.errors}"


def test_validate_pipeline_cli_on_demo(repo, demo_dir):
    r = subprocess.run([sys.executable, "scripts/validate_pipeline.py", str(demo_dir)],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "校验通过" in r.stdout


# ── 覆盖率自检 ──
def test_check_coverage_outputs_sections(repo, demo_copy):
    r = subprocess.run([sys.executable, "scripts/check_coverage.py", str(demo_copy)],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    cov = json.loads((demo_copy / "07_coverage.json").read_text(encoding="utf-8"))
    assert cov["关键词覆盖"], "应有关键词命中矩阵"
    assert "独有命中" in next(iter(cov["关键词覆盖"].values()))
    assert cov["案件等级分布"].get("普通(07)") == 6
    assert cov["顺位覆盖"] is None, "实案模式顺位节本期应预留为 null"
    assert cov["去重审计"]["Gid重复"] == []


def test_check_coverage_roster_gap(repo, demo_copy):
    """名录里塞一个样本池没有的案号 → 必须出现在缺口。"""
    roster = [
        {"名称": "甲影视公司诉乙科技公司案", "案号": "（2021）示01民初0001号", "来源": "演示名录"},
        {"名称": "不存在的典型案例", "案号": "（2099）缺00民初1号", "来源": "演示名录"},
    ]
    (demo_copy / "名录.json").write_text(json.dumps(roster, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, "scripts/check_coverage.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    cov = json.loads((demo_copy / "07_coverage.json").read_text(encoding="utf-8"))
    assert cov["名录核对"]["命中数"] == 1
    assert any("不存在的典型案例" in g.get("名称", "") for g in cov["名录核对"]["缺口"])


# ── 分歧检测数据层 ──
def test_divergence_in_general_analytics(repo, demo_copy):
    subprocess.run([sys.executable, "scripts/general/normalize_cases.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run([sys.executable, "scripts/general/run_analytics.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    a = json.loads((demo_copy / "06_analytics.json").read_text(encoding="utf-8"))
    div = a["分歧地图"]
    assert div, "demo 中支持原告/支持被告并存的争点应被检出"
    issue = "平台是否构成信息网络传播权侵权"
    assert issue in div
    info = div[issue]
    assert set(info["立场分布"]) == {"支持原告", "支持被告"}
    assert info["代表案"]["支持被告"], "对立立场应有代表案号"
    assert info["地域闸门"]["report"] is False, "小样本不得作地域倾向结论"
    # 仅单一实质立场（另一焦点 4×支持原告+2×未评述）不应入分歧地图
    assert "算法推荐对“技术中立/避风港”抗辩的影响" not in div


def test_divergence_in_securities_analytics(repo, demo_sec_copy):
    subprocess.run([sys.executable, "scripts/securities/normalize_secmisrep.py",
                    str(demo_sec_copy)], cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run([sys.executable, "scripts/securities/run_analytics_secmisrep.py",
                    str(demo_sec_copy)], cwd=repo, capture_output=True, text=True, check=True)
    a = json.loads((demo_sec_copy / "06_analytics.json").read_text(encoding="utf-8"))
    div = a["分歧地图"]
    assert "重大性" in div, "S01 具有重大性 vs S03 不具重大性 应被检出"
    assert len(div["重大性"]["立场分布"]) >= 2


# ── 引文核验层（内容级抽检）──
def test_quote_check_real_vs_fabricated(demo_dir):
    import verify_report as V
    corpus = V.collect_corpus(demo_dir)
    assert len(corpus) > 1000
    # demo 池真实裁判说理片段 → 应命中
    real = V.check_quotes("法院认为“算法推荐使平台对内容传播范围具有控制力与获益”云云", corpus)
    assert real and real[0][1] in ("精确", "模糊"), real
    # 伪造"判决原话" → 必须未命中
    fake = V.check_quotes("法院指出“本案应适用火星法统一裁判原理予以处断”", corpus)
    assert fake and fake[0][1] == "未命中", fake
    # 嵌套引号容错：语料含引号时归一化后仍可命中
    assert V._norm_text('让装睡的"看门人"不敢装睡') == V._norm_text("让装睡的看门人不敢装睡")


def test_apply_coding_protects_raw_fields(repo, demo_copy, tmp_path):
    import json as _json, subprocess, sys as _sys
    coding = [{"CaseFlag": "（2021）示01民初0001号", "新编码字段": "v",
               "Identified": "恶意改写"}]
    cf = tmp_path / "c.json"
    cf.write_text(_json.dumps(coding, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([_sys.executable, "scripts/general/apply_coding.py",
                        str(demo_copy), str(cf)], cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    recs = _json.loads((demo_copy / "05_enriched_cases.json").read_text(encoding="utf-8"))
    rec = next(x for x in recs if x.get("CaseFlag") == "（2021）示01民初0001号")
    assert rec["新编码字段"] == "v"
    assert "恶意改写" not in (rec.get("Identified") or "")


def test_verify_flag_not_treated_as_filename(repo):
    """回归：显式文件名 + --strict-quotes 组合，旗标不得被当文件名（曾致永远 FAIL）。"""
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, "scripts/verify_report.py",
                        "examples/demo_证券虚假陈述集团诉讼",
                        "证券虚假陈述-裁判规则研究报告-20260609.md", "--strict-quotes"],
                       cwd=repo, capture_output=True, text=True)
    assert "找不到" not in r.stdout, r.stdout
    assert r.returncode == 0, r.stdout


def test_demo_reports_pass_strict_quotes(repo):
    """demo 报告引用合成判决原文，必须能过 strict（引文层的回归保护）。"""
    import subprocess, sys as _sys
    r = subprocess.run([_sys.executable, "scripts/verify_report.py",
                        "examples/demo_证券虚假陈述集团诉讼", "--strict-quotes"],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_term_mark_sentinel(repo):
    """「」豁免通道哨兵：裁判语体/超长片段被标出，正常短术语与命中语料者放行。"""
    import sys as _sys
    _sys.path.insert(0, str(repo / "scripts"))
    from verify_report import check_term_marks, _norm_text
    corpus = _norm_text("被告平台对侵权视频的算法推荐构成应知，应当承担连带赔偿责任。")
    md = ("本院观点为「本院认为，被告的行为构成侵权，应当承担赔偿责任」；"
          "术语如「应当参照」「重大事件＋价量敏感」不应触发；"
          "超长归纳「平台经算法推荐机制传播用户上传的侵权影视切条内容」应触发；"
          "命中语料的「被告平台对侵权视频的算法推荐构成应知」自动豁免。")
    flagged = check_term_marks(md, corpus)
    assert any("本院认为" in t for t in flagged)
    assert any("影视切条" in t for t in flagged)
    assert not any(t in ("应当参照", "重大事件＋价量敏感") for t in flagged)
    assert not any("构成应知" in t for t in flagged)
    assert len(flagged) == 2, flagged


def test_demo_reports_no_sentinel_warnings(repo):
    """demo 报告须无「」哨兵警示——示范文本必须自身合规。"""
    import subprocess, sys as _sys
    for d in ("examples/demo_算法推荐短视频侵权", "examples/demo_证券虚假陈述集团诉讼"):
        r = subprocess.run([_sys.executable, "scripts/verify_report.py", d, "--strict-quotes"],
                           cwd=repo, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout
        assert "「」哨兵" not in r.stdout, r.stdout
