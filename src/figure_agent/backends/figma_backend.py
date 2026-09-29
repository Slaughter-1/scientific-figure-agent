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


def _compile_figma_scene_legacy(spec: dict[str, Any]) -> dict[str, Any]:
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


def _compile_figma_scene_route_plan(spec: dict[str, Any], route_plan: dict[str, Any]) -> dict[str, Any]:
    """Compile the shared RoutePlan as editable local vector geometry."""
    left, bottom, right, top = route_plan["bounds"]
    pixels_per_mm = 4.0
    layout_scale = float(route_plan["mm_per_unit"])
    width = float(route_plan["paper_width_mm"]) * pixels_per_mm
    height = (top - bottom) * layout_scale * pixels_per_mm

    def point(value: tuple[float, float]) -> list[float]:
        return [(value[0] - left) * layout_scale * pixels_per_mm,
                (top - value[1]) * layout_scale * pixels_per_mm]

    def box(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1 = point((value[0], value[3]))
        x2, y2 = point((value[2], value[1]))
        return x1, y1, x2-x1, y2-y1

    nodes: list[dict[str, Any]] = [{
        "kind": "FRAME", "name": spec.get("title", "Scientific Figure"), "x": 0, "y": 0,
        "width": width, "height": height, "children": [],
        "route_plan_transform": {"origin": [left, bottom], "mm_per_unit": layout_scale,
                                  "pixels_per_mm": pixels_per_mm, "y_axis": "down"},
    }]
    colors = spec.get("style", {}).get("colors", {})
    for group in spec.get("groups", []):
        group_box = route_plan.get("group_boxes", {}).get(group["id"])
        if group_box:
            x, y, w, h = box(group_box)
            nodes.append({"kind": "FRAME", "source_id": group["id"], "name": group["label"],
                          "x": x, "y": y, "width": w, "height": h,
                          "children": list(group["children"])})
    for node in spec["nodes"]:
        x, y, w, h = box(route_plan["node_boxes"][node["id"]])
        nodes.append({"kind": "RECTANGLE", "source_id": node["id"], "name": node["label"],
                      "x": x, "y": y, "width": w, "height": h,
                      "fills": [{"color": colors.get(node["type"], "#E8EEF7")}],
                      "route_plan_position": point(route_plan["positions"][node["id"]])})
        nodes.append({"kind": "TEXT", "source_id": f"{node['id']}:label", "name": node["label"],
                      "x": x + 12, "y": y + max((h - 28) / 2, 0), "width": max(w - 24, 24), "height": 28,
                      "characters": node["label"]})
    for route, edge in zip(route_plan["routes"], spec["edges"]):
        points = [point(tuple(value)) for value in route.get("points", [])]
        path_data = " ".join(("M" if index == 0 else "L") + f" {value[0]:.3f} {value[1]:.3f}" for index, value in enumerate(points))
        nodes.append({"kind": "VECTOR", "source_id": f"edge:{route['edge_index']}",
                      "name": edge.get("label", edge["type"]), "label": edge.get("label", ""),
                      "source": edge["source"], "target": edge["target"], "edge_index": route["edge_index"],
                      "role": route["role"], "fan_out": route["fan_out"], "fan_in": route["fan_in"],
                      "points": points, "path_data": path_data, "source_port": route["source_port"],
                      "target_port": route["target_port"], "marker_end": "ARROW_LINES"})
        label = route.get("label_box")
        if label:
            x, y, w, h = box(label["box"])
            nodes.append({"kind": "TEXT", "source_id": f"edge:{route['edge_index']}:label",
                          "name": label["text"], "characters": label["text"], "edge_index": route["edge_index"],
                          "x": x, "y": y, "width": w, "height": h, "anchor": point(label["anchor"]),
                          "font_size_pt": label["font_size_pt"]})
    return {"schema_version": "0.1", "kind": "FIGMA_SCENE", "nodes": nodes,
            "route_plan": {"paper_width_mm": route_plan["paper_width_mm"], "mm_per_unit": layout_scale,
                           "bounds": list(route_plan["bounds"]), "pixels_per_mm": pixels_per_mm}}


def compile_figma_scene(spec: dict[str, Any], *, route_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    require_valid_spec(spec)
    return _compile_figma_scene_route_plan(spec, route_plan) if route_plan is not None else _compile_figma_scene_legacy(spec)


class LocalFigmaDriver:
    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]:
        return {"status": "mock", "node_count": len(scene["nodes"])}


def render_figma_spec(spec: dict[str, Any], output_dir: str | Path, transport: FigmaDriver | None = None,
                      *, route_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    scene = compile_figma_scene(spec, route_plan=route_plan)
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
