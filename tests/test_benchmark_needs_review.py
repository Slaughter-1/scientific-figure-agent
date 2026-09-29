import json
import warnings

import pytest


CLEAN_CASE = {"id": "clean_01", "category": "pipeline", "text": "文本经过分词、编码后送入分类器并输出标签"}
NEEDS_REVIEW_CASE = {"id": "review_01", "category": "pipeline", "text": "文本经过分词、编码后送入分类器，可能的后处理模块输出标签"}
FAILED_CASE = {"id": "failed_01", "category": "pipeline", "text": ""}


@pytest.fixture(scope="module")
def benchmark(tmp_path_factory):
    from figure_agent.visual_eval import generate_benchmark

    root = tmp_path_factory.mktemp("benchmark")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        index = generate_benchmark([CLEAN_CASE, NEEDS_REVIEW_CASE, FAILED_CASE], root)
    return json.loads(index.read_text(encoding="utf-8"))


def _record(payload, case_id):
    return next(record for record in payload["records"] if record["case_id"] == case_id)


def test_three_outcomes_are_distinguishable_in_the_run_index(benchmark):
    """无待审生成 / 带待审生成 / 生成失败 must be three distinct, readable outcomes."""
    assert _record(benchmark, "clean_01")["review_state"] == "clean"
    assert _record(benchmark, "review_01")["review_state"] == "needs_review"
    assert _record(benchmark, "failed_01")["review_state"] == "failed"


def test_raw_generated_failed_status_is_preserved(benchmark):
    """The pre-existing status vocabulary must not change meaning."""
    assert _record(benchmark, "clean_01")["status"] == "generated"
    assert _record(benchmark, "review_01")["status"] == "generated"
    assert _record(benchmark, "failed_01")["status"] == "failed"
    assert _record(benchmark, "review_01")["candidate_count"] == 3
    assert "error" in _record(benchmark, "failed_01")


def test_needs_review_counts_and_codes_are_recorded(benchmark):
    record = _record(benchmark, "review_01")
    assert record["needs_review_count"] >= 1
    assert "uncertain_entity" in record["needs_review_codes"]
    assert _record(benchmark, "clean_01")["needs_review_count"] == 0
    assert _record(benchmark, "clean_01")["needs_review_codes"] == []


def test_candidate_level_review_status_is_preserved(benchmark):
    record = _record(benchmark, "review_01")
    assert [item["candidate_id"] for item in record["candidates"]] == ["candidate_01", "candidate_02", "candidate_03"]
    assert all(item["review_state"] == "needs_review" for item in record["candidates"])
    assert all(item["needs_review_count"] >= 1 for item in record["candidates"])
    assert all(item["review_state"] == "clean" for item in _record(benchmark, "clean_01")["candidates"])
    assert _record(benchmark, "failed_01")["candidates"] == []


def test_summary_partitions_every_case_exactly_once(benchmark):
    summary = benchmark["summary"]
    assert summary["generated_clean"] == 1
    assert summary["generated_with_needs_review"] == 1
    assert summary["failed"] == 1
    assert summary["generated_clean"] + summary["generated_with_needs_review"] + summary["failed"] == benchmark["case_count"] == 3
    assert summary["complete"] is True


def test_summary_aggregates_needs_review_by_code(benchmark):
    assert benchmark["summary"]["needs_review_by_code"]["uncertain_entity"] >= 1


def test_summary_is_not_complete_when_cases_go_unaccounted(tmp_path):
    """Fail-closed: a shrunken denominator must not read as a complete run."""
    from figure_agent.visual_eval import summarize_benchmark

    payload = {"case_count": 3, "records": [{"case_id": "clean_01", "status": "generated", "review_state": "clean", "needs_review_codes": [], "needs_review_count": 0}]}
    assert summarize_benchmark(payload)["complete"] is False


def test_summary_rejects_duplicate_case_ids():
    from figure_agent.visual_eval import summarize_benchmark

    record = {"case_id": "clean_01", "status": "generated", "review_state": "clean", "needs_review_codes": [], "needs_review_count": 0}
    payload = {"case_count": 2, "records": [record, dict(record)]}
    assert summarize_benchmark(payload)["complete"] is False


def test_summary_rejects_unknown_review_state():
    from figure_agent.visual_eval import summarize_benchmark

    payload = {"case_count": 1, "records": [{"case_id": "x", "status": "generated", "review_state": "probably_fine", "needs_review_codes": [], "needs_review_count": 0}]}
    result = summarize_benchmark(payload)
    assert result["complete"] is False
    assert result["generated_clean"] == 0
