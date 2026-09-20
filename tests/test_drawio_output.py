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
