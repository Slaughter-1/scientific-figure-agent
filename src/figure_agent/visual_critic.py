from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


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
