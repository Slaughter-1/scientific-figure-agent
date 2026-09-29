"""Development regressions from the reviewed v3 artifact (not a holdout)."""
from collections import Counter
from copy import deepcopy
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "routing_readability"


@pytest.fixture
def base_spec():
    return json.loads((FIXTURES / "v3_candidate_02_spec.json").read_text(encoding="utf-8"))


def test_reference_semantics_are_four_nodes_five_edges(base_spec):
    labels = {n["id"]: n["label"] for n in base_spec["nodes"]}
    assert len(labels) == 4
    assert Counter((labels[e["source"]], labels[e["target"]], e["type"], e.get("label", ""))
                   for e in base_spec["edges"]) == Counter([
        ("协调器", "检索代理", "data_flow", ""),
        ("协调器", "分析代理", "data_flow", ""),
        ("检索代理", "回答代理", "data_flow", ""),
        ("分析代理", "回答代理", "data_flow", ""),
        ("回答代理", "检索代理", "control_flow", "若证据不足"),
    ])


@pytest.mark.parametrize("left,right,code", [
    ([(0, 0), (10, 0)], [(3, 0), (9, 0)], "edge_visual_merge"),
    ([(0, 0), (0, 10)], [(0, 9), (0, 3)], "edge_reverse_overlap"),
    ([(0, 0), (0, 0), (2, 0), (4, 0), (6, 0), (10, 0)], [(0, 1), (10, 1)], "edge_visual_merge"),
    ([(0, 0), (10, 0)], [(0, 3), (10, 3)], None),
    ([(0, 0), (2, 0)], [(2, 0), (4, 0)], None),
])
def test_route_conflicts_include_same_direction_and_fragmented_near_parallel(left, right, code):
    from figure_agent.layouts import route_pair_conflicts
    findings = route_pair_conflicts(left, right, mm_per_unit=1.0)
    assert code in {f["code"] for f in findings} if code else findings == []


def test_route_conflicts_report_unmarked_interior_crossing():
    from figure_agent.layouts import route_crossings
    findings = route_crossings([(0, 1), (10, 1)], [(5, 0), (5, 2)])
    assert "edge_crossing" in {finding["code"] for finding in findings}


def test_original_long_fanin_and_short_fanout_are_detected():
    from figure_agent.layouts import route_pair_conflicts
    old = json.loads((FIXTURES / "v3_candidate_02_routes.json").read_text(encoding="utf-8"))
    for a, b in [(0, 1), (2, 3)]:
        assert "edge_visual_merge" in {f["code"] for f in route_pair_conflicts(
            old["routes"][a], old["routes"][b], mm_per_unit=10.0)}


def assert_independent_routes(plan):
    from figure_agent.layouts import route_pair_conflicts
    assert not any(f["code"] == "routing_unresolved" for f in plan["findings"])
    ports = {}
    for i, route in enumerate(plan["routes"]):
        assert len(route["points"]) >= 2
        assert tuple(route["points"][0]) == tuple(route["source_port"]["point"])
        assert tuple(route["points"][-1]) == tuple(route["target_port"]["point"])
        for other in plan["routes"][i+1:]:
            assert route_pair_conflicts(route["points"], other["points"], mm_per_unit=plan["mm_per_unit"]) == []
        for node, port in [(route["source"], route["source_port"]), (route["target"], route["target_port"])]:
            assert 0.2 <= port["offset"] <= 0.8
            for other in ports.setdefault(node, []):
                assert math.dist(port["point"], other) * plan["mm_per_unit"] >= 2.0 - 1e-6
            ports[node].append(port["point"])


@pytest.mark.parametrize("family", ["pipeline", "swimlane", "hierarchy", "loop"])
@pytest.mark.parametrize("width_mm", [85.0, 180.0])
def test_routes_preserve_every_semantic_field_and_use_independent_channels(base_spec, family, width_mm):
    from figure_agent.layouts import build_route_plan
    before = deepcopy(base_spec)
    plan = build_route_plan(base_spec, family=family, paper_width_mm=width_mm)
    assert base_spec == before
    assert [(r["source"], r["target"]) for r in plan["routes"]] == [
        (e["source"], e["target"]) for e in base_spec["edges"]]
    assert_independent_routes(plan)


def test_explicit_v3_positions_are_preserved(base_spec):
    from figure_agent.layouts import build_route_plan
    old = json.loads((FIXTURES / "v3_candidate_02_routes.json").read_text(encoding="utf-8"))
    positions = {key: tuple(value) for key, value in old["positions"].items()}
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0, positions=positions)
    assert plan["positions"] == positions
    assert_independent_routes(plan)
    for route in plan["routes"]:
        points = route["points"]
        assert len(points) == len({tuple(point) for point in points})
        for index, (a, b) in enumerate(zip(points, points[1:])):
            for c, d in zip(points[index + 2:], points[index + 3:]):
                if abs(a[1]-b[1]) < 1e-8 and abs(c[1]-d[1]) < 1e-8 and abs(a[1]-c[1]) < 1e-8:
                    assert min(max(a[0], b[0]), max(c[0], d[0])) <= max(min(a[0], b[0]), min(c[0], d[0])) + 1e-8
                if abs(a[0]-b[0]) < 1e-8 and abs(c[0]-d[0]) < 1e-8 and abs(a[0]-c[0]) < 1e-8:
                    assert min(max(a[1], b[1]), max(c[1], d[1])) <= max(min(a[1], b[1]), min(c[1], d[1])) + 1e-8
    for index, left in enumerate(plan["routes"]):
        left_inner = {tuple(point) for point in left["points"][1:-1]}
        for right in plan["routes"][index + 1:]:
            assert not left_inner & {tuple(point) for point in right["points"][1:-1]}


@pytest.mark.parametrize("width", [85.0, 180.0])
def test_parallel_agents_share_a_layer_and_feedback_is_external(base_spec, width):
    from figure_agent.layouts import build_route_plan
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=width)
    p = plan["positions"]
    axis = 0 if width == 180 else 1
    assert p["node_1"][axis] == p["node_2"][axis]
    assert p["node_0"][axis] != p["node_1"][axis] != p["node_3"][axis]
    assert [r["role"] for r in plan["routes"]] == ["forward"] * 4 + ["feedback"]


def test_roles_survive_array_order_and_label_changes(base_spec):
    from figure_agent.layouts import build_route_plan
    base_spec["nodes"].reverse()
    base_spec["edges"].reverse()
    for node in base_spec["nodes"]:
        node["label"] = "renamed " + node["id"]
    base_spec["edges"].append({"source": "node_0", "target": "node_3", "type": "control_flow", "label": "approved"})
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180)
    roles = {(r["source"], r["target"]): r["role"] for r in plan["routes"]}
    assert roles["node_3", "node_1"] == "feedback"
    assert roles["node_0", "node_3"] == "forward"


def test_three_branches_have_independent_ports_and_channels(base_spec):
    from figure_agent.layouts import build_route_plan
    base_spec["nodes"].append({"id": "extra", "label": "第三代理", "type": "process"})
    base_spec["edges"].extend([
        {"source": "node_0", "target": "extra", "type": "data_flow"},
        {"source": "extra", "target": "node_3", "type": "data_flow"},
    ])
    for width in (85, 180):
        assert_independent_routes(build_route_plan(base_spec, family="swimlane", paper_width_mm=width))


def test_two_conditions_on_same_endpoints_remain_distinct(base_spec):
    from figure_agent.layouts import build_route_plan
    extra = deepcopy(base_spec["edges"][-1])
    extra["label"] = "若存在矛盾"
    base_spec["edges"].append(extra)
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180)
    assert len(plan["routes"]) == 6
    assert_independent_routes(plan)


@pytest.mark.parametrize("width", [85.0, 180.0])
def test_route_plan_inspection_accepts_final_size_geometry(base_spec, width):
    from figure_agent.layouts import build_route_plan
    from figure_agent.visual_critic import inspect_route_plan
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=width)
    codes = {f["code"] for f in inspect_route_plan(plan)}
    assert not codes & {"edge_port_crowding", "edge_label_clearance", "edge_visual_merge",
                        "edge_reverse_overlap", "edge_crossing", "edge_self_overlap",
                        "edge_crosses_node", "routing_unresolved"}
    labels = [r["label_box"] for r in plan["routes"] if r["label_box"]]
    assert len(labels) == 1
    assert labels[0]["text"] == "若证据不足"
    assert labels[0]["font_size_pt"] >= 8.0
    from figure_agent.layouts import _segments, segment_box_distance
    label_box = plan["routes"][4]["label_box"]["box"]
    assert min(segment_box_distance(a, b, label_box) for a, b in _segments(plan["routes"][4]["points"])) * plan["mm_per_unit"] >= 1.0


def test_pipeline_feedback_label_clears_figure_title(base_spec):
    from figure_agent.layouts import box_distance, build_route_plan
    from figure_agent.visual_critic import inspect_route_plan
    plan = build_route_plan(base_spec, family="pipeline", paper_width_mm=180.0)
    assert not {f["code"] for f in inspect_route_plan(plan)} & {"edge_label_clearance", "edge_self_overlap"}
    label_box = plan["routes"][4]["label_box"]["box"]
    assert box_distance(label_box, plan["title"]["box"]) * plan["mm_per_unit"] >= 1.0


def test_fault_injected_label_is_reported(base_spec):
    from figure_agent.layouts import build_route_plan
    from figure_agent.visual_critic import inspect_route_plan
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180)
    label = plan["routes"][4]["label_box"]
    plan["routes"][4]["label_box"] = {**label, "box": plan["routes"][2]["label_box"]["box"] if plan["routes"][2]["label_box"] else plan["node_boxes"]["node_3"]}
    assert "edge_label_clearance" in {f["code"] for f in inspect_route_plan(plan)}


def test_fault_injected_shared_port_is_reported(base_spec):
    from figure_agent.layouts import build_route_plan
    from figure_agent.visual_critic import inspect_route_plan
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180)
    plan["routes"][1]["source_port"] = {**plan["routes"][1]["source_port"], "point": plan["routes"][0]["source_port"]["point"]}
    assert "edge_port_crowding" in {f["code"] for f in inspect_route_plan(plan)}


@pytest.mark.parametrize("width", [85.0, 180.0])
def test_route_plan_preview_has_exact_physical_width(base_spec, tmp_path, width):
    from PIL import Image
    from figure_agent.layouts import build_route_plan
    from figure_agent.backends.drawio_backend import render_route_plan_preview
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=width)
    output = render_route_plan_preview(base_spec, plan, tmp_path, stem=f"after-{int(width)}")
    assert output["png"].exists() and output["svg"].exists() and output["pdf"].exists()
    image = Image.open(output["png"])
    assert abs(image.width / image.height - width / ((plan["bounds"][3]-plan["bounds"][1])*plan["mm_per_unit"])) < 0.03


def test_all_editable_outputs_consume_one_route_plan(base_spec, tmp_path):
    from figure_agent.backends.drawio_backend import build_drawio_xml, render_drawio_spec
    from figure_agent.backends.figma_backend import compile_figma_scene
    from figure_agent.layouts import build_route_plan
    from figure_agent.parity import compare_semantics, extract_drawio_semantics, extract_figma_semantics
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0)
    xml = build_drawio_xml(base_spec, route_plan=plan)
    outputs = render_drawio_spec(base_spec, tmp_path, "figure", route_plan=plan)
    scene = compile_figma_scene(base_spec, route_plan=plan)
    assert len(plan["routes"]) == 5
    assert set(outputs) == {"drawio", "svg", "pdf", "png"}
    assert all(path.is_file() and path.stat().st_size > 0 for path in outputs.values())
    assert "若证据不足" in xml
    assert compare_semantics(base_spec, extract_drawio_semantics(outputs["drawio"])) == []
    shape_edges = [n for n in scene["nodes"] if n.get("source") and n.get("target")]
    assert len(shape_edges) == 5
    for expected, actual in zip(plan["routes"], shape_edges):
        assert (actual["source"], actual["target"]) == (expected["source"], expected["target"])
        assert len(actual["points"]) == len(expected["points"])
        assert actual["label"] == base_spec["edges"][expected["edge_index"]].get("label", "")
    assert compare_semantics(base_spec, extract_figma_semantics(scene)) == []


def test_editable_route_points_preserve_multiplicity(base_spec):
    from figure_agent.backends.figma_backend import compile_figma_scene
    from figure_agent.layouts import build_route_plan
    from figure_agent.parity import compare_semantics, extract_figma_semantics
    duplicate = deepcopy(base_spec["edges"][-1])
    duplicate["label"] = "若存在矛盾"
    base_spec["edges"].append(duplicate)
    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0)
    scene = compile_figma_scene(base_spec, route_plan=plan)
    shape_edges = [n for n in scene["nodes"] if n.get("source") and n.get("target")]
    assert len(shape_edges) == 6
    assert compare_semantics(base_spec, extract_figma_semantics(scene)) == []


def _style_value(style, key):
    match = re.search(rf"(?:^|;){re.escape(key)}=([^;]+)", style)
    assert match, f"{key} missing from Draw.io style: {style}"
    return float(match.group(1))


@pytest.mark.parametrize("family", ["pipeline", "swimlane", "hierarchy", "loop"])
def test_drawio_native_ports_match_serialized_route_endpoints(base_spec, family):
    """Native Draw.io ports must describe the same screen-space endpoints as data-route-points."""
    from figure_agent.backends.drawio_backend import build_drawio_xml
    from figure_agent.layouts import build_route_plan

    plan = build_route_plan(base_spec, family=family, paper_width_mm=180.0)
    root = ET.fromstring(build_drawio_xml(base_spec, route_plan=plan))
    geometries = {
        cell.get("id"): cell.find("mxGeometry")
        for cell in root.findall(".//mxCell[@vertex='1']")
    }
    for route in plan["routes"]:
        edge = root.find(f".//mxCell[@id='edge-{route['edge_index']}']")
        assert edge is not None
        recorded = json.loads(edge.get("data-route-points"))
        for prefix, node_id, expected in (
            ("exit", route["source"], recorded[0]),
            ("entry", route["target"], recorded[-1]),
        ):
            geometry = geometries[node_id]
            x = float(geometry.get("x"))
            y = float(geometry.get("y"))
            width = float(geometry.get("width"))
            height = float(geometry.get("height"))
            actual = (
                x + _style_value(edge.get("style"), f"{prefix}X") * width,
                y + _style_value(edge.get("style"), f"{prefix}Y") * height,
            )
            assert math.dist(actual, tuple(expected)) <= 0.01, (
                f"{family} edge {route['edge_index']} {prefix} port {actual} "
                f"does not match route endpoint {expected}"
            )


def test_svg_node_geometry_preserves_route_plan_physical_scale(base_spec, tmp_path):
    """The final SVG must retain the RoutePlan millimetre scale inside its canvas."""
    from figure_agent.backends.drawio_backend import render_route_plan_preview
    from figure_agent.layouts import build_route_plan

    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0)
    output = render_route_plan_preview(base_spec, plan, tmp_path, stem="physical-scale")
    root = ET.fromstring(output["svg"].read_text(encoding="utf-8"))
    namespace = "{http://www.w3.org/2000/svg}"
    node_paths = []
    for path in root.iter(f"{namespace}path"):
        if "fill: #dbeafe" not in (path.get("style") or ""):
            continue
        values = [float(value) for value in re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", path.get("d") or "")]
        xs, ys = values[0::2], values[1::2]
        node_paths.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    assert len(node_paths) == len(base_spec["nodes"])
    # The first and last nodes are stable in the fixture and avoid relying on
    # text glyph extraction, which differs between font installations.
    actual_pt = math.dist(node_paths[0], node_paths[-1])
    expected_pt = (math.dist(plan["positions"]["node_0"], plan["positions"]["node_3"])
                   * plan["mm_per_unit"] * 72 / 25.4)
    assert math.isclose(actual_pt, expected_pt, rel_tol=0.01, abs_tol=0.5)


def test_feedback_label_is_nearest_to_its_own_route(base_spec):
    from figure_agent.layouts import _segments, build_route_plan, segment_box_distance

    plan = build_route_plan(base_spec, family="pipeline", paper_width_mm=180.0)
    feedback = plan["routes"][4]
    label_box = feedback["label_box"]["box"]
    own = min(segment_box_distance(a, b, label_box) for a, b in _segments(feedback["points"]))
    other = min(
        segment_box_distance(a, b, label_box)
        for route in plan["routes"][:4]
        for a, b in _segments(route["points"])
    )
    assert own * plan["mm_per_unit"] + 0.25 <= other * plan["mm_per_unit"]


def test_group_title_has_clearance_from_every_route(base_spec):
    from figure_agent.layouts import _segments, build_route_plan, segment_box_distance
    from figure_agent.visual_critic import inspect_route_plan

    plan = build_route_plan(base_spec, family="pipeline", paper_width_mm=180.0)
    assert "edge_group_title_clearance" not in {f["code"] for f in inspect_route_plan(plan)}
    for title in plan["group_titles"]:
        clearance = min(
            segment_box_distance(a, b, title["box"]) * plan["mm_per_unit"]
            for route in plan["routes"]
            for a, b in _segments(route["points"])
        )
        assert clearance >= 1.2


def _group_box_children(spec, group_id):
    for group in spec.get("groups", []):
        if group["id"] == group_id:
            return group["children"]
    raise AssertionError(f"group {group_id} missing from spec")


@pytest.mark.parametrize("family", ["pipeline", "swimlane", "hierarchy", "loop"])
def test_drawio_group_rectangles_are_positive_and_bound_their_nodes(base_spec, family):
    """F1: group cells must serialize as positive-extent rectangles enclosing their nodes.

    ``_drawio_point`` flips y, so the transformed corners arrive swapped. The
    serialized rectangle must be normalized after the transform rather than
    taking the raw corner order.
    """
    from figure_agent.backends.drawio_backend import build_drawio_xml
    from figure_agent.layouts import build_route_plan

    plan = build_route_plan(base_spec, family=family, paper_width_mm=180.0)
    root = ET.fromstring(build_drawio_xml(base_spec, route_plan=plan))
    node_geometries = {
        cell.get("id"): cell.find("mxGeometry")
        for cell in root.findall(".//mxCell[@vertex='1']")
    }
    groups = [c for c in root.findall(".//mxCell[@vertex='1']") if str(c.get("id")).startswith("group-")]
    assert groups, "expected at least one serialized group cell"
    for cell in groups:
        geometry = cell.find("mxGeometry")
        x = float(geometry.get("x"))
        y = float(geometry.get("y"))
        width = float(geometry.get("width"))
        height = float(geometry.get("height"))
        assert width > 0, f"{family} {cell.get('id')} width must be positive, got {width}"
        assert height > 0, f"{family} {cell.get('id')} height must be positive, got {height}"

        spec_group = next(g for g in base_spec["groups"] if g["label"] == cell.get("value"))
        for node_id in spec_group["children"]:
            node = node_geometries[node_id]
            nx, ny = float(node.get("x")), float(node.get("y"))
            nw, nh = float(node.get("width")), float(node.get("height"))
            assert x <= nx and nx + nw <= x + width, (
                f"{family} {cell.get('id')} does not horizontally enclose {node_id}"
            )
            assert y <= ny and ny + nh <= y + height, (
                f"{family} {cell.get('id')} does not vertically enclose {node_id}"
            )


def test_reviewed_candidate_02_group_rectangle_matches_normalized_values(base_spec):
    """F1 fixed regression: the reviewed candidate_02 rectangle, not a universal constant."""
    from figure_agent.backends.drawio_backend import build_drawio_xml
    from figure_agent.layouts import build_route_plan

    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0)
    root = ET.fromstring(build_drawio_xml(base_spec, route_plan=plan))
    cell = next(c for c in root.findall(".//mxCell[@vertex='1']") if str(c.get("id")).startswith("group-"))
    geometry = cell.find("mxGeometry")
    actual = tuple(round(float(geometry.get(k)), 3) for k in ("x", "y", "width", "height"))
    assert actual == (50.5, 88.375, 1035.25, 382.5), (
        f"reviewed candidate_02 group rectangle regressed: {actual}"
    )


MINIMAL_LABEL_CASES = [
    # name, polyline in native draw.io coordinates, intended label anchor
    ("horizontal_forward", [(0.0, 0.0), (100.0, 0.0)], (50.0, 20.0)),
    ("horizontal_reverse", [(100.0, 0.0), (0.0, 0.0)], (50.0, 20.0)),
    ("vertical_forward", [(0.0, 0.0), (0.0, 100.0)], (20.0, 50.0)),
    ("vertical_reverse", [(0.0, 100.0), (0.0, 0.0)], (20.0, 50.0)),
    ("polyline_corner", [(0.0, 0.0), (100.0, 0.0), (100.0, 80.0)], (112.0, 40.0)),
    ("polyline_z", [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0), (140.0, 60.0)], (60.0, -25.0)),
    ("fractional_along_edge", [(0.0, 0.0), (101.0, 0.0)], (50.25, 0.0)),
    ("negative_along_edge", [(0.0, 0.0), (200.0, 0.0)], (25.0, -13.5)),
    ("diagonal", [(0.0, 0.0), (100.0, 100.0)], (30.0, 80.0)),
    # zero perpendicular offset: passes even under an inverted normal, so it is
    # the control that proves the other cases fail for the sign and not the setup
    ("zero_normal_control", [(0.0, 0.0), (100.0, 0.0)], (50.0, 0.0)),
]


@pytest.mark.parametrize("name,points,anchor", MINIMAL_LABEL_CASES,
                         ids=[c[0] for c in MINIMAL_LABEL_CASES])
def test_label_geometry_round_trips_through_official_getpoint(name, points, anchor):
    """F2 root cause: the encoded normal must match mxGraph's, not oppose it.

    The oracle is ``mxgraph_getpoint_reference.get_point``, a transcription of
    upstream ``mxGraphView.prototype.getPoint``. It shares no code with the
    encoder, so agreement here cannot come from two copies of the same mistake
    cancelling out. Before the fix, ``horizontal_forward`` encoded y=+20 and this
    oracle resolved it to (50, -20) -- 40 units away from the planned anchor.
    """
    from figure_agent.backends.drawio_backend import _label_geometry_attrs

    from mxgraph_getpoint_reference import get_point

    attrs, offset = _label_geometry_attrs(anchor, points)
    assert attrs and offset, f"{name}: encoder produced no native geometry"

    geometry = ET.fromstring(f"<mxGeometry relative=\"1\"{attrs}>{offset}</mxGeometry>")
    relative_x, perpendicular, label_offset = _native_geometry_fields(geometry)
    actual = get_point(points, relative_x, perpendicular, label_offset)
    assert math.dist(actual, anchor) <= 0.01, (
        f"{name}: official getPoint resolves the serialized geometry to {actual}, "
        f"but the planned anchor is {anchor}"
    )
    _assert_perpendicular_carries_the_offset(name, points, anchor, relative_x,
                                             perpendicular, label_offset)


def test_official_getpoint_reference_rejects_the_inverted_normal():
    """Guard the oracle itself: it must disagree with the old, mirrored normal.

    If someone re-introduces ``normal = (-uy, ux)`` the encoder would emit y=+20
    for this anchor. The oracle has to place that at (50, -20); an oracle that
    accepted both signs would make the tests above vacuous.
    """
    from mxgraph_getpoint_reference import get_point

    assert get_point([(0.0, 0.0), (100.0, 0.0)], 0.0, 20.0, (0.0, 0.0)) == (50.0, -20.0)
    assert get_point([(0.0, 0.0), (100.0, 0.0)], 0.0, -20.0, (0.0, 0.0)) == (50.0, 20.0)


def test_official_getpoint_reference_rounds_along_edge_distance_like_javascript():
    """``dist = Math.round((gx + 0.5) * state.length)`` runs before segment pick.

    On an odd-length edge the native midpoint is therefore *not* the geometric
    midpoint: a 101-unit edge rounds 50.5 up to 51. Any encoder that assumes the
    geometric midpoint drifts by up to half a unit per label, which is why
    ``_label_geometry_attrs`` measures its perpendicular against this rule and
    lets ``mxPoint as="offset"`` absorb the rounding residual.
    """
    from mxgraph_getpoint_reference import get_point, js_round, segments_of

    assert js_round(0.5) == 1 and js_round(1.5) == 2 and js_round(-0.5) == 0

    points = [(0.0, 0.0), (101.0, 0.0)]
    _, total = segments_of(points)
    assert total == 101.0
    assert get_point(points, 0.0, 0.0) == (51.0, 0.0), (
        "native mid-edge label follows Math.round(0.5 * length), not length / 2"
    )
    # unrounded arithmetic would land here, so the rounding really is in effect
    assert total / 2.0 == 50.5


def _native_geometry_fields(geometry):
    """Read the native mxGraph label fields straight off serialized XML."""
    relative_x = float(geometry.get("x") or 0.0)
    perpendicular = float(geometry.get("y") or 0.0)
    offset = geometry.find("mxPoint[@as='offset']")
    offset_x = float(offset.get("x") or 0.0) if offset is not None else 0.0
    offset_y = float(offset.get("y") or 0.0) if offset is not None else 0.0
    return (relative_x, perpendicular, (offset_x, offset_y))


def test_drawio_feedback_label_uses_native_label_geometry(base_spec):
    """F2: the RoutePlan label anchor must reach native edge label geometry.

    mxGraph places an edge label from ``geometry.relative``: x is the position
    along the edge in [-1, 1] (0 = centre), y is the perpendicular offset, and
    ``mxPoint as="offset"`` shifts it further. Recomputing the label centre from
    those native fields must land on the shared RoutePlan anchor; the
    ``data-label-*`` attributes are kept for cross-checking but cannot stand in
    for native geometry.
    """
    from figure_agent.backends.drawio_backend import build_drawio_xml
    from figure_agent.layouts import build_route_plan

    from mxgraph_getpoint_reference import get_point

    plan = build_route_plan(base_spec, family="swimlane", paper_width_mm=180.0)
    root = ET.fromstring(build_drawio_xml(base_spec, route_plan=plan))
    labelled = [r for r in plan["routes"] if r["label_box"]]
    assert labelled, "fixture must carry at least one conditional label"

    for route in labelled:
        edge = root.find(f".//mxCell[@id='edge-{route['edge_index']}']")
        assert edge is not None
        assert edge.get("value"), "conditional text must survive serialization"
        geometry = edge.find("mxGeometry")
        assert geometry.get("relative") == "1"

        expected = _drawio_point_for_test(route["label_box"]["anchor"], plan)
        points = [_drawio_point_for_test(p, plan) for p in route["points"]]
        relative_x, perpendicular, label_offset = _native_geometry_fields(geometry)
        actual = get_point(points, relative_x, perpendicular, label_offset)
        assert math.dist(actual, expected) <= 0.01, (
            f"edge {route['edge_index']} native label centre {actual} does not "
            f"match RoutePlan anchor {expected}"
        )
        _assert_perpendicular_carries_the_offset(
            f"edge {route['edge_index']}", points, expected, relative_x,
            perpendicular, label_offset)


def _drawio_point_for_test(point, plan):
    left, bottom, right, top = plan["bounds"]
    return (round((point[0] - left) * 100, 3), round((top - point[1]) * 100, 3))


def _official_foot_and_normal(points, relative_x):
    """Foot point and unit normal mxGraph itself uses, probed from the oracle.

    Both come from ``get_point`` rather than from any expression in the encoder,
    so a test built on them cannot be satisfied by an encoder that mirrors the
    normal and hides the difference in ``offset``.
    """
    from mxgraph_getpoint_reference import get_point

    foot = get_point(points, relative_x, 0.0)
    unit = get_point(points, relative_x, 1.0)
    return foot, (unit[0] - foot[0], unit[1] - foot[1])


def _assert_perpendicular_carries_the_offset(name, points, anchor, relative_x,
                                             perpendicular, label_offset):
    """The label must sit on the anchor *and* do it the way mxGraph intends.

    Landing on the anchor is not sufficient evidence of a correct normal: an
    inverted normal still round-trips, because ``offset`` then quietly carries
    twice the perpendicular. So assert the two things an inverted normal breaks:

    * ``geometry.y`` equals the anchor's displacement projected on the *official*
      normal, sign included;
    * ``offset`` never exceeds what the native rule genuinely cannot express,
      which is bounded by the anchor's distance from the native foot point.
    """
    foot, normal = _official_foot_and_normal(points, relative_x)
    expected_y = ((anchor[0] - foot[0]) * normal[0]
                  + (anchor[1] - foot[1]) * normal[1])
    assert abs(perpendicular - expected_y) <= 0.01, (
        f"{name}: geometry.y is {perpendicular} but the official normal {normal} "
        f"puts the anchor at {expected_y} -- the encoded normal is misaligned"
    )
    residual = math.dist(anchor, foot)
    assert math.hypot(*label_offset) <= residual + 0.01, (
        f"{name}: offset {label_offset} is larger than the {residual:.4f} the "
        "native rule cannot express, so geometry.y is not carrying the "
        "perpendicular displacement"
    )
