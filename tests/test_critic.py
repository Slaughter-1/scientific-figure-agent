from figure_agent.critic import critique_spec, refine_spec


def _spec():
    return {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [
            {"id": "a", "label": "Input", "type": "data"},
            {"id": "b", "label": "Input", "type": "model"},
        ],
        "edges": [{"source": "a", "target": "missing", "type": "data_flow"}],
    }


def test_critique_reports_actionable_findings():
    findings = critique_spec(_spec())
    codes = {finding["code"] for finding in findings}
    assert {"missing_style", "missing_title", "dangling_edge", "duplicate_label"} <= codes
    assert all(set(finding) >= {"code", "severity", "message"} for finding in findings)


def test_refine_spec_fixes_only_safe_metadata_and_returns_valid_spec():
    refined, changes = refine_spec(_spec())
    assert refined["title"] == "Workflow"
    assert refined["style"] == {}
    assert {"add_title", "add_style"} <= set(changes)
    assert not {finding["code"] for finding in critique_spec(refined)} & {"missing_style", "missing_title"}


def test_critique_reports_nodes_without_evidence():
    spec = {
        "schema_version": "0.3", "figure_type": "workflow", "title": "Method",
        "layout": {"direction": "left-to-right"}, "style": {},
        "nodes": [{"id": "a", "label": "Unsupported module", "type": "process", "evidence": []}],
        "edges": [], "groups": [],
    }

    findings = critique_spec(spec)

    assert any(item["code"] == "missing_evidence" and "a" in item["message"] for item in findings)
