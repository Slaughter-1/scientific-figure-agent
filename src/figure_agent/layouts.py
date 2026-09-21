from __future__ import annotations

from typing import Any


def _node_index(spec: dict[str, Any]) -> dict[str, int]:
    return {node["id"]: index for index, node in enumerate(spec.get("nodes", []))}


def layout_nodes(spec: dict[str, Any], *, family: str) -> dict[str, tuple[float, float]]:
    """Return deterministic center positions in preview inches."""
    nodes = spec.get("nodes", [])
    positions: dict[str, tuple[float, float]] = {}
    if family == "pipeline":
        for index, node in enumerate(nodes):
            positions[node["id"]] = (1.6 + index * 2.65, 3.6)
    elif family == "swimlane":
        for index, node in enumerate(nodes):
            row, column = divmod(index, 3)
            positions[node["id"]] = (1.7 + column * 2.8, 5.0 - row * 1.75)
    elif family == "loop":
        center_x, center_y = 4.2, 3.8
        offsets = [(0.0, 1.9), (2.5, 0.3), (0.0, -1.9), (-2.5, 0.3)]
        for index, node in enumerate(nodes):
            dx, dy = offsets[index % len(offsets)]
            positions[node["id"]] = (center_x + dx, center_y + dy)
    elif family == "hierarchy":
        for index, node in enumerate(nodes):
            column, row = divmod(index, 2)
            positions[node["id"]] = (1.8 + column * 2.9, 4.8 - row * 1.8)
    else:
        raise ValueError(f"unsupported layout family: {family}")
    return positions


def layout_edges(spec: dict[str, Any], positions: dict[str, tuple[float, float]], *, family: str) -> list[list[tuple[float, float]]]:
    """Return route points for each edge, keeping feedback outside node centers."""
    indexes = _node_index(spec)
    routes: list[list[tuple[float, float]]] = []
    for edge in spec.get("edges", []):
        source, target = positions[edge["source"]], positions[edge["target"]]
        if family == "loop" and indexes.get(edge["target"], 0) <= indexes.get(edge["source"], 0):
            left = min(source[0], target[0]) - 1.2
            routes.append([(source[0] - 0.7, source[1]), (left, source[1]), (left, target[1]), (target[0] - 0.7, target[1])])
        elif family in {"swimlane", "hierarchy"} and abs(source[1] - target[1]) > 0.2:
            middle_x = (source[0] + target[0]) / 2
            routes.append([(source[0], source[1] - 0.35), (middle_x, source[1]), (middle_x, target[1]), (target[0], target[1] + 0.35)])
        else:
            routes.append([(source[0] + 0.7, source[1]), (target[0] - 0.7, target[1])])
    return routes
