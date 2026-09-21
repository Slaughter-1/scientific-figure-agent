def test_generate_three_candidates_preserves_semantics_and_writes_artifacts(tmp_path):
    from figure_agent.candidates import generate_candidates

    spec = {
        "schema_version": "0.2", "figure_type": "workflow", "title": "Agent", "layout": {"direction": "left-to-right"},
        "nodes": [
            {"id": "a", "label": "Input", "type": "data", "evidence": [{"source": "paper", "quote": "Input"}]},
            {"id": "b", "label": "Planner", "type": "process", "evidence": [{"source": "paper", "quote": "Planner"}]},
        ],
        "edges": [{"source": "a", "target": "b", "type": "data_flow"}], "groups": [], "style": {},
    }
    results = generate_candidates(spec, tmp_path, count=3)
    assert len(results) == 3
    assert [result["candidate_id"] for result in results] == ["candidate_01", "candidate_02", "candidate_03"]
    assert all(result["scores"]["structural_validity"] == 1.0 for result in results)
    assert all((tmp_path / result["candidate_id"] / "figure.drawio").exists() for result in results)
    assert results[0]["spec"]["nodes"][0]["id"] == "a"
    assert results[0]["spec"]["candidate_id"] == "candidate_01"


def test_generate_candidates_rejects_more_than_three(tmp_path):
    import pytest

    from figure_agent.candidates import generate_candidates

    with pytest.raises(ValueError, match="between 1 and 3"):
        generate_candidates({"schema_version": "0.1", "figure_type": "workflow", "layout": {"direction": "left-to-right"}, "nodes": [], "edges": [], "style": {}}, tmp_path, count=4)


def test_candidates_have_distinct_design_families_and_fingerprints(tmp_path):
    from figure_agent.candidates import generate_candidates

    spec = {
        "schema_version": "0.2", "figure_type": "workflow", "title": "Agent Loop", "layout": {"direction": "left-to-right"},
        "nodes": [
            {"id": "query", "label": "用户问题", "type": "data", "evidence": [{"source": "paper", "quote": "用户问题"}]},
            {"id": "planner", "label": "规划器", "type": "process", "evidence": [{"source": "paper", "quote": "规划器"}]},
            {"id": "tool", "label": "工具", "type": "tool", "evidence": [{"source": "paper", "quote": "工具"}]},
            {"id": "answer", "label": "答案", "type": "data", "evidence": [{"source": "paper", "quote": "答案"}]},
        ],
        "edges": [
            {"source": "query", "target": "planner", "type": "data_flow"},
            {"source": "planner", "target": "tool", "type": "control_flow"},
            {"source": "tool", "target": "answer", "type": "data_flow"},
            {"source": "tool", "target": "planner", "type": "control_flow"},
        ],
        "groups": [], "style": {},
    }
    results = generate_candidates(spec, tmp_path, count=3)

    assert len({item["design"]["family"] for item in results}) == 3
    assert all(item["design"]["rationale"] for item in results)
    assert all(item["preview_fingerprint"]["node_positions"] for item in results)
    assert len({str(item["preview_fingerprint"]) for item in results}) == 3


def test_linear_candidates_explain_loop_tradeoff(tmp_path):
    from figure_agent.candidates import generate_candidates

    spec = {
        "schema_version": "0.2", "figure_type": "workflow", "layout": {"direction": "left-to-right"},
        "nodes": [
            {"id": "a", "label": "A", "type": "data", "evidence": [{"source": "paper", "quote": "A"}]},
            {"id": "b", "label": "B", "type": "process", "evidence": [{"source": "paper", "quote": "B"}]},
            {"id": "c", "label": "C", "type": "data", "evidence": [{"source": "paper", "quote": "C"}]},
        ],
        "edges": [{"source": "a", "target": "b", "type": "data_flow"}, {"source": "b", "target": "c", "type": "data_flow"}],
        "groups": [], "style": {},
    }
    result = generate_candidates(spec, tmp_path, count=3)[2]

    assert result["design"]["family"] in {"hierarchy", "swimlane"}
    assert any("反馈" in item or "loop" in item.lower() for item in result["design"]["tradeoffs"])
