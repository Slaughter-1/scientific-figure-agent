from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _segment_crosses_box(start: tuple[float, float], end: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    """Return whether an orthogonal segment enters the strict interior of a box."""
    x1, y1 = start
    x2, y2 = end
    left, bottom, right, top = box
    if abs(x1 - x2) < 1e-9:
        return left < x1 < right and max(min(y1, y2), bottom) < min(max(y1, y2), top)
    if abs(y1 - y2) < 1e-9:
        return bottom < y1 < top and max(min(x1, x2), left) < min(max(x1, x2), right)
    return False


def critique_spec_geometry(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Check deterministic routes before rendering so clipping and crossings are caught."""
    from .layouts import layout_edges, layout_nodes, node_size
    from .visual_styles import get_visual_style

    nodes = spec.get("nodes", [])
    if not nodes or not spec.get("edges"):
        return []
    family = get_visual_style(spec.get("style", {}).get("variant", "editorial")).get("layout_family", "pipeline")
    positions = layout_nodes(spec, family=family)
    routes = layout_edges(spec, positions, family=family)
    width, height = node_size(spec)
    boxes = {
        node["id"]: (positions[node["id"]][0] - width / 2, positions[node["id"]][1] - height / 2,
                     positions[node["id"]][0] + width / 2, positions[node["id"]][1] + height / 2)
        for node in nodes
    }
    findings: list[dict[str, str]] = []
    for edge, route in zip(spec.get("edges", []), routes):
        if any(abs(a - b) < 1e-9 and abs(c - d) < 1e-9 for (a, c), (b, d) in zip(route, route[1:])):
            findings.append(_finding("degenerate_route", "warning", f"edge {edge.get('source')}->{edge.get('target')} contains a zero-length segment"))
        for node_id, box in boxes.items():
            if node_id in {edge.get("source"), edge.get("target")}:
                continue
            if any(_segment_crosses_box(start, end, box) for start, end in zip(route, route[1:])):
                findings.append(_finding("edge_crosses_node", "error", f"edge {edge.get('source')}->{edge.get('target')} crosses node {node_id}"))
                break
    def horizontal_segments(route):
        for start, end in zip(route, route[1:]):
            if abs(start[1] - end[1]) < 1e-8 and abs(start[0] - end[0]) > 1e-8:
                yield min(start[0], end[0]), max(start[0], end[0]), start[1], start[0] < end[0]

    def vertical_segments(route):
        for start, end in zip(route, route[1:]):
            if abs(start[0] - end[0]) < 1e-8 and abs(start[1] - end[1]) > 1e-8:
                yield min(start[1], end[1]), max(start[1], end[1]), start[0], start[1] < end[1]

    for index, left_route in enumerate(routes):
        for right_route in routes[index + 1:]:
            if any(
                left[2] == right[2]
                and left[3] != right[3]
                and min(left[1], right[1]) - max(left[0], right[0]) > 1e-8
                for left in horizontal_segments(left_route)
                for right in horizontal_segments(right_route)
            ) or any(
                left[2] == right[2]
                and left[3] != right[3]
                and min(left[1], right[1]) - max(left[0], right[0]) > 1e-8
                for left in vertical_segments(left_route)
                for right in vertical_segments(right_route)
            ):
                findings.append(_finding("edge_reverse_overlap", "error", "two edge routes share a horizontal or vertical segment in opposite directions"))
    return findings


def _finding(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def critique_scene(scene: dict[str, Any]) -> list[dict[str, str]]:
    """Run deterministic geometry checks on a compiled Figma-like scene."""
    findings: list[dict[str, str]] = []
    frame = next((n for n in scene.get("nodes", []) if n.get("kind") == "FRAME" and "source_id" not in n), None)
    bounds = (float(frame.get("x", 0)), float(frame.get("y", 0)), float(frame.get("width", 0)), float(frame.get("height", 0))) if frame else None
    shapes = [n for n in scene.get("nodes", []) if n.get("kind") in {"RECTANGLE", "TEXT"} and all(k in n for k in ("x", "y", "width", "height"))]
    for index, node in enumerate(shapes):
        x, y, width, height = (float(node[k]) for k in ("x", "y", "width", "height"))
        if bounds and (x < bounds[0] or y < bounds[1] or x + width > bounds[0] + bounds[2] or y + height > bounds[1] + bounds[3]):
            findings.append(_finding("out_of_bounds", "warning", f"{node.get('source_id', node.get('name', index))} exceeds the canvas"))
        for other in shapes[index + 1 :]:
            ox, oy, ow, oh = (float(other[k]) for k in ("x", "y", "width", "height"))
            if x < ox + ow and x + width > ox and y < oy + oh and y + height > oy:
                if node.get("kind") == "RECTANGLE" and other.get("kind") == "RECTANGLE":
                    findings.append(_finding("node_overlap", "warning", f"{node.get('source_id')} overlaps {other.get('source_id')}"))
    return findings


def critique_artifact(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if path.suffix.lower() == ".svg":
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8"))
        except (OSError, ET.ParseError) as exc:
            return [_finding("invalid_svg", "error", str(exc))]
        findings: list[dict[str, str]] = []
        if not root.get("width") or not root.get("height"):
            findings.append(_finding("missing_dimensions", "warning", "SVG has no explicit width and height"))
        texts = list(root.iter("text"))
        if not texts:
            findings.append(_finding("missing_text", "warning", "SVG contains no text labels"))
        if root.get("viewBox") is None:
            findings.append(_finding("missing_viewbox", "warning", "SVG has no viewBox for reliable downstream scaling"))
        return findings
    if path.suffix.lower() == ".json":
        try:
            import json
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("kind") == "FIGMA_SCENE":
                return critique_scene(payload)
        except (OSError, ValueError):
            return [_finding("invalid_json", "error", "JSON artifact cannot be parsed")]
    return []


def critique_candidate_set(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Detect candidates that are visually identical despite different IDs."""
    findings: list[dict[str, str]] = []
    fingerprints: dict[str, str] = {}
    for candidate in candidates:
        fingerprint = json.dumps(candidate.get("preview_fingerprint", {}), ensure_ascii=False, sort_keys=True)
        if fingerprint in fingerprints:
            findings.append(_finding("candidate_similarity", "warning", f"{candidate.get('candidate_id')} is visually identical to {fingerprints[fingerprint]}"))
        else:
            fingerprints[fingerprint] = str(candidate.get("candidate_id", "unknown"))
    return findings
