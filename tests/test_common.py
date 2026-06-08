"""scripts/common 公共派生与样本量自适应闸门的单元测试。"""
import pkulaw_utils as U
import stats_guard as sg


# ── pkulaw_utils 确定性派生 ──
def test_clean_url_extracts_bare_link():
    assert U.clean_url("[北大法宝](https://x.com/a.html)") == "https://x.com/a.html"
    assert U.clean_url("https://x.com/b") == "https://x.com/b"
    assert U.clean_url("") == ""


def test_derive_court_level_covers_special_courts():
    assert U.derive_court_level("北京互联网法院") == "互联网法院"
    assert U.derive_court_level("上海金融法院") == "金融法院"
    assert U.derive_court_level("北京知识产权法院") == "知产法院"
    assert U.derive_court_level("上海市浦东新区人民法院") == "基层"
    assert U.derive_court_level("某省高级人民法院") == "高院"
    assert U.derive_court_level("最高人民法院") == "最高人民法院"


def test_flatten_court_splits_province_and_court():
    nested = {"示01": "北京", "示0192": "北京互联网法院"}
    province, court = U.flatten_court(nested)
    assert province == "北京"
    assert court == "北京互联网法院"


def test_derive_year():
    assert U.derive_year("2023.06.18") == "2023"
    assert U.derive_year("2021-01-01") == "2021"
    assert U.derive_year("") == ""


# ── stats_guard 样本量自适应闸门（核心方法论保护）──
def test_depth_mode_switches_on_sample_size():
    assert sg.depth_mode(6)["mode"] == "qualitative_deep"
    assert sg.depth_mode(500)["mode"] == "quantitative_lead"


def test_stat_tier_thresholds():
    assert sg.stat_tier(6) == "T0_descriptive"
    assert sg.stat_tier(50) == "T1_association"
    assert sg.stat_tier(150) == "T2_model"


def test_divergence_gate_blocks_tiny_groups():
    """根治"京沪 2 件就逐问题伪差异"：任一组不足阈值 → 不报告地域分歧。"""
    small = sg.divergence_gate({"上海": 17, "北京": 2})
    assert small["report"] is False
    big = sg.divergence_gate({"上海": 40, "北京": 35})
    assert big["report"] is True


def test_divergence_gate_empty():
    assert sg.divergence_gate({})["report"] is False
