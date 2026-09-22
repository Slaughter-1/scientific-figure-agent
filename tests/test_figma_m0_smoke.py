from pathlib import Path


def _m0_spec():
    return {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "title": "M0 Figma Smoke",
        "layout": {"direction": "left-to-right", "spacing": 24},
        "nodes": [
            {"id": "query", "label": "用户问题", "type": "data"},
            {"id": "retriever", "label": "检索器", "type": "tool"},
            {"id": "generator", "label": "生成器", "type": "model"},
            {"id": "answer", "label": "答案", "type": "data"},
        ],
        "edges": [
            {"source": "query", "target": "retriever", "type": "data_flow"},
            {"source": "retriever", "target": "generator", "type": "data_flow"},
            {"source": "generator", "target": "answer", "type": "data_flow"},
            {"source": "generator", "target": "retriever", "type": "control_flow", "label": "若证据不足"},
        ],
        "groups": [{"id": "agent-loop", "label": "Agent loop", "children": ["retriever", "generator"]}],
        "style": {"colors": {"data": "#F2F4F7", "process": "#E8EEF7"}},
    }


def test_m0_local_figma_scene_is_native_and_semantically_equal(tmp_path):
    from figure_agent.backends.figma_backend import LocalFigmaDriver, render_figma_spec
    from figure_agent.backends.figma_backend import compile_figma_scene
    from figure_agent.parity import compare_semantics, extract_figma_semantics

    spec = _m0_spec()
    scene = compile_figma_scene(spec)
    assert {node["kind"] for node in scene["nodes"]} >= {"FRAME", "RECTANGLE", "TEXT", "LINE"}
    assert any(node.get("label") == "若证据不足" for node in scene["nodes"] if node["kind"] == "LINE")
    assert compare_semantics(spec, extract_figma_semantics(scene)) == []
    result = render_figma_spec(spec, tmp_path, LocalFigmaDriver())
    assert result["scene"] == str(Path(tmp_path) / "figure.figma-scene.json")
    assert result["status"] == "mock"
    assert result["node_count"] == len(scene["nodes"])


def test_m0_connected_transport_requires_explicit_identity(tmp_path):
    from figure_agent.backends.figma_backend import ConnectedFigmaDriver, render_figma_spec

    spec = _m0_spec()
    result = render_figma_spec(
        spec,
        tmp_path,
        ConnectedFigmaDriver(lambda scene: {"status": "connected", "file_or_frame": "figma://m0"}),
    )
    assert result["status"] == "connected"
    assert result["file_or_frame"] == "figma://m0"
