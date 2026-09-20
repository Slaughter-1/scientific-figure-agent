from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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


def check_drawio_output(path: str | Path) -> list[str]:
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
    errors = [f"missing required label: {label}" for label in REQUIRED_LABELS if label not in text]
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
    positions = {node["id"]: (80 + (index % 5) * 190, 80 + (index // 5) * 150) for index, node in enumerate(spec["nodes"])}
    for index, node in enumerate(spec["nodes"], start=2):
        x, y = positions[node["id"]]
        style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#E8EEF7;strokeColor=#64748B;"
        cells.append(f'<mxCell id="{node["id"]}" value="{node["label"]}" style="{style}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="150" height="60" as="geometry"/></mxCell>')
    for index, edge in enumerate(spec["edges"], start=100):
        cells.append(f'<mxCell id="edge-{index}" edge="1" parent="1" source="{edge["source"]}" target="{edge["target"]}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;"><mxGeometry relative="1" as="geometry"/></mxCell>')
    return '<mxfile host="Scientific Figure Agent"><diagram name="Agent Workflow"><mxGraphModel><root>' + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>"
