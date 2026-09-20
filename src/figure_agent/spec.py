from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

NODE_TYPES = {"model", "tool", "data", "process", "storage", "decision"}
EDGE_TYPES = {"data_flow", "control_flow", "dependency"}
FIGURE_TYPES = {"architecture", "workflow", "graph", "plot"}
SCHEMA_VERSIONS = {"0.1", "0.2"}
DIRECTIONS = {"left-to-right", "top-to-bottom"}
PLOT_KINDS = {"bar", "line", "heatmap", "scatter"}
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("schema_version") not in SCHEMA_VERSIONS:
        errors.append("schema_version must be '0.1' or '0.2'")
    if spec.get("figure_type") not in FIGURE_TYPES:
        errors.append("figure_type is unsupported")
    layout = spec.get("layout", {})
    if layout.get("direction") not in DIRECTIONS:
        errors.append("layout.direction is unsupported")
    if not isinstance(spec.get("style"), dict):
        errors.append("style is required and must be an object")
    for field_name in ("provenance", "constraints"):
        if field_name in spec and not isinstance(spec[field_name], dict):
            errors.append(f"{field_name} must be an object")
    for field_name in ("template_refs", "asset_refs", "review_notes"):
        if field_name in spec and not isinstance(spec[field_name], list):
            errors.append(f"{field_name} must be an array")
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
    groups = spec.get("groups", [])
    if not isinstance(groups, list):
        errors.append("groups must be an array")
    else:
        group_ids: set[str] = set()
        for index, group in enumerate(groups):
            group_id = group.get("id") if isinstance(group, dict) else None
            if not group_id:
                errors.append(f"groups[{index}].id is required")
                continue
            if group_id in group_ids:
                errors.append(f"duplicate group id: {group_id}")
            group_ids.add(group_id)
            children = group.get("children")
            if not isinstance(children, list):
                errors.append(f"groups[{index}].children must be an array")
            else:
                for child in children:
                    if child not in ids:
                        errors.append(f"groups[{index}] references missing node: {child}")
    if spec.get("figure_type") == "plot":
        data = spec.get("data")
        if not isinstance(data, dict):
            errors.append("plot data is required and must be an object")
        elif data.get("kind") not in PLOT_KINDS:
            errors.append("plot data.kind is unsupported")
        elif data.get("kind") == "heatmap":
            matrix = data.get("matrix")
            if not isinstance(matrix, list) or not matrix or not all(isinstance(row, list) for row in matrix):
                errors.append("plot data.matrix must be a non-empty array")
            elif any(len(row) != len(matrix[0]) for row in matrix):
                errors.append("plot data.matrix must be rectangular")
        else:
            x_values, y_values = data.get("x"), data.get("y")
            if not isinstance(x_values, list) or not isinstance(y_values, list):
                errors.append("plot data.x and data.y must be arrays")
            elif len(x_values) != len(y_values):
                errors.append("plot data.x and data.y must have equal lengths")
    colors = spec.get("style", {}).get("colors", {}) if isinstance(spec.get("style"), dict) else {}
    for name, color in colors.items():
        if not isinstance(color, str) or not HEX_COLOR.fullmatch(color):
            errors.append(f"style.colors.{name} must be a six-digit hex color")
    return errors


def require_valid_spec(spec: dict[str, Any]) -> None:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Invalid Figure Spec:\n" + "\n".join(f"- {error}" for error in errors))
