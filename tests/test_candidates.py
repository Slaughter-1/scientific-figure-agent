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
