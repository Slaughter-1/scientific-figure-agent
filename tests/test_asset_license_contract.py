import pytest


def _asset_files(tmp_path):
    svg = tmp_path / "retriever.svg"
    svg.write_text('<svg width="320" height="180"></svg>', encoding="utf-8")
    evidence = tmp_path / "retriever-license.txt"
    evidence.write_text("MIT License\nCopyright (c) 2026 Example Owner\n", encoding="utf-8")
    return svg, evidence


def _authorized(tmp_path):
    from figure_agent.components import register_asset

    svg, evidence = _asset_files(tmp_path)
    return register_asset(
        svg,
        source="user_upload",
        license="MIT",
        source_url="https://example.org/assets/retriever.svg",
        license_evidence_url="https://example.org/assets/LICENSE",
        license_evidence_path=evidence,
        approval_status="approved",
    )


def _findings(asset):
    from figure_agent.license import check_export_license

    return check_export_license({"template_refs": [], "asset_refs": [asset]})


def test_default_registration_is_not_approved(tmp_path):
    """Registration must never self-approve; approval stays an explicit human act."""
    from figure_agent.components import register_asset

    svg, _ = _asset_files(tmp_path)
    asset = register_asset(svg, source="user_upload", license_status="user_confirmed")
    assert asset["approval_status"] == "pending_review"
    assert {item["code"] for item in _findings(asset)} >= {"license_review_required"}


def test_registration_always_binds_the_hash_to_file_bytes(tmp_path):
    from figure_agent.components import register_asset

    svg, _ = _asset_files(tmp_path)
    asset = register_asset(svg, source="user_upload")
    assert asset["hash_scope"] == "file_bytes"
    assert asset["content_sha256"] == asset["sha256"]


def test_authorized_asset_passes_the_export_audit(tmp_path):
    """The legal happy path must actually clear the gate, not merely be blockable."""
    assert _findings(_authorized(tmp_path)) == []


def test_approval_is_refused_when_evidence_is_incomplete(tmp_path):
    from figure_agent.components import register_asset

    svg, _ = _asset_files(tmp_path)
    with pytest.raises(ValueError):
        register_asset(svg, source="user_upload", license="MIT", approval_status="approved")


def test_unknown_license_cannot_be_approved(tmp_path):
    from figure_agent.components import register_asset

    svg, evidence = _asset_files(tmp_path)
    with pytest.raises(ValueError):
        register_asset(svg, source="user_upload", license="unknown", source_url="https://example.org/a.svg",
                       license_evidence_url="https://example.org/LICENSE", license_evidence_path=evidence,
                       approval_status="approved")


def test_changed_asset_bytes_still_fail_after_approval(tmp_path):
    asset = _authorized(tmp_path)
    (tmp_path / "retriever.svg").write_text('<svg width="999" height="180"></svg>', encoding="utf-8")
    assert {item["code"] for item in _findings(asset)} >= {"content_identity_mismatch"}


def test_changed_license_evidence_still_fails_after_approval(tmp_path):
    asset = _authorized(tmp_path)
    (tmp_path / "retriever-license.txt").write_text("All rights reserved.\n", encoding="utf-8")
    assert {item["code"] for item in _findings(asset)} >= {"license_evidence_mismatch"}


def test_missing_evidence_asset_still_fails(tmp_path):
    from figure_agent.components import register_asset

    svg, _ = _asset_files(tmp_path)
    asset = register_asset(svg, source="user_upload", license="MIT")
    codes = {item["code"] for item in _findings(asset)}
    assert "license_review_required" in codes
    assert "license_evidence_missing" in codes


def test_bulk_assembly_does_not_grant_approval(tmp_path):
    """Directory-scanned assets are unreviewed by definition."""
    import json
    from figure_agent.assembly import assemble_spec_with_assets

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "retriever.svg").write_text('<svg width="320" height="180"></svg>', encoding="utf-8")
    spec_path = tmp_path / "figure-spec.json"
    spec_path.write_text(json.dumps({"nodes": [{"id": "retriever", "label": "R", "type": "tool"}]}), encoding="utf-8")
    result = assemble_spec_with_assets(spec_path, assets_dir, tmp_path / "out.json")
    assert result["asset_refs"][0]["approval_status"] == "pending_review"
    assert _findings(result["asset_refs"][0])
