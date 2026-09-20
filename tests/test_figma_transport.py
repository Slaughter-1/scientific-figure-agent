from pathlib import Path


def _spec():
    return {
        "schema_version": "0.1", "figure_type": "workflow", "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "a", "label": "A", "type": "process"}], "edges": [], "groups": [], "style": {},
    }


def test_figma_transport_success_preserves_scene_and_remote_identity(tmp_path):
    from figure_agent.backends.figma_backend import render_figma_spec

    class Transport:
        def write_scene(self, scene):
            return {"status": "connected", "file_or_frame": "figma://file/123", "node_count": len(scene["nodes"])}

    result = render_figma_spec(_spec(), tmp_path, Transport())
    assert result["status"] == "connected"
    assert result["file_or_frame"] == "figma://file/123"
    assert Path(result["scene"]).exists()


def test_figma_transport_failure_keeps_local_scene(tmp_path):
    from figure_agent.backends.figma_backend import render_figma_spec

    class BrokenTransport:
        def write_scene(self, scene):
            raise RuntimeError("MCP unavailable")

    result = render_figma_spec(_spec(), tmp_path, BrokenTransport())
    assert result["status"] == "error"
    assert "MCP unavailable" in result["error"]
    assert Path(result["scene"]).exists()
