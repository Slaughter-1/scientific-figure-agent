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


def test_critique_flags_branch_cue_collapsed_to_linear_graph():
    spec = {
        "schema_version": "0.1", "figure_type": "workflow", "title": "Method",
        "layout": {"direction": "left-to-right"}, "style": {},
        "nodes": [
            {"id": "a", "label": "审核", "type": "decision", "evidence": [{"quote": "审核通过后发布，审核失败则返回修改环节"}]},
            {"id": "b", "label": "发布", "type": "process", "evidence": [{"quote": "审核通过后发布，审核失败则返回修改环节"}]},
        ], "edges": [{"source": "a", "target": "b", "type": "data_flow"}], "groups": [],
    }
    assert any(item["code"] == "missing_branch_structure" for item in critique_spec(spec))


def test_critique_flags_loop_cue_without_feedback_edge():
    spec = {
        "schema_version": "0.1", "figure_type": "workflow", "title": "Method",
        "layout": {"direction": "left-to-right"}, "style": {},
        "nodes": [
            {"id": "a", "label": "检索器", "type": "tool", "evidence": [{"quote": "证据不足则回到检索器"}]},
            {"id": "b", "label": "知识库", "type": "storage", "evidence": [{"quote": "查询知识库，证据不足则回到检索器"}]},
        ], "edges": [{"source": "a", "target": "b", "type": "data_flow"}], "groups": [],
    }
    assert any(item["code"] == "missing_feedback_structure" for item in critique_spec(spec))


def test_critique_does_not_call_a_conditional_feedback_edge_a_branch():
    spec = {
        "schema_version": "0.1", "figure_type": "workflow", "title": "Method",
        "layout": {"direction": "left-to-right"}, "style": {},
        "nodes": [
            {"id": "a", "label": "检索器", "type": "tool", "evidence": [{"quote": "若证据不足则回到检索器"}]},
            {"id": "b", "label": "知识库", "type": "storage", "evidence": [{"quote": "查询知识库，若证据不足则回到检索器"}]},
        ], "edges": [
            {"source": "a", "target": "b", "type": "data_flow"},
            {"source": "b", "target": "a", "type": "control_flow", "label": "若证据不足"},
        ], "groups": [],
    }
    codes = {item["code"] for item in critique_spec(spec)}
    assert "missing_branch_structure" not in codes
