from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Protocol

from ..layouts import node_size_px
from ..spec import require_valid_spec


class FigmaDriver(Protocol):
    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]: ...


class ConnectedFigmaDriver:
    """Adapter for an externally supplied Figma writer.

    The callback is intentionally injected so the core package never guesses a
    particular MCP/API schema. The caller owns authentication and transport.
    """

    def __init__(self, writer: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._writer = writer

    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]:
        result = self._writer(scene)
        if not isinstance(result, dict):
            raise TypeError("external Figma writer must return a dict")
        if result.get("status") != "connected":
            raise ValueError("external Figma writer must return status=connected")
        if not result.get("file_or_frame"):
            raise ValueError("connected Figma result must include file_or_frame")
        return result


def _positions(spec: dict[str, Any], node_width: float, node_height: float) -> dict[str, tuple[float, float]]:
    direction = spec["layout"]["direction"]
    spacing = max(float(spec["layout"].get("spacing", 24)), 12.0)
    column_step = node_width + spacing + 20
    row_step = node_height + spacing + 36
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(spec["nodes"]):
        if direction == "top-to-bottom":
            positions[node["id"]] = (80 + (index % 3) * column_step, 80 + (index // 3) * row_step)
        else:
            positions[node["id"]] = (80 + (index % 5) * column_step, 80 + (index // 5) * row_step)
    return positions


def compile_figma_scene(spec: dict[str, Any]) -> dict[str, Any]:
    require_valid_spec(spec)
    node_width, node_height = node_size_px(spec)
    positions = _positions(spec, node_width, node_height)
    columns = 3 if spec["layout"]["direction"] == "top-to-bottom" else 5
    rows = max(1, (len(spec.get("nodes", [])) + columns - 1) // columns)
    frame_width = max(1400.0, 160 + min(columns, max(len(spec.get("nodes", [])), 1)) * (node_width + 20))
    frame_height = max(800.0, 160 + rows * (node_height + 36))
    nodes: list[dict[str, Any]] = [{"kind": "FRAME", "name": spec.get("title", "Scientific Figure"), "x": 0, "y": 0, "width": frame_width, "height": frame_height, "children": []}]
    colors = spec.get("style", {}).get("colors", {})
    for group in spec.get("groups", []):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        nodes.append({"kind": "FRAME", "source_id": group["id"], "name": group["label"], "x": min(xs) - 20, "y": min(ys) - 20, "width": max(xs) - min(xs) + node_width + 40, "height": max(ys) - min(ys) + node_height + 40, "children": list(group["children"])})
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        nodes.append({"kind": "RECTANGLE", "source_id": node["id"], "name": node["label"], "x": x, "y": y, "width": node_width, "height": node_height, "fills": [{"color": colors.get(node["type"], "#E8EEF7")}]})
        nodes.append({"kind": "TEXT", "source_id": f"{node['id']}:label", "name": node["label"], "x": x + 12, "y": y + (node_height - 28) / 2, "width": max(node_width - 24, 24), "height": 28, "characters": node["label"]})
    for index, edge in enumerate(spec["edges"]):
        source_x, source_y = positions[edge["source"]]
        target_x, target_y = positions[edge["target"]]
        nodes.append({"kind": "LINE", "source_id": f"edge:{index}", "name": edge.get("label", edge["type"]), "label": edge.get("label", ""), "source": edge["source"], "target": edge["target"], "start": [source_x + node_width, source_y + node_height / 2], "end": [target_x, target_y + node_height / 2], "marker_end": "ARROW_LINES"})
    return {"schema_version": "0.1", "kind": "FIGMA_SCENE", "nodes": nodes}


class LocalFigmaDriver:
    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]:
        return {"status": "mock", "node_count": len(scene["nodes"])}


def render_figma_spec(spec: dict[str, Any], output_dir: str | Path, transport: FigmaDriver | None = None) -> dict[str, Any]:
    scene = compile_figma_scene(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_path = output_dir / "figure.figma-scene.json"
    scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    result: dict[str, Any] = {"scene": str(scene_path), "status": "unavailable"}
    if transport is not None:
        try:
            result.update(transport.write_scene(scene))
        except Exception as exc:
            result.update({"status": "error", "error": str(exc)})
    return result
