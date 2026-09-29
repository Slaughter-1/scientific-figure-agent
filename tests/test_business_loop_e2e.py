"""The full business loop must stay green through the product HTTP entry point.

This guards A: 创建任务 -> 分析 -> 生成三候选 -> 审阅修改 -> 生成新修订 -> 重新选择
-> 正式导出 -> 校验导出包. The helper under test is the loop script itself, so a
regression in any API guard fails here rather than only in a manual run.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_business_loop.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_business_loop", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_business_loop"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def loop_result(tmp_path_factory):
    pytest.importorskip("fastapi")
    module = _load_script()
    return module.run_loop(tmp_path_factory.mktemp("loop") / "data", verbose=False)


def test_loop_script_is_shipped():
    assert SCRIPT.is_file(), "the loop acceptance script must ship with the repo"


def test_every_loop_assertion_passes(loop_result):
    assert loop_result["failures"] == []
    assert loop_result["all_ok"] is True


def test_loop_covers_the_whole_documented_sequence(loop_result):
    steps = " ".join(record["step"] for record in loop_result["assertions"])
    for stage in ("创建任务", "分析", "生成三候选", "审阅修改", "重新选择", "正式导出", "校验导出包"):
        assert stage in steps, f"loop does not cover {stage}"


def test_three_distinct_revisions_are_produced(loop_result):
    revisions = loop_result["revisions"]
    assert len(revisions) == 3
    assert len(set(revisions)) == 3


def test_export_binds_the_reconfirmed_revision(loop_result):
    assert loop_result["export_revision_id"] == loop_result["revisions"][-1]
    assert loop_result["manifest_revision_id"] == loop_result["revisions"][-1]


def test_package_verification_is_recorded_as_verified(loop_result):
    assert loop_result["verification"]["status"] == "verified"
    assert len(loop_result["verification"]["package_sha256"]) == 64


def test_package_carries_every_requested_output(loop_result):
    suffixes = {Path(name).suffix for name in loop_result["zip_entries"]}
    assert {".svg", ".pdf", ".png", ".drawio"} <= suffixes


def test_review_trail_only_records_successful_actions(loop_result):
    assert loop_result["review_trail"] == [
        "select_candidate", "mark_needs_evidence", "resolve_needs_evidence", "select_candidate"]


def test_contract_required_node_removal_is_reported(loop_result):
    codes = loop_result["contract_negative_codes"]
    assert any(code.startswith("contract_required_") for code in codes)


def test_assertion_count_does_not_silently_shrink(loop_result):
    assert len(loop_result["assertions"]) >= 32
