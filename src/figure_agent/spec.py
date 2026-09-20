from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NODE_TYPES = {"model", "tool", "data", "process", "storage", "decision"}
EDGE_TYPES = {"data_flow", "control_flow", "dependency"}
FIGURE_TYPES = {"architecture", "workflow", "graph", "plot"}
DIRECTIONS = {"left-to-right", "top-to-bottom"}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("schema_version") != "0.1":
        errors.append("schema_version must be '0.1'")
    if spec.get("figure_type") not in FIGURE_TYPES:
        errors.append("figure_type is unsupported")
    layout = spec.get("layout", {})
    if layout.get("direction") not in DIRECTIONS:
        errors.append("layout.direction is unsupported")
    if not isinstance(spec.get("style"), dict):
        errors.append("style is required and must be an object")
    nodes = spec.get("nodes")
    edges = spec.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return errors + ["nodes and edges must be arrays"]
    ids: set[str] = set()
    for index, node in enumerate(nodes):
        node_id = node.get("id") if isinstance(node, dict) else None
        if not node_id:
            errors.append(f"nodes[{index}].id is required")
            continue
        if node_id in ids:
            errors.append(f"duplicate node id: {node_id}")
        ids.add(node_id)
        if node.get("type") not in NODE_TYPES:
            errors.append(f"nodes[{index}].type is unsupported")
        if not isinstance(node.get("label"), str) or not node["label"].strip():
            errors.append(f"nodes[{index}].label is required")
    for index, edge in enumerate(edges):
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"edges[{index}].type is unsupported")
        for endpoint in ("source", "target"):
            value = edge.get(endpoint)
            if value not in ids:
                errors.append(f"edges[{index}].{endpoint} references missing node: {value}")
    colors = spec.get("style", {}).get("colors", {}) if isinstance(spec.get("style"), dict) else {}
    for name, color in colors.items():
        if not isinstance(color, str) or not HEX_COLOR.fullmatch(color):
            errors.append(f"style.colors.{name} must be a six-digit hex color")
    return errors


def require_valid_spec(spec: dict[str, Any]) -> None:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Invalid Figure Spec:\n" + "\n".join(f"- {error}" for error in errors))
