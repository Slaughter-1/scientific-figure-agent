from pathlib import Path

from figure_agent.spec import load_spec, validate_spec


def test_all_m1_examples_validate():
    examples = sorted(Path("examples/m1").glob("*.json"))
    assert {path.stem for path in examples} == {"architecture", "workflow", "graph", "plot"}
    for path in examples:
        assert validate_spec(load_spec(path)) == [], path


def test_group_children_must_reference_existing_nodes():
    spec = {
        "schema_version": "0.1",
        "figure_type": "architecture",
        "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "a", "label": "A", "type": "process"}],
        "edges": [],
        "groups": [{"id": "g", "label": "Group", "children": ["missing"]}],
        "style": {"colors": {}},
    }
    errors = validate_spec(spec)
    assert any("group" in error.lower() and "missing" in error for error in errors)


def test_plot_requires_data_block():
    spec = {
        "schema_version": "0.1",
        "figure_type": "plot",
        "layout": {"direction": "left-to-right"},
        "nodes": [],
        "edges": [],
        "groups": [],
        "style": {"colors": {}},
    }
    assert any("data" in error.lower() for error in validate_spec(spec))
