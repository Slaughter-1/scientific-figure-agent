import json
from pathlib import Path


def _workflow_spec():
    return {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "title": "Agent Workflow",
        "layout": {"direction": "left-to-right", "spacing": 24},
        "nodes": [
            {"id": "query", "label": "User Query", "type": "data"},
            {"id": "planner", "label": "Planner", "type": "process"},
        ],
        "edges": [{"source": "query", "target": "planner", "type": "data_flow"}],
        "groups": [],
        "style": {"colors": {"data": "#F2F4F7", "process": "#E8EEF7"}},
    }


def test_compile_figma_scene_has_editable_nodes_and_stable_source_ids():
    from figure_agent.backends.figma_backend import compile_figma_scene

    scene = compile_figma_scene(_workflow_spec())
    kinds = {node["kind"] for node in scene["nodes"]}
    assert {"FRAME", "RECTANGLE", "TEXT", "LINE"} <= kinds
    source_ids = [node["source_id"] for node in scene["nodes"] if node.get("source_id")]
    assert len(source_ids) == len(set(source_ids))
    assert {"query", "planner"} <= set(source_ids)


def test_render_figma_without_driver_is_explicitly_unavailable(tmp_path):
    from figure_agent.backends.figma_backend import render_figma_spec

    result = render_figma_spec(_workflow_spec(), tmp_path)
    assert result["status"] == "unavailable"
    assert Path(result["scene"]).exists()
    assert "file_or_frame" not in result
    json.loads(Path(result["scene"]).read_text(encoding="utf-8"))


def test_local_figma_driver_returns_mock_status(tmp_path):
    from figure_agent.backends.figma_backend import LocalFigmaDriver, render_figma_spec

    result = render_figma_spec(_workflow_spec(), tmp_path, LocalFigmaDriver())
    assert result["status"] == "mock"
    assert Path(result["scene"]).exists()
