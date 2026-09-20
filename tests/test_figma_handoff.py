import json


def _spec():
    return {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "a", "label": "A", "type": "process"}],
        "edges": [],
        "groups": [],
        "style": {},
    }


def test_build_figma_handoff_writes_scene_and_unavailable_manifest(tmp_path):
    from figure_agent.figma_handoff import build_figma_handoff

    spec_path = tmp_path / "figure-spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    result = build_figma_handoff(spec_path, tmp_path / "out")
    assert result["status"] == "unavailable"
    assert (tmp_path / "out" / "figure.figma-scene.json").exists()
    assert (tmp_path / "out" / "figma-manifest.json").exists()


def test_build_figma_handoff_accepts_connected_identity(tmp_path):
    from figure_agent.figma_handoff import build_figma_handoff

    spec_path = tmp_path / "figure-spec.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    result = build_figma_handoff(
        spec_path,
        tmp_path / "out",
        connection={"status": "connected", "file_or_frame": "https://www.figma.com/design/example"},
    )
    assert result["status"] == "connected"
    assert result["file_or_frame"].endswith("example")
