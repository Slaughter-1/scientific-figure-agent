import json


def test_figma_m0_local_bundle_is_explicitly_unavailable_without_transport(tmp_path):
    from figure_agent.figma_m0 import run_figma_m0

    result = run_figma_m0(tmp_path)
    assert result["status"] == "unavailable"
    assert json.loads((tmp_path / "parity.json").read_text(encoding="utf-8"))["status"] == "pass"
    assert (tmp_path / "transport-schema.json").exists()
    assert (tmp_path / "smoke.log").exists()


def test_visual_review_sheet_has_20_cases_x_3_candidates_x_2_sizes(tmp_path):
    from figure_agent.visual_eval import build_review_sheet

    cases = json.loads(open("eval_cases/visual_quality/benchmark_20.json", encoding="utf-8").read())
    payload = json.loads(build_review_sheet(cases, tmp_path / "reviews.json").read_text(encoding="utf-8"))
    assert len(cases) == 20
    assert payload["row_count"] == 120
    assert payload["rows"][0]["paper_width"] == "single_column"


def test_embedded_external_asset_requires_source_and_content_identity():
    from figure_agent.license import check_export_license

    findings = check_export_license({"template_refs": [], "asset_refs": [{"asset_id": "a", "license": "MIT", "embedded": True}]})
    assert {item["code"] for item in findings} >= {"license_evidence_missing", "content_identity_missing"}
