from pathlib import Path


def _spec():
    return {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [
            {"id": "a", "label": "Input", "type": "data"},
            {"id": "b", "label": "Model", "type": "model"},
        ],
        "edges": [{"source": "a", "target": "b", "type": "data_flow"}],
        "groups": [],
        "style": {},
    }


def test_same_spec_drawio_and_figma_semantics_match(tmp_path):
    from figure_agent.backends.drawio_backend import render_drawio_spec
    from figure_agent.backends.figma_backend import compile_figma_scene
    from figure_agent.parity import compare_semantics, extract_drawio_semantics, extract_figma_semantics

    spec = _spec()
    drawio = render_drawio_spec(spec, tmp_path, "figure")["drawio"]
    assert compare_semantics(spec, extract_drawio_semantics(drawio)) == []
    assert compare_semantics(spec, extract_figma_semantics(compile_figma_scene(spec))) == []


def test_parity_reports_label_mismatch_with_source_id():
    from figure_agent.backends.figma_backend import compile_figma_scene
    from figure_agent.parity import compare_semantics, extract_figma_semantics

    scene = compile_figma_scene(_spec())
    next(node for node in scene["nodes"] if node.get("source_id") == "b")["name"] = "Wrong"
    findings = compare_semantics(_spec(), extract_figma_semantics(scene))
    assert any(finding["code"] == "label_mismatch" and finding["source_id"] == "b" for finding in findings)
