from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Protocol

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


def _positions(spec: dict[str, Any]) -> dict[str, tuple[float, float]]:
    direction = spec["layout"]["direction"]
    spacing = max(float(spec["layout"].get("spacing", 24)), 12.0)
    positions: dict[str, tuple[float, float]] = {}
    for index, node in enumerate(spec["nodes"]):
        if direction == "top-to-bottom":
            positions[node["id"]] = (80 + (index % 3) * (220 + spacing), 80 + (index // 3) * (150 + spacing))
        else:
            positions[node["id"]] = (80 + (index % 5) * (220 + spacing), 80 + (index // 5) * (150 + spacing))
    return positions


def compile_figma_scene(spec: dict[str, Any]) -> dict[str, Any]:
    require_valid_spec(spec)
    positions = _positions(spec)
    nodes: list[dict[str, Any]] = [{"kind": "FRAME", "name": spec.get("title", "Scientific Figure"), "x": 0, "y": 0, "width": 1400, "height": 800, "children": []}]
    colors = spec.get("style", {}).get("colors", {})
    for group in spec.get("groups", []):
        children = [positions[node_id] for node_id in group["children"] if node_id in positions]
        if not children:
            continue
        xs, ys = zip(*children)
        nodes.append({"kind": "FRAME", "source_id": group["id"], "name": group["label"], "x": min(xs) - 20, "y": min(ys) - 20, "width": max(xs) - min(xs) + 200, "height": max(ys) - min(ys) + 100, "children": list(group["children"])})
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        nodes.append({"kind": "RECTANGLE", "source_id": node["id"], "name": node["label"], "x": x, "y": y, "width": 160, "height": 64, "fills": [{"color": colors.get(node["type"], "#E8EEF7")}]})
        nodes.append({"kind": "TEXT", "source_id": f"{node['id']}:label", "name": node["label"], "x": x + 12, "y": y + 22, "width": 136, "height": 20, "characters": node["label"]})
    for index, edge in enumerate(spec["edges"]):
        source_x, source_y = positions[edge["source"]]
        target_x, target_y = positions[edge["target"]]
        nodes.append({"kind": "LINE", "source_id": f"edge:{index}", "name": edge.get("label", edge["type"]), "source": edge["source"], "target": edge["target"], "start": [source_x + 160, source_y + 32], "end": [target_x, target_y + 32], "marker_end": "ARROW_LINES"})
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
