from pathlib import Path


def test_drawio_output_contains_shared_workflow_labels():
    from figure_agent.backends.drawio_backend import check_drawio_output

    errors = check_drawio_output(Path("outputs/m0/workflow.drawio"))
    assert errors == []
