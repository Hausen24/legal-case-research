"""二期双模式测试：顺位解析、顺位覆盖、学理图表、指导性案例数据集。"""
import json
import subprocess
import sys

import court_hierarchy as ch
import sys as _s; _s.path.insert(0, "scripts/general")


# ── 四顺位法院解析 ──
def test_tier_resolution_municipality_multi_intermediate():
    """直辖市多中院：朝阳→三中院（不是一/二/四中院）。"""
    r = ch.resolve_tiers("北京市朝阳区人民法院")
    t4 = r["顺位"]["顺位4_上一级及本院"]["法院"]
    assert "北京市第三中级人民法院" in t4 and "北京市朝阳区人民法院" in t4
    assert r["顺位"]["顺位3_本省高院"]["法院"] == ["北京市高级人民法院"]
    assert r["needs_confirmation"] is True


def test_tier_resolution_regular_city():
    r = ch.resolve_tiers("浙江省杭州市西湖区人民法院")
    assert "杭州市中级人民法院" in r["顺位"]["顺位4_上一级及本院"]["法院"]
    assert r["顺位"]["顺位3_本省高院"]["法院"] == ["浙江省高级人民法院"]


def test_tier_resolution_special_court():
    r = ch.resolve_tiers("上海金融法院")
    assert "上海市高级人民法院" in r["顺位"]["顺位4_上一级及本院"]["法院"]


# ── 覆盖率自检的顺位覆盖节 ──
def test_coverage_tier_section(repo, demo_copy):
    tiers = {"顺位2_最高法": ["最高人民法院"],
             "顺位3_本省高院": ["北京市高级人民法院"],
             "顺位4_上一级及本院": ["北京知识产权法院", "北京互联网法院"]}
    (demo_copy / "顺位法院.json").write_text(
        json.dumps(tiers, ensure_ascii=False), encoding="utf-8")
    subprocess.run([sys.executable, "scripts/check_coverage.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    cov = json.loads((demo_copy / "07_coverage.json").read_text(encoding="utf-8"))
    tc = cov["顺位覆盖"]
    assert tc is not None
    assert "顺位1_指导性案例" in tc
    # demo 里有 3 件北京互联网法院 + 1 件北京知产法院 → 顺位4 命中 ≥4
    assert tc["顺位4_上一级及本院"]["命中"] >= 4
    # demo 的"最高人民法院（演示）"含"最高人民法院"子串 → 顺位2 命中且无缺口提示
    assert tc["顺位2_最高法"]["命中"] >= 1


# ── 学理模式图表 ──
def test_scholarly_charts_generated(repo, demo_copy):
    subprocess.run([sys.executable, "scripts/general/normalize_cases.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    subprocess.run([sys.executable, "scripts/general/run_analytics.py", str(demo_copy)],
                   cwd=repo, capture_output=True, text=True, check=True)
    manifest = json.loads(
        (demo_copy / "output" / "_charts" / "manifest.json").read_text(encoding="utf-8"))
    assert "region_dist" in manifest, "学理模式地域分布图应生成"
    assert "issue_region" in manifest, "争点×地域热力矩阵应生成"
    assert (demo_copy / "output" / "_charts" / "issue_region.png").exists()


# ── 指导性案例数据集（测已提交数据，不访问网络）──
def test_guiding_cases_dataset(repo):
    idx_path = repo / "data" / "guiding_cases" / "index.json"
    assert idx_path.exists(), "指导性案例数据集应已建立"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    assert len(idx) >= 250
    nums = {r["编号"] for r in idx}
    assert 279 in nums and 1 in nums
    # 抽查一案结构化质量
    rec = json.loads((repo / "data" / "guiding_cases" / idx[0]["本地文件"])
                     .read_text(encoding="utf-8"))
    for key in ("裁判要点", "基本案情", "裁判理由"):
        assert rec.get(key), f"最新案例缺 {key}"
    assert rec["url"].startswith("https://www.court.gov.cn/")


# ── 集团案自动检测阀门 ──
def test_group_valve_detect_mode(repo):
    """demo 池 8 件各异公司 → 阀门应判散案形态（不触发折叠）。"""
    import subprocess, sys
    r = subprocess.run([sys.executable, "scripts/general/fold_group_cases.py",
                        str(repo / "examples" / "demo_证券虚假陈述集团诉讼"),
                        "--detect", "--cause", "证券虚假陈述"],
                       cwd=repo, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "散案形态" in r.stdout


def test_group_valve_helpers():
    import fold_group_cases as fg
    assert fg.classify({"RefereeResult": "驳回原告的全部诉讼请求。"}) == "驳回"
    assert fg.classify({"RefereeResult": "赔偿原告投资差额损失1万元；驳回其余请求"}) == "部分支持"
    # 伪公司名黑名单：法条名不得被当公司
    c = {"Ascertain": "依据中华人民共和国证券投资基金法的规定，" * 3,
         "Identified": "贵州长征天成控股股份有限公司存在虚假记载" * 3}
    assert "长征天成" in fg.body_issuer(c)
