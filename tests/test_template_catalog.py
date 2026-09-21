def test_search_templates_returns_open_license_candidates_with_audit_fields():
    from figure_agent.templates import search_templates

    results = search_templates("architecture", policy="open_license_first", limit=3)
    assert len(results) == 3
    assert all(result["license"] in {"verified", "project_owned"} for result in results)
    assert all({"source_url", "license_evidence_url", "editable", "supported_types", "components", "restrictions", "approval_status"} <= set(result) for result in results)


def test_broad_search_can_expose_review_required_template_but_open_policy_filters_it():
    from figure_agent.templates import search_templates

    broad = search_templates("figma", policy="broad_search", limit=10)
    safe = search_templates("figma", policy="open_license_first", limit=10)
    assert any(result["license"] == "review_required" for result in broad)
    assert all(result["license"] != "review_required" for result in safe)
