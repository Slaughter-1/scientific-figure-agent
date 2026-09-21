import json


def test_build_manifest_contains_reproducibility_fields():
    from figure_agent.artifacts import build_manifest

    spec = {"schema_version": "0.1", "figure_type": "workflow", "nodes": [], "edges": []}
    manifest = build_manifest(spec, {"drawio": {"status": "ok", "path": "figure.drawio"}})
    assert manifest["spec_sha256"]
    assert manifest["backends"] == ["drawio"]
    assert manifest["artifacts"]["drawio"]["status"] == "ok"
    json.dumps(manifest)


def test_render_backends_reports_unknown_backend_without_crashing(tmp_path):
    from figure_agent.router import render_backends

    result = render_backends({}, ["unknown"], tmp_path)
    assert result["unknown"]["status"] == "error"
    assert "unknown backend" in result["unknown"]["error"]


def test_export_license_blocks_review_required_resources():
    from figure_agent.license import check_export_license

    findings = check_export_license({"template_refs": [{"id": "community", "approval_status": "review_required"}], "asset_refs": []})

    assert findings[0]["code"] == "license_review_required"
