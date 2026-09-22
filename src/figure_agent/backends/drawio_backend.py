from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

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


def build_drawio_xml(spec: dict[str, Any]) -> str:
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


def render_drawio_spec(spec: dict[str, Any], output_dir: str | Path, stem: str = "figure") -> dict[str, Path]:
    """Render one validated Figure Spec to editable Draw.io plus SVG/PDF/PNG previews."""
    from figure_agent.spec import require_valid_spec

    require_valid_spec(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = output_dir / f"{stem}.drawio"
    drawio_path.write_text(build_drawio_xml(spec), encoding="utf-8")

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
