from __future__ import annotations

import html
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, Polygon
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.font_manager import FontProperties

from ..layouts import layout_edges, layout_nodes, node_size_px
from ..visual_styles import get_visual_style

REQUIRED_LABELS = [
    "User Query",
    "Planner",
    "Tool Selection",
    "Environment",
    "Observation",
    "Search Tool",
    "Code Tool",
    "Reflection",
    "Answer",
]

# Keep Chinese labels editable in Draw.io and render them correctly in the preview.
plt.rcParams["font.sans-serif"] = ["Noto Sans SC", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"
# Type 3 embeds glyph outlines instead of declaring an incompatible TrueType
# wrapper. Keep the save operation scoped too: other backends set rcParams.
plt.rcParams["pdf.fonttype"] = 3


def check_drawio_output(path: str | Path, required_labels: list[str] | None = None) -> list[str]:
    path = Path(path)
    if not path.exists():
        return [f"artifact does not exist: {path}"]
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as exc:
        return [f"invalid drawio XML: {exc}"]
    text = " ".join(root.itertext()) + " " + " ".join(
        value for element in root.iter() for value in element.attrib.values()
    )
    labels = REQUIRED_LABELS if required_labels is None else required_labels
    errors = [f"missing required label: {label}" for label in labels if label not in text]
    if not root.findall(".//mxCell[@edge='1']"):
        errors.append("no editable edge cells found")
    if not root.findall(".//mxCell[@vertex='1']"):
        errors.append("no editable vertex cells found")
    return errors


def _drawio_point(point: tuple[float, float], route_plan: dict[str, Any]) -> tuple[float, float]:
    left, bottom, right, top = route_plan["bounds"]
    return (round((point[0] - left) * 100, 3), round((top - point[1]) * 100, 3))


def _js_round(value: float) -> float:
    """``Math.round`` semantics: exact halves go towards +Infinity."""
    return math.floor(value + 0.5)


def _edge_segments(points: list[tuple[float, float]]) -> tuple[list[float], float]:
    """Reproduce ``mxCellState.segments`` / ``mxCellState.length``."""
    segments = [math.dist(a, b) for a, b in zip(points, points[1:])]
    return segments, sum(segments)


def _wrap_label(text: str, max_width_mm: float, font_size_pt: float, font_path: str | None = None) -> str:
    """Greedily wrap a label so its rendered ink fits a final-size node box."""
    value = str(text)
    if not value or max_width_mm <= 0:
        return value
    font = FontProperties(fname=font_path, size=font_size_pt) if font_path else FontProperties(size=font_size_pt)
    renderer = RendererAgg(1, 1, 72)

    def width(line: str) -> float:
        measured, _, _ = renderer.get_text_width_height_descent(line, font, False)
        return measured * 25.4 / 72

    if width(value) <= max_width_mm:
        return value
    lines: list[str] = []
    current = ""
    for char in value:
        candidate = current + char
        if current and width(candidate) > max_width_mm:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


def _native_label_point(points: list[tuple[float, float]],
                        geometry_x: float,
                        geometry_y: float,
                        offset: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    """Resolve a relative edge-label geometry the way mxGraph does.

    Transcribed from ``mxGraphView.prototype.getPoint`` (jgraph/mxgraph,
    ``javascript/src/js/view/mxGraphView.js``) so that the encoder below can
    invert the exact native rule::

        var dist = Math.round((gx + 0.5) * state.length);
        while (dist >= Math.round(length + segment) && index < pointCount - 1) ...
        var nx = (segment == 0) ? 0 : dy / segment;
        var ny = (segment == 0) ? 0 : dx / segment;
        x = p0.x + dx * factor + (nx * gy + offsetX) * this.scale;
        y = p0.y + dy * factor - (ny * gy - offsetY) * this.scale;

    The normal applied to ``gy`` is therefore ``(dy/segment, -dx/segment)``,
    i.e. ``(+uy, -ux)`` in screen coordinates, and the along-edge distance is
    rounded to a whole number *before* the segment is chosen. The document is
    written at scale 1, so ``this.scale`` is omitted.
    """
    segments, total = _edge_segments(points)
    gx = geometry_x / 2.0
    point_count = len(points)
    dist = _js_round((gx + 0.5) * total)
    segment = segments[0]
    length = 0.0
    index = 1
    while dist >= _js_round(length + segment) and index < point_count - 1:
        length += segment
        segment = segments[index]
        index += 1
    factor = 0.0 if segment == 0 else (dist - length) / segment
    p0 = points[index - 1]
    pe = points[index]
    dx = pe[0] - p0[0]
    dy = pe[1] - p0[1]
    nx = 0.0 if segment == 0 else dy / segment
    ny = 0.0 if segment == 0 else dx / segment
    return (p0[0] + dx * factor + (nx * geometry_y + offset[0]),
            p0[1] + dy * factor - (ny * geometry_y - offset[1]))


def _label_geometry_attrs(anchor: tuple[float, float],
                          points: list[tuple[float, float]]) -> tuple[str, str]:
    """Encode a RoutePlan label anchor as native mxGraph edge-label geometry.

    For a relative edge geometry mxGraph resolves the label from ``x`` (position
    along the edge in [-1, 1], 0 being the centre), ``y`` (perpendicular offset
    along ``(+uy, -ux)``) and an optional ``mxPoint as="offset"``. The anchor is
    projected onto the saved polyline to recover ``x`` and ``y``; because the
    native rule rounds the along-edge distance to a whole number, the remaining
    residual is absorbed by ``offset`` so that the editor reproduces the planned
    point exactly. ``data-label-*`` is still written, but only as cross-check
    metadata.
    """
    points = [(float(px), float(py)) for px, py in points]
    if len(points) < 2:
        return ("", "")
    segments, total = _edge_segments(points)
    if total <= 0:
        return ("", "")

    best: tuple[float, float] | None = None
    travelled = 0.0
    for (a, b), length in zip(zip(points, points[1:]), segments):
        if length > 0:
            ratio = ((anchor[0] - a[0]) * (b[0] - a[0]) + (anchor[1] - a[1]) * (b[1] - a[1])) / (length * length)
            ratio = min(1.0, max(0.0, ratio))
            foot = (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)
            distance = math.dist(anchor, foot)
            if best is None or distance < best[0]:
                best = (distance, travelled + length * ratio)
        travelled += length
    if best is None:
        return ("", "")

    relative_x = round(min(1.0, max(-1.0, (best[1] / total) * 2.0 - 1.0)), 6)

    # Measure the perpendicular on the segment the *native* rule selects for this
    # relative_x, not on the nearest-projection segment: rounding can move it.
    foot = _native_label_point(points, relative_x, 0.0)
    direction = _native_label_point(points, relative_x, 1.0)
    normal = (direction[0] - foot[0], direction[1] - foot[1])
    perpendicular = round((anchor[0] - foot[0]) * normal[0] + (anchor[1] - foot[1]) * normal[1], 3)

    base = _native_label_point(points, relative_x, perpendicular)
    offset_x = round(anchor[0] - base[0], 3)
    offset_y = round(anchor[1] - base[1], 3)

    attrs = f' x="{relative_x}" y="{perpendicular}"'
    offset = f'<mxPoint x="{offset_x}" y="{offset_y}" as="offset" />'
    return (attrs, offset)


def _normalized_rect(corner_a: tuple[float, float], corner_b: tuple[float, float]) -> tuple[float, float, float, float]:
    """Normalize two transformed corners into an mxGeometry rectangle.

    ``_drawio_point`` flips y, so the corners arrive with their vertical order
    swapped. ``mxGeometry`` defines a vertex by position plus extent, so the
    rectangle is rebuilt after the transform instead of reusing the incoming
    corner order; taking ``abs`` of the height alone would keep the wrong y.
    """
    x1, y1 = corner_a
    x2, y2 = corner_b
    return (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


def _port_style(port: dict[str, Any], prefix: str, geometry: tuple[float, float, float, float],
                route_plan: dict[str, Any]) -> str:
    """Serialize a port from the same screen-space endpoint as the route.

    RoutePlan coordinates grow upwards while Draw.io geometry grows downwards.
    Deriving the normalized port from the serialized geometry keeps the native
    ``entry/exit`` coordinates aligned with ``data-route-points`` for every
    side, including north/south ports.
    """
    x, y, width, height = geometry
    point_x, point_y = _drawio_point(tuple(port["point"]), route_plan)
    normalized_x = min(1.0, max(0.0, (point_x - x) / width))
    normalized_y = min(1.0, max(0.0, (point_y - y) / height))
    return (f"{prefix}X={normalized_x:.6f};{prefix}Y={normalized_y:.6f};"
            f"{prefix}Perimeter=1;")


def _build_drawio_xml_from_plan(spec: dict[str, Any], route_plan: dict[str, Any]) -> str:
    """Serialize the exact RoutePlan geometry into editable mxGraph cells."""
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    node_width, node_height = route_plan.get("node_size_px", node_size_px(spec))
    group_by_node = {child: group["id"] for group in spec.get("groups", []) for child in group["children"]}
    node_geometries: dict[str, tuple[float, float, float, float]] = {}
    for index, node in enumerate(spec["nodes"], start=2):
        center = _drawio_point(route_plan["positions"][node["id"]], route_plan)
        x, y = center[0] - node_width / 2, center[1] - node_height / 2
        geometry = (round(x, 3), round(y, 3), round(node_width, 3), round(node_height, 3))
        node_geometries[node["id"]] = geometry
        style_config = spec.get("style", {})
        color = style_config.get("colors", {}).get(node.get("type"), "#E8EEF7")
        stroke = style_config.get("stroke", "#64748B")
        font_family = style_config.get("font_family", "Noto Sans SC")
        font_size = style_config.get("font_sizes", {}).get("node", 14)
        style = f"rounded=1;shape={style_config.get('shape', 'rounded')};whiteSpace=wrap;html=1;fillColor={color};strokeColor={stroke};fontFamily={font_family};fontSize={font_size};fontColor=#172033;"
        label = html.escape(str(node["label"]), quote=True)
        group_attribute = f' data-group="{html.escape(group_by_node[node["id"]], quote=True)}"' if node["id"] in group_by_node else ""
        cells.append(f'<mxCell id="{node["id"]}" value="{label}" style="{style}" vertex="1" parent="1"{group_attribute}><mxGeometry x="{geometry[0]}" y="{geometry[1]}" width="{geometry[2]}" height="{geometry[3]}" as="geometry"/></mxCell>')
    for group_index, group in enumerate(spec.get("groups", []), start=500):
        box = route_plan.get("group_boxes", {}).get(group["id"])
        if not box:
            continue
        left, top = _drawio_point((box[0], box[3]), route_plan)
        right, bottom = _drawio_point((box[2], box[1]), route_plan)
        x1, y1, group_width, group_height = _normalized_rect((left, top), (right, bottom))
        label = html.escape(str(group["label"]), quote=True)
        style_config = spec.get("style", {})
        cells.append(f'<mxCell id="group-{group_index}" value="{label}" style="swimlane;html=1;rounded=1;dashed=1;fillColor={style_config.get("group_fill", "#F8FAFC")};fillOpacity=20;strokeColor={style_config.get("stroke", "#94A3B8")};fontFamily={style_config.get("font_family", "Noto Sans SC")};fontSize=12;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{round(x1, 3)}" y="{round(y1, 3)}" width="{round(group_width, 3)}" height="{round(group_height, 3)}" as="geometry"/></mxCell>')
    for route, edge in zip(route_plan["routes"], spec.get("edges", [])):
        points = route.get("points", [])
        intermediate = "".join(f'<mxPoint x="{point[0]}" y="{point[1]}" />' for point in (_drawio_point(p, route_plan) for p in points[1:-1]))
        data_points = html.escape(json.dumps([_drawio_point(p, route_plan) for p in points], separators=(",", ":")), quote=True)
        label = html.escape(str(edge.get("label", "")), quote=True)
        label_box = route.get("label_box")
        label_data = ""
        label_attrs, label_offset = "", ""
        if label_box:
            lx, ly = _drawio_point(label_box["anchor"], route_plan)
            label_data = f' data-label-x="{lx}" data-label-y="{ly}" data-label-box="{html.escape(json.dumps(label_box["box"], separators=(",", ":")), quote=True)}"'
            label_attrs, label_offset = _label_geometry_attrs((lx, ly), [_drawio_point(p, route_plan) for p in points])
        style = ("edgeStyle=none;orthogonal=0;noEdgeStyle=1;rounded=0;endArrow=block;"
                 f"strokeColor={spec.get('style', {}).get('arrow_color', '#64748B')};strokeWidth=1.5;labelBackgroundColor=#FFFFFF;"
                 + _port_style(route["source_port"], "exit", node_geometries[edge["source"]], route_plan)
                 + _port_style(route["target_port"], "entry", node_geometries[edge["target"]], route_plan))
        attrs = (f' data-route-points="{data_points}" data-role="{route["role"]}"'
                 f' data-source-port="{html.escape(json.dumps(route["source_port"], separators=(",", ":")), quote=True)}"'
                 f' data-target-port="{html.escape(json.dumps(route["target_port"], separators=(",", ":")), quote=True)}"'
                 f' data-fan-out="{str(route["fan_out"]).lower()}" data-fan-in="{str(route["fan_in"]).lower()}"{label_data}')
        cells.append(f'<mxCell id="edge-{route["edge_index"]}" value="{label}" edge="1" parent="1" source="{edge["source"]}" target="{edge["target"]}"{attrs} style="{style}"><mxGeometry relative="1"{label_attrs} as="geometry"><Array as="points">{intermediate}</Array>{label_offset}</mxGeometry></mxCell>')
    return '<mxfile host="Scientific Figure Agent"><diagram name="Agent Workflow"><mxGraphModel><root>' + "".join(cells) + '</root></mxGraphModel></diagram></mxfile>'


def build_drawio_xml(spec: dict[str, Any], *, route_plan: dict[str, Any] | None = None) -> str:
    if route_plan is not None:
        return _build_drawio_xml_from_plan(spec, route_plan)
    cells = [
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
    ]
    preview_positions = _layout(spec)
    positions = {node_id: (round(x * 100), round((6.2 - y) * 100)) for node_id, (x, y) in preview_positions.items()}
    group_by_node = {child: group["id"] for group in spec.get("groups", []) for child in group["children"]}
    for index, node in enumerate(spec["nodes"], start=2):
        x, y = positions[node["id"]]
        style_config = spec.get("style", {})
        color = style_config.get("colors", {}).get(node.get("type"), "#E8EEF7")
        stroke = style_config.get("stroke", "#64748B")
        font_family = style_config.get("font_family", "Noto Sans SC")
        font_size = style_config.get("font_sizes", {}).get("node", 14)
        shape = style_config.get("shape", "rounded")
        style = f"rounded=1;shape={shape};whiteSpace=wrap;html=1;fillColor={color};strokeColor={stroke};fontFamily={font_family};fontSize={font_size};fontColor=#172033;"
        label = html.escape(str(node["label"]), quote=True)
        group_attribute = f' data-group="{html.escape(group_by_node[node["id"]], quote=True)}"' if node["id"] in group_by_node else ""
        node_width, node_height = node_size_px(spec)
        node_width, node_height = round(node_width), round(node_height)
        x, y = x - node_width / 2, y - node_height / 2
        cells.append(f'<mxCell id="{node["id"]}" value="{label}" style="{style}" vertex="1" parent="1"{group_attribute}><mxGeometry x="{x}" y="{y}" width="{node_width}" height="{node_height}" as="geometry"/></mxCell>')
    for group_index, group in enumerate(spec.get("groups", []), start=500):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        node_width, node_height = node_size_px(spec)
        x, y = min(xs) - node_width / 2 - 35, min(ys) - node_height / 2 - 35
        width, height = max(xs) - min(xs) + node_width + 70, max(ys) - min(ys) + node_height + 70
        label = html.escape(str(group["label"]), quote=True)
        group_style = spec.get("style", {})
        group_fill = group_style.get("group_fill", "#F8FAFC")
        cells.append(f'<mxCell id="group-{group_index}" value="{label}" style="swimlane;html=1;rounded=1;dashed=1;fillColor={group_fill};fillOpacity=20;strokeColor={group_style.get("stroke", "#94A3B8")};fontFamily={group_style.get("font_family", "Noto Sans SC")};fontSize=12;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry"/></mxCell>')
    route_points = layout_edges(spec, preview_positions, family=_layout_family(spec))
    for index, edge in enumerate(spec["edges"], start=100):
        arrow_color = spec.get("style", {}).get("arrow_color", "#64748B")
        points = route_points[index - 100]
        intermediate = "".join(f'<mxPoint x="{round(point[0] * 100)}" y="{round((6.2 - point[1]) * 100)}" />' for point in points[1:-1])
        edge_label = html.escape(str(edge.get("label", "")), quote=True)
        cells.append(f'<mxCell id="edge-{index}" value="{edge_label}" edge="1" parent="1" source="{edge["source"]}" target="{edge["target"]}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=block;strokeColor={arrow_color};strokeWidth=1.5;labelBackgroundColor=#FFFFFF;"><mxGeometry relative="1" as="geometry"><Array as="points">{intermediate}</Array></mxGeometry></mxCell>')
    return '<mxfile host="Scientific Figure Agent"><diagram name="Agent Workflow"><mxGraphModel><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>"


def _layout(spec: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Return deterministic center positions in inches for preview and XML."""
    return layout_nodes(spec, family=_layout_family(spec))


def _layout_family(spec: dict[str, Any]) -> str:
    variant = spec.get("style", {}).get("variant", "editorial")
    return get_visual_style(variant).get("layout_family", "pipeline")


def _node_color(spec: dict[str, Any], node: dict[str, Any]) -> str:
    colors = spec.get("style", {}).get("colors", {})
    return colors.get(node.get("type"), "#E8EEF7")


def render_drawio_spec(spec: dict[str, Any], output_dir: str | Path, stem: str = "figure",
                       *, route_plan: dict[str, Any] | None = None) -> dict[str, Path]:
    """Render one validated Figure Spec to editable Draw.io plus SVG/PDF/PNG previews."""
    from figure_agent.spec import require_valid_spec

    require_valid_spec(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = output_dir / f"{stem}.drawio"
    drawio_path.write_text(build_drawio_xml(spec, route_plan=route_plan), encoding="utf-8")
    if route_plan is not None:
        preview = render_route_plan_preview(spec, route_plan, output_dir, stem)
        return {"drawio": drawio_path, **preview}

    positions = _layout(spec)
    route_points = layout_edges(spec, positions, family=_layout_family(spec))
    node_width, node_height = node_size_px(spec)
    node_half_width, node_half_height = node_width / 100 / 2, node_height / 100 / 2
    all_points = list(positions.values()) + [point for route in route_points for point in route]
    min_x = min((x for x, _ in all_points), default=0.0) - node_half_width - 0.45
    max_x = max((x for x, _ in all_points), default=2.0) + node_half_width + 0.45
    min_y = min((y for _, y in all_points), default=0.0) - node_half_height - 0.45
    max_y = max((y for _, y in all_points), default=2.0) + node_half_height + 0.75
    fig, ax = plt.subplots(figsize=(max(5.5, max_x), max(3.5, max_y)), constrained_layout=True)
    style_config = spec.get("style", {})
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.axis("off")
    for group_index, group in enumerate(spec.get("groups", [])):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        pad = 0.35
        style_config = spec.get("style", {})
        rect = Rectangle((min(xs) - node_half_width - pad, min(ys) - node_half_height - pad), max(xs) - min(xs) + 2 * node_half_width + 2 * pad, max(ys) - min(ys) + 2 * node_half_height + 2 * pad, fill=True, facecolor=style_config.get("group_fill", "#F8FAFC"), alpha=0.45, linestyle="--", linewidth=1.0, edgecolor=style_config.get("stroke", "#94A3B8"), zorder=0)
        ax.add_patch(rect)
        ax.text(min(xs) - 0.95, max(ys) + 0.5 + group_index * 0.28, group["label"], fontsize=8, color="#475569")
    for points in route_points:
        for start, end in zip(points, points[1:]):
            ax.plot([start[0], end[0]], [start[1], end[1]], color=style_config.get("arrow_color", "#475569"), linewidth=1.0, zorder=1)
        start, end = points[-2], points[-1]
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10, color=style_config.get("arrow_color", "#475569"), linewidth=1.0, zorder=2))
    for edge, points in zip(spec.get("edges", []), route_points):
        if edge.get("label"):
            mid = points[len(points) // 2]
            ax.text(mid[0], mid[1] + 0.12, edge["label"], ha="center", va="bottom", fontsize=style_config.get("font_sizes", {}).get("edge", 8), fontfamily=style_config.get("font_family", "Noto Sans SC"), color="#475569", bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5}, zorder=3)
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        style_config = spec.get("style", {})
        patch = FancyBboxPatch((x - node_half_width, y - node_half_height), node_half_width * 2, node_half_height * 2, boxstyle="round,pad=0,rounding_size=0.10", facecolor=_node_color(spec, node), edgecolor=style_config.get("stroke", "#64748B"), linewidth=1.2)
        ax.add_patch(patch)
        ax.text(x, y, node["label"], ha="center", va="center", fontsize=style_config.get("font_sizes", {}).get("node", 9), fontfamily=style_config.get("font_family", "Noto Sans SC"), color="#172033")
    if spec.get("title"):
        ax.set_title(spec["title"], fontsize=style_config.get("font_sizes", {}).get("title", 13), pad=12, fontfamily=style_config.get("font_family", "Noto Sans SC"), color="#172033", fontweight="bold")
    svg_path = output_dir / f"{stem}.svg"
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    fig.savefig(svg_path, format="svg")
    with matplotlib.rc_context({"pdf.fonttype": 3}):
        fig.savefig(pdf_path, format="pdf")
    fig.savefig(png_path, format="png", dpi=220)
    plt.close(fig)
    return {"drawio": drawio_path, "svg": svg_path, "pdf": pdf_path, "png": png_path}


def render_route_plan_preview(spec: dict[str, Any], route_plan: dict[str, Any], output_dir: str | Path,
                              stem: str = "figure") -> dict[str, Path]:
    """Render a RoutePlan at its requested physical width for Task 3 review.

    This preview deliberately does not change the native Draw.io/Figma
    serializers. It makes the proposed geometry visible at final size before
    those backends are adapted and checked against their native clients.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = float(route_plan["mm_per_unit"])
    left, bottom, right, top = route_plan["bounds"]
    width_mm = float(route_plan["paper_width_mm"])
    height_mm = max(35.0, (top-bottom)*scale)
    fig = plt.figure(figsize=(width_mm/25.4, height_mm/25.4), dpi=220)
    # Make one data unit map to the same physical length in the SVG/PDF/PNG.
    # ``plt.subplots`` reserves a default margin; with equal aspect that
    # shrinks the data rectangle to roughly 77% of the declared canvas.
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0, width_mm)
    ax.set_ylim(0, height_mm)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    style = spec.get("style", {})
    font_path = route_plan.get("font_path")
    font = FontProperties(fname=font_path) if font_path else None

    def xy(point):
        return ((point[0]-left)*scale, (point[1]-bottom)*scale)

    for box in route_plan.get("group_boxes", {}).values():
        x1, y1 = xy((box[0], box[1]))
        x2, y2 = xy((box[2], box[3]))
        ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, facecolor=style.get("group_fill", "#F8FAFC"),
                               edgecolor=style.get("stroke", "#94A3B8"), linestyle="--", linewidth=0.6, alpha=0.45, zorder=0))
    for title in route_plan.get("group_titles", []):
        ax.text(*xy(title["anchor"]), title["text"], fontsize=title["font_size_pt"], color="#475569",
                ha="center", va="center", fontproperties=font, zorder=4)
    for route in route_plan.get("routes", []):
        points = route.get("points", [])
        if len(points) < 2:
            continue
        display = [xy(point) for point in points]
        for start, end in zip(display, display[1:]):
            ax.plot([start[0], end[0]], [start[1], end[1]], color=style.get("arrow_color", "#56718C"),
                    linewidth=max(0.8, route_plan.get("line_width_pt", 0.8)), zorder=1)
        polygon = route.get("arrow_polygon", [])
        if polygon:
            ax.add_patch(Polygon([xy(point) for point in polygon], closed=True,
                                 facecolor=style.get("arrow_color", "#56718C"), edgecolor="none", zorder=2))
        label = route.get("label_box")
        if label:
            box = label["box"]
            x1, y1 = xy((box[0], box[1]))
            x2, y2 = xy((box[2], box[3]))
            ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, facecolor="white", edgecolor="none", zorder=2.5))
            ax.text(*xy(label["anchor"]), label["text"], fontsize=label["font_size_pt"], color="#475569",
                    ha="center", va="center", fontproperties=font, zorder=3)
    node_width, node_height = node_size_px(spec)
    node_width, node_height = node_width/100, node_height/100
    for node in spec.get("nodes", []):
        box = route_plan["node_boxes"][node["id"]]
        x1, y1 = xy((box[0], box[1]))
        x2, y2 = xy((box[2], box[3]))
        patch = FancyBboxPatch((x1, y1), x2-x1, y2-y1, boxstyle="round,pad=0,rounding_size=2.0",
                               facecolor=_node_color(spec, node), edgecolor=style.get("stroke", "#64748B"),
                               linewidth=0.8, zorder=3)
        ax.add_patch(patch)
        node_font_size = route_plan.get("node_font_size_pt", 8)
        wrapped = _wrap_label(node["label"], max(2.0, (x2 - x1) - 2.0), node_font_size, font_path)
        ax.text(*xy(route_plan["positions"][node["id"]]), wrapped,
                fontsize=node_font_size, color="#172033",
                ha="center", va="center", fontproperties=font, zorder=4)
    if route_plan.get("title"):
        title = route_plan["title"]
        ax.text(*xy(title["anchor"]), title["text"], fontsize=title["font_size_pt"], color="#172033",
                ha="center", va="center", fontproperties=font, fontweight="bold", zorder=4)
    svg_path = output_dir / f"{stem}.svg"
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    fig.savefig(svg_path, format="svg", dpi=220)
    with matplotlib.rc_context({"pdf.fonttype": 3}):
        fig.savefig(pdf_path, format="pdf", dpi=220)
    fig.savefig(png_path, format="png", dpi=220)
    plt.close(fig)
    return {"svg": svg_path, "pdf": pdf_path, "png": png_path}
