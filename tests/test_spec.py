def test_valid_workflow_spec_has_no_errors():
    from figure_agent.spec import load_spec, validate_spec

    spec = load_spec("examples/m0/workflow.json")
    assert validate_spec(spec) == []


def test_unknown_edge_target_is_rejected():
    from figure_agent.spec import validate_spec

    spec = {
        "figure_type": "workflow",
        "nodes": [{"id": "a", "type": "process", "label": "A"}],
        "edges": [{"source": "a", "target": "missing", "type": "data_flow"}],
    }
    errors = validate_spec(spec)
    assert any("missing" in error for error in errors)


def test_duplicate_node_id_is_rejected():
    from figure_agent.spec import validate_spec

    spec = {
        "figure_type": "workflow",
        "nodes": [
            {"id": "a", "type": "process", "label": "A"},
            {"id": "a", "type": "process", "label": "A2"},
        ],
        "edges": [],
    }
    assert any("duplicate" in error.lower() for error in validate_spec(spec))
