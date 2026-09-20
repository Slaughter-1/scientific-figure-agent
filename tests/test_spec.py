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


def test_missing_style_is_rejected():
    from figure_agent.spec import validate_spec

    spec = {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [],
        "edges": [],
    }
    assert any("style" in error.lower() for error in validate_spec(spec))


def test_plot_arrays_must_have_equal_lengths():
    from figure_agent.spec import validate_spec

    spec = {
        "schema_version": "0.1", "figure_type": "plot", "layout": {"direction": "left-to-right"},
        "nodes": [], "edges": [], "style": {}, "data": {"kind": "line", "x": [1, 2], "y": [0.5]},
    }
    assert any("equal lengths" in error for error in validate_spec(spec))


def test_heatmap_matrix_must_be_rectangular():
    from figure_agent.spec import validate_spec

    spec = {
        "schema_version": "0.1", "figure_type": "plot", "layout": {"direction": "left-to-right"},
        "nodes": [], "edges": [], "style": {}, "data": {"kind": "heatmap", "matrix": [[1, 2], [3]]},
    }
    assert any("rectangular" in error for error in validate_spec(spec))
