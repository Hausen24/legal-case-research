"""反幻觉校验脚本的正反测试：真实引用通过、编造案号被抓出。"""
import verify_report as V


def test_normalize_caseno_unifies_brackets():
    assert V.normalize_caseno("(2023) 示01民初0001号") == "（2023）示01民初0001号"


def test_extract_case_numbers_from_text():
    md = "见甲案（（2021）示01民初0001号·北京互联网法院）与乙案（2022）示01民初0042号。"
    cited, _ = V.extract_from_report(md)
    keys = set(cited)
    assert "（2021）示01民初0001号" in keys
    assert "（2022）示01民初0042号" in keys


def test_demo_report_passes_verification(demo_dir):
    """演示报告引用的全部案号都应能在样本池中溯源。"""
    truth_nos, truth_urls = V.collect_truth(demo_dir)
    assert truth_nos, "样本池应至少有一个案号"
    report = demo_dir / "output" / "类案分析报告_居中.md"
    result = V.verify_one(report, truth_nos, truth_urls)
    assert result["bad_nos"] == {}, f"不应有疑似编造案号：{result['bad_nos']}"
    assert result["matched"] == result["cited_total"]


def test_fabricated_caseno_is_flagged(demo_dir, tmp_path):
    """在报告里塞一个样本池没有的案号 → 必须被标记为疑似编造。"""
    truth_nos, truth_urls = V.collect_truth(demo_dir)
    src = (demo_dir / "output" / "类案分析报告_居中.md").read_text(encoding="utf-8")
    tampered = src + "\n\n另见某案（（2099）假00民初9999号·虚构法院）。\n"
    p = tmp_path / "tampered.md"
    p.write_text(tampered, encoding="utf-8")
    result = V.verify_one(p, truth_nos, truth_urls)
    assert "（2099）假00民初9999号" in result["bad_nos"]
