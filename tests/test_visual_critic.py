import json


def test_critique_scene_detects_overlap_and_out_of_bounds():
    from figure_agent.visual_critic import critique_scene

    scene = {
        "nodes": [
            {"kind": "FRAME", "x": 0, "y": 0, "width": 200, "height": 120},
            {"kind": "RECTANGLE", "source_id": "a", "x": 10, "y": 10, "width": 100, "height": 50},
            {"kind": "RECTANGLE", "source_id": "b", "x": 50, "y": 20, "width": 100, "height": 50},
            {"kind": "RECTANGLE", "source_id": "c", "x": 180, "y": 90, "width": 40, "height": 40},
        ]
    }
    findings = critique_scene(scene)
    codes = {item["code"] for item in findings}
    assert "node_overlap" in codes
    assert "out_of_bounds" in codes


def test_critique_svg_reports_missing_dimensions(tmp_path):
    from figure_agent.visual_critic import critique_artifact

    path = tmp_path / "figure.svg"
    path.write_text('<svg><text>tiny</text></svg>', encoding="utf-8")
    findings = critique_artifact(path)
    assert any(item["code"] == "missing_dimensions" for item in findings)


def test_critique_candidate_set_detects_duplicate_visual_fingerprint():
    from figure_agent.visual_critic import critique_candidate_set

    candidates = [
        {"candidate_id": "candidate_01", "preview_fingerprint": {"node_positions": {"a": [1, 1]}, "edge_routes": [], "style_variant": "editorial"}},
        {"candidate_id": "candidate_02", "preview_fingerprint": {"node_positions": {"a": [1, 1]}, "edge_routes": [], "style_variant": "editorial"}},
    ]

    findings = critique_candidate_set(candidates)

    assert any(item["code"] == "candidate_similarity" for item in findings)
