from __future__ import annotations

from typing import Any
import heapq
import math


def node_size(spec: dict[str, Any]) -> tuple[float, float]:
    style = spec.get("style", {})
    token = style.get("node", {})
    return (style.get("node_width", token.get("width", 210)) / 100,
            style.get("node_height", token.get("height", 84)) / 100)


def node_size_px(spec: dict[str, Any]) -> tuple[float, float]:
    """Return the canonical node box used by editable and raster outputs."""
    width, height = node_size(spec)
    return width * 100, height * 100


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
        radius = max(2.5, len(nodes) * 0.6)
        center_x = center_y = radius + 1.5
        for index, node in enumerate(nodes):
            angle = math.pi / 2 - 2 * math.pi * index / len(nodes)
            positions[node["id"]] = (center_x + radius * math.cos(angle), center_y + radius * math.sin(angle))
    elif family == "hierarchy":
        for index, node in enumerate(nodes):
            column, row = divmod(index, 2)
            positions[node["id"]] = (1.8 + column * 2.9, 4.8 - row * 1.8)
    else:
        raise ValueError(f"unsupported layout family: {family}")
    return positions


def layout_edges(spec: dict[str, Any], positions: dict[str, tuple[float, float]], *, family: str) -> list[list[tuple[float, float]]]:
    """Route orthogonally outside node bounds with outward-facing ports.

    A visibility grid supplies detours around all nodes; terminal stubs ensure
    the arrow approaches the target boundary rather than doubling back inside it.
    """
    width, height = node_size(spec)
    boxes = [(x-width/2, y-height/2, x+width/2, y+height/2) for x, y in positions.values()]
    clearance = 0.18

    def clear(a, b):
        for left, bottom, right, top in boxes:
            if abs(a[0]-b[0]) < 1e-8:
                if left+1e-8 < a[0] < right-1e-8 and max(min(a[1], b[1]), bottom) < min(max(a[1], b[1]), top)-1e-8:
                    return False
            elif bottom+1e-8 < a[1] < top-1e-8 and max(min(a[0], b[0]), left) < min(max(a[0], b[0]), right)-1e-8:
                return False
        return True

    def ports(center):
        x, y = center
        return [((x+dx*width/2, y+dy*height/2), (x+dx*(width/2+clearance), y+dy*(height/2+clearance))) for dx, dy in [(1, 0), (0, -1), (-1, 0), (0, 1)]]

    routes = []
    pipeline_feedback_count = 0
    indexes = _node_index(spec)

    def reverse_horizontal_overlap(left_route, right_route):
        def segments(route):
            for start, end in zip(route, route[1:]):
                if abs(start[1] - end[1]) < 1e-8 and abs(start[0] - end[0]) > 1e-8:
                    yield min(start[0], end[0]), max(start[0], end[0]), start[1], start[0] < end[0]

        return any(
            left[2] == right[2]
            and left[3] != right[3]
            and min(left[1], right[1]) - max(left[0], right[0]) > 1e-8
            for left in segments(left_route)
            for right in segments(right_route)
        )

    def add_route(route, source, target):
        """Append a route, detouring a later edge when it reverses a lane."""
        if any(reverse_horizontal_overlap(route, previous) for previous in routes):
            left = min(box[0] for box in boxes) - clearance
            right = max(box[2] for box in boxes) + clearance
            top = max(box[3] for box in boxes) + clearance
            bottom = min(box[1] for box in boxes) - clearance
            alternatives = [
                [(source[0] + width / 2, source[1]), (right, source[1]), (right, target[1]), (target[0] + width / 2, target[1])],
                [(source[0] - width / 2, source[1]), (left, source[1]), (left, target[1]), (target[0] - width / 2, target[1])],
                [(source[0], source[1] + height / 2), (source[0], top), (target[0], top), (target[0], target[1] + height / 2)],
                [(source[0], source[1] - height / 2), (source[0], bottom), (target[0], bottom), (target[0], target[1] - height / 2)],
            ]
            for alternative in alternatives:
                if all(clear(start, end) for start, end in zip(alternative, alternative[1:])) and not any(reverse_horizontal_overlap(alternative, previous) for previous in routes):
                    route = alternative
                    break
        routes.append(route)

    for edge in spec.get("edges", []):
        # Reverse control-flow edges in a pipeline get their own outer
        # corridor. Routing them through the forward lane makes the two
        # arrows share a long segment in opposite directions, which is hard
        # to read even when no node is crossed.
        if family == "pipeline" and edge.get("type") == "control_flow" and indexes.get(edge["target"], 0) <= indexes.get(edge["source"], 0):
            source = positions[edge["source"]]
            target = positions[edge["target"]]
            corridor = max(y for _, y in positions.values()) + height / 2 + 0.65 + pipeline_feedback_count * 0.22
            proposed = [(source[0], source[1] + height / 2), (source[0], corridor), (target[0], corridor), (target[0], target[1] + height / 2)]
            if all(clear(a, b) for a, b in zip(proposed, proposed[1:])):
                add_route(proposed, source, target)
                pipeline_feedback_count += 1
                continue
        if family in {"hierarchy", "swimlane"} and indexes.get(edge["target"], 0) <= indexes.get(edge["source"], 0):
            source = positions[edge["source"]]
            target = positions[edge["target"]]
            corridor = min(y for _, y in positions.values()) - height / 2 - 0.55 - len(routes) * 0.18
            proposed = [(source[0], source[1] - height / 2), (source[0], corridor), (target[0], corridor), (target[0], target[1] - height / 2)]
            if all(clear(a, b) for a, b in zip(proposed, proposed[1:])):
                add_route(proposed, source, target)
                continue
            # If the target column contains another node, approach from the
            # outside of the whole graph instead of crossing that node.
            side_x = min(left for left, _, _, _ in boxes) - clearance
            side_route = [(source[0], source[1] - height / 2), (source[0], corridor), (side_x, corridor), (side_x, target[1]), (target[0] - width / 2, target[1])]
            if all(clear(a, b) for a, b in zip(side_route, side_route[1:])):
                add_route(side_route, source, target)
                continue
        if family == "loop" and indexes.get(edge["target"], 0) <= indexes.get(edge["source"], 0):
            source = positions[edge["source"]]
            target = positions[edge["target"]]
            corridor = max(y for _, y in positions.values()) + height / 2 + 0.65 + len(routes) * 0.18
            proposed = [(source[0], source[1] + height / 2), (source[0], corridor), (target[0], corridor), (target[0], target[1] + height / 2)]
            if all(clear(a, b) for a, b in zip(proposed, proposed[1:])):
                add_route(proposed, source, target)
                continue
        source = positions[edge["source"]]
        target = positions[edge["target"]]
        starts, ends = ports(source), ports(target)
        xs = sorted({p[0] for pair in starts+ends for p in pair} | {v for l,b,r,t in boxes for v in (l-clearance, r+clearance)})
        ys = sorted({p[1] for pair in starts+ends for p in pair} | {v for l,b,r,t in boxes for v in (b-clearance, t+clearance)})
        targets = {outer: boundary for boundary, outer in ends if clear(boundary, outer)}
        queue, distances, previous, roots = [], {}, {}, {}
        for boundary, outer in starts:
            if clear(boundary, outer):
                distances[outer] = clearance
                previous[outer] = None
                roots[outer] = boundary
                heapq.heappush(queue, (clearance, outer))
        finish = None
        while queue:
            distance, point = heapq.heappop(queue)
            if distance != distances[point]:
                continue
            if point in targets and (edge["source"] != edge["target"] or distance > clearance+1e-8):
                finish = point
                break
            i, j = xs.index(point[0]), ys.index(point[1])
            neighbors = [(xs[k], point[1]) for k in (i-1, i+1) if 0 <= k < len(xs)] + [(point[0], ys[k]) for k in (j-1, j+1) if 0 <= k < len(ys)]
            for other in neighbors:
                cost = distance + abs(other[0]-point[0]) + abs(other[1]-point[1])
                if clear(point, other) and cost < distances.get(other, float("inf"))-1e-8:
                    distances[other] = cost
                    previous[other] = point
                    heapq.heappush(queue, (cost, other))
        if finish is None:
            raise ValueError("Cannot route edge without crossing a node; review the layout")
        route = [targets[finish], finish]
        while previous[route[-1]] is not None:
            point = previous[route[-1]]
            route.append(point)
        route.append(roots[route[-1]])
        route.reverse()
        compact = [route[0]]
        for point in route[1:]:
            if math.dist(compact[-1], point) > 1e-8:
                compact.append(point)
        add_route(compact, source, target)
    return routes
