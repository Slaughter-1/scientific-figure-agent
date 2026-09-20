from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

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
        color = spec.get("style", {}).get("colors", {}).get(node.get("type"), "#E8EEF7")
        style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={color};strokeColor=#64748B;"
        label = html.escape(str(node["label"]), quote=True)
        group_attribute = f' data-group="{html.escape(group_by_node[node["id"]], quote=True)}"' if node["id"] in group_by_node else ""
        cells.append(f'<mxCell id="{node["id"]}" value="{label}" style="{style}" vertex="1" parent="1"{group_attribute}><mxGeometry x="{x}" y="{y}" width="150" height="60" as="geometry"/></mxCell>')
    for group_index, group in enumerate(spec.get("groups", []), start=500):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        x, y = min(xs) - 20, min(ys) - 25
        width, height = max(xs) - min(xs) + 190, max(ys) - min(ys) + 110
        label = html.escape(str(group["label"]), quote=True)
        cells.append(f'<mxCell id="group-{group_index}" value="{label}" style="swimlane;html=1;rounded=1;dashed=1;fillOpacity=0;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry"/></mxCell>')
    for index, edge in enumerate(spec["edges"], start=100):
        cells.append(f'<mxCell id="edge-{index}" edge="1" parent="1" source="{edge["source"]}" target="{edge["target"]}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;"><mxGeometry relative="1" as="geometry"/></mxCell>')
    return '<mxfile host="Scientific Figure Agent"><diagram name="Agent Workflow"><mxGraphModel><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>"


def _layout(spec: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Return deterministic center positions in inches for preview and XML."""
    direction = spec.get("layout", {}).get("direction", "left-to-right")
    spacing = max(float(spec.get("layout", {}).get("spacing", 24)), 12.0) / 24.0
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(spec["nodes"]):
        if direction == "top-to-bottom":
            positions[node["id"]] = (1.2 + (index % 3) * (2.2 + spacing), 5.2 - (index // 3) * (1.4 + spacing))
        else:
            positions[node["id"]] = (0.8 + (index % 5) * (2.0 + spacing), 3.8 - (index // 5) * (1.5 + spacing))
    return positions


def _node_color(spec: dict[str, Any], node: dict[str, Any]) -> str:
    colors = spec.get("style", {}).get("colors", {})
    return colors.get(node.get("type"), "#E8EEF7")


def render_drawio_spec(spec: dict[str, Any], output_dir: str | Path, stem: str = "figure") -> dict[str, Path]:
    """Render one validated Figure Spec to editable Draw.io plus SVG/PDF previews."""
    from figure_agent.spec import require_valid_spec

    require_valid_spec(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    drawio_path = output_dir / f"{stem}.drawio"
    drawio_path.write_text(build_drawio_xml(spec), encoding="utf-8")

    positions = _layout(spec)
    max_x = max((x for x, _ in positions.values()), default=2.0) + 1.6
    max_y = max((y for _, y in positions.values()), default=2.0) + 1.0
    fig, ax = plt.subplots(figsize=(max(5.5, max_x), max(3.5, max_y)), constrained_layout=True)
    ax.set_xlim(0, max_x)
    ax.set_ylim(0, max_y)
    ax.axis("off")
    for group in spec.get("groups", []):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        pad = 0.35
        rect = Rectangle((min(xs) - 1.0 - pad, min(ys) - 0.45 - pad), max(xs) - min(xs) + 2.0 + 2 * pad, max(ys) - min(ys) + 0.9 + 2 * pad, fill=False, linestyle="--", linewidth=1.0, edgecolor="#94A3B8")
        ax.add_patch(rect)
        ax.text(min(xs) - 0.95, max(ys) + 0.5, group["label"], fontsize=8, color="#475569")
    for edge in spec["edges"]:
        sx, sy = positions[edge["source"]]
        tx, ty = positions[edge["target"]]
        ax.annotate("", xy=(tx - 0.98, ty), xytext=(sx + 0.98, sy), arrowprops={"arrowstyle": "->", "color": "#475569", "linewidth": 0.9})
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        patch = FancyBboxPatch((x - 0.98, y - 0.38), 1.96, 0.76, boxstyle="round,pad=0.03,rounding_size=0.08", facecolor=_node_color(spec, node), edgecolor="#64748B", linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x, y, node["label"], ha="center", va="center", fontsize=8)
    if spec.get("title"):
        ax.set_title(spec["title"], fontsize=11, pad=10)
    svg_path = output_dir / f"{stem}.svg"
    pdf_path = output_dir / f"{stem}.pdf"
    fig.savefig(svg_path, format="svg")
    fig.savefig(pdf_path, format="pdf")
    plt.close(fig)
    return {"drawio": drawio_path, "svg": svg_path, "pdf": pdf_path}
