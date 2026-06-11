"""pytest 公共夹具：把已提交的演示样本（examples/demo_*）拷到临时目录，
在隔离副本上跑脚本，避免污染版本库里的展示产物。"""
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo_算法推荐短视频侵权"
DEMO_SEC = REPO / "examples" / "demo_证券虚假陈述集团诉讼"

# 让测试能直接 import 脚本里的纯函数
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "general"))
sys.path.insert(0, str(REPO / "scripts" / "common"))


@pytest.fixture
def demo_copy(tmp_path):
    """把演示研究目录的输入态（03/04/05）拷到 tmp_path，返回该副本路径。"""
    dst = tmp_path / "demo"
    dst.mkdir()
    for name in ("03_raw_cases.json", "04_screened_cases.json", "05_enriched_cases.json"):
        shutil.copy(DEMO / name, dst / name)
    return dst


@pytest.fixture
def demo_sec_copy(tmp_path):
    """把证券集团诉讼演示目录的输入态拷到 tmp_path，返回该副本路径。"""
    dst = tmp_path / "demo_sec"
    dst.mkdir()
    for name in ("03_raw_cases.json", "04_screened_cases.json", "05_enriched_cases.json"):
        shutil.copy(DEMO_SEC / name, dst / name)
    return dst


@pytest.fixture(scope="session")
def repo():
    return REPO


@pytest.fixture(scope="session")
def demo_dir():
    return DEMO
