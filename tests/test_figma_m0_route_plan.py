import json


def test_m0_bundle_compiles_edges_as_vector_from_the_existing_route_plan(tmp_path):
    """M0 must reuse RoutePlan geometry, not the legacy straight-LINE path."""
    from figure_agent.figma_m0 import run_figma_m0

    run_figma_m0(tmp_path)
    scene = json.loads((tmp_path / "local-scene.json").read_text(encoding="utf-8"))
    kinds = {node["kind"] for node in scene["nodes"]}
    assert "VECTOR" in kinds
    assert "LINE" not in kinds


def test_m0_vector_edges_keep_full_polyline_ports_and_source_identity(tmp_path):
    from figure_agent.figma_m0 import run_figma_m0

    run_figma_m0(tmp_path)
    scene = json.loads((tmp_path / "local-scene.json").read_text(encoding="utf-8"))
    vectors = [node for node in scene["nodes"] if node["kind"] == "VECTOR"]
    assert len(vectors) == 4
    for vector in vectors:
        assert vector["source_id"] == f"edge:{vector['edge_index']}"
        assert len(vector["points"]) >= 2
        assert vector["source_port"] and vector["target_port"]
        assert vector["path_data"].startswith("M ")
    # the feedback edge is a routed polyline, not a two-point straight segment
    feedback = next(vector for vector in vectors if vector["label"] == "若证据不足")
    assert len(feedback["points"]) > 2


def test_m0_bundle_records_the_route_plan_transform(tmp_path):
    from figure_agent.figma_m0 import run_figma_m0

    run_figma_m0(tmp_path)
    scene = json.loads((tmp_path / "local-scene.json").read_text(encoding="utf-8"))
    frame = scene["nodes"][0]
    assert frame["kind"] == "FRAME"
    assert frame["route_plan_transform"]["y_axis"] == "down"
    assert scene["route_plan"]["paper_width_mm"] > 20


def test_m0_edge_labels_are_emitted_as_native_text(tmp_path):
    from figure_agent.figma_m0 import run_figma_m0

    run_figma_m0(tmp_path)
    scene = json.loads((tmp_path / "local-scene.json").read_text(encoding="utf-8"))
    labels = [node for node in scene["nodes"] if node["kind"] == "TEXT" and node.get("source_id", "").endswith(":label") and node["source_id"].startswith("edge:")]
    assert any(node["characters"] == "若证据不足" for node in labels)
    for node in labels:
        assert node["anchor"] and node["font_size_pt"] > 0


def test_m0_parity_still_passes_on_the_route_plan_scene(tmp_path):
    from figure_agent.figma_m0 import run_figma_m0

    run_figma_m0(tmp_path)
    parity = json.loads((tmp_path / "parity.json").read_text(encoding="utf-8"))
    assert parity["status"] == "pass"
    assert parity["findings"] == []


def test_m0_remains_unavailable_without_a_real_transport(tmp_path):
    """Local scene generation must never be reported as a connected Figma round-trip."""
    from figure_agent.figma_m0 import run_figma_m0

    result = run_figma_m0(tmp_path)
    assert result["status"] == "unavailable"
    assert result["file_or_frame"] is None
    assert json.loads((tmp_path / "readback.json").read_text(encoding="utf-8"))["status"] == "not_available"
