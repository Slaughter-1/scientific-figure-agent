from pathlib import Path


def test_drawio_output_contains_shared_workflow_labels():
    from figure_agent.backends.drawio_backend import check_drawio_output

    errors = check_drawio_output(Path("outputs/m0/workflow.drawio"))
    assert errors == []


def test_drawio_xml_escapes_label_text():
    from figure_agent.backends.drawio_backend import build_drawio_xml

    xml = build_drawio_xml(
        {
            "nodes": [{"id": "a", "label": "A & B", "type": "process"}],
            "edges": [],
        }
    )
    assert "A &amp; B" in xml


def test_render_drawio_spec_writes_editable_and_preview_artifacts(tmp_path):
    from figure_agent.backends.drawio_backend import check_drawio_output, render_drawio_spec

    spec = {
        "schema_version": "0.1",
        "figure_type": "architecture",
        "layout": {"direction": "top-to-bottom", "spacing": 32},
        "nodes": [
            {"id": "input", "label": "Input", "type": "data"},
            {"id": "model", "label": "Model", "type": "model"},
            {"id": "store", "label": "Store", "type": "storage"},
        ],
        "edges": [
            {"source": "input", "target": "model", "type": "data_flow"},
            {"source": "model", "target": "store", "type": "data_flow"},
        ],
        "groups": [{"id": "stage", "label": "Stage", "children": ["model"]}],
        "style": {"colors": {"data": "#F2F4F7", "model": "#DCEBFA", "storage": "#EFE7FA"}},
    }

    artifacts = render_drawio_spec(spec, tmp_path, "architecture")
    assert set(artifacts) == {"drawio", "svg", "pdf"}
    assert all(path.exists() and path.stat().st_size > 0 for path in artifacts.values())
    assert check_drawio_output(artifacts["drawio"], ["Input", "Model", "Store"]) == []
    assert "Input" in artifacts["svg"].read_text(encoding="utf-8")
