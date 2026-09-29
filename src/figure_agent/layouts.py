from __future__ import annotations

from typing import Any
import heapq
import math
from collections import defaultdict

Point = tuple[float, float]
Box = tuple[float, float, float, float]
_EPS = 1e-8


def compact_route(points: list[Point]) -> list[Point]:
    """Remove zero segments and consecutive collinear runs within one edge."""
    result: list[Point] = []
    for point in points:
        point = tuple(point)
        if result and math.dist(result[-1], point) < _EPS:
            continue
        if len(result) >= 2:
            a, b = result[-2:]
            cross = (b[0]-a[0])*(point[1]-b[1]) - (b[1]-a[1])*(point[0]-b[0])
            dot = (b[0]-a[0])*(point[0]-b[0]) + (b[1]-a[1])*(point[1]-b[1])
            if abs(cross) < _EPS and dot > 0:
                result.pop()
        result.append(point)
    return result


def _segments(points):
    points = compact_route(points)
    return list(zip(points, points[1:]))


def _parallel_overlap(a, b, c, d):
    """Return projected length, line gap and opposite direction for parallel segments."""
    axis = 0 if abs(a[1]-b[1]) < _EPS else 1
    other = 1-axis
    if abs(c[other]-d[other]) > _EPS:
        return 0.0, math.inf, False
    length = min(max(a[axis], b[axis]), max(c[axis], d[axis])) - max(min(a[axis], b[axis]), min(c[axis], d[axis]))
    return max(0.0, length), abs(a[other]-c[other]), (b[axis]-a[axis])*(d[axis]-c[axis]) < 0


def route_crossings(left: list[Point], right: list[Point]) -> list[dict[str, Any]]:
    findings = []
    for a, b in _segments(left):
        for c, d in _segments(right):
            if _proper_crossing(a, b, c, d):
                findings.append({"code": "edge_crossing", "severity": "error",
                                 "message": "different edges cross at an interior point"})
    return findings


def route_self_conflicts(points: list[Point]) -> list[dict[str, Any]]:
    segments = _segments(points)
    return [{"code": "edge_self_overlap", "severity": "error",
             "message": "one edge folds back over its own path"}
            for index, (a, b) in enumerate(segments)
            for c, d in segments[index+1:]
            if (lambda overlap: overlap[0] > _EPS and overlap[1] < _EPS)(
                _parallel_overlap(a, b, c, d))]


def route_pair_conflicts(left: list[Point], right: list[Point], *, mm_per_unit: float) -> list[dict[str, Any]]:
    """Report shared paths or long parallel runs closer than the final 2 mm limit."""
    findings = []
    for a, b in _segments(left):
        for c, d in _segments(right):
            length, gap, reverse = _parallel_overlap(a, b, c, d)
            if length <= _EPS:
                continue
            if gap < _EPS or (gap * mm_per_unit < 2.0-_EPS and length * mm_per_unit > 5.0+_EPS):
                code = "edge_reverse_overlap" if reverse and gap < _EPS else "edge_visual_merge"
                findings.append({"code": code, "severity": "error", "message": "different edges share a path or a close parallel corridor",
                                 "length_mm": length * mm_per_unit, "gap_mm": gap * mm_per_unit})
    return findings


def segment_box_distance(a: Point, b: Point, box: Box) -> float:
    """Euclidean clearance from an orthogonal segment to an axis-aligned box."""
    l, bottom, r, top = box
    dx = max(l-max(a[0], b[0]), min(a[0], b[0])-r, 0.0)
    dy = max(bottom-max(a[1], b[1]), min(a[1], b[1])-top, 0.0)
    return math.hypot(dx, dy)


def box_distance(a: Box, b: Box) -> float:
    return math.hypot(max(a[0]-b[2], b[0]-a[2], 0), max(a[1]-b[3], b[1]-a[3], 0))


def _enters_box(a, b, box):
    l, bottom, r, top = box
    if abs(a[0]-b[0]) < _EPS:
        return l+_EPS < a[0] < r-_EPS and min(max(a[1], b[1]), top)-max(min(a[1], b[1]), bottom) > _EPS
    return bottom+_EPS < a[1] < top-_EPS and min(max(a[0], b[0]), r)-max(min(a[0], b[0]), l) > _EPS


def _crosses(a, b, c, d):
    if abs(a[0]-b[0]) < _EPS:
        a, b, c, d = c, d, a, b
    return (abs(a[1]-b[1]) < _EPS and abs(c[0]-d[0]) < _EPS
            and min(a[0], b[0])-_EPS <= c[0] <= max(a[0], b[0])+_EPS
            and min(c[1], d[1])-_EPS <= a[1] <= max(c[1], d[1])+_EPS)


def _proper_crossing(a, b, c, d):
    """Return true for an interior orthogonal crossing, excluding endpoints."""
    if not _crosses(a, b, c, d):
        return False
    if abs(a[1]-b[1]) < _EPS:
        return (min(a[0], b[0])+_EPS < c[0] < max(a[0], b[0])-_EPS
                and min(c[1], d[1])+_EPS < a[1] < max(c[1], d[1])-_EPS)
    return (min(c[0], d[0])+_EPS < a[0] < max(c[0], d[0])-_EPS
            and min(a[1], b[1])+_EPS < c[1] < max(a[1], b[1])-_EPS)


def _forward_structure(spec):
    successors = {n["id"]: set() for n in spec["nodes"]}
    indegree = dict.fromkeys(successors, 0)
    for edge in spec.get("edges", []):
        if edge.get("type", "data_flow") == "data_flow" and edge["target"] not in successors[edge["source"]]:
            successors[edge["source"]].add(edge["target"])
            indegree[edge["target"]] += 1
    ranks = dict.fromkeys(successors, 0)
    ready = sorted(n for n, degree in indegree.items() if not degree)
    visited = []
    while ready:
        node = ready.pop(0)
        visited.append(node)
        for target in sorted(successors[node]):
            ranks[target] = max(ranks[target], ranks[node]+1)
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()

    def reaches(source, target):
        pending, seen = list(successors[source]), set()
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node not in seen:
                seen.add(node)
                pending.extend(successors[node])
        return False

    roles = ["feedback" if e.get("type") == "control_flow" and reaches(e["target"], e["source"]) else "forward"
             for e in spec.get("edges", [])]
    return ranks, roles, len(visited) == len(successors)


def _is_linear_structure(spec) -> bool:
    """Return true when the graph has no fan-in/fan-out geometry to protect."""
    outgoing = defaultdict(int)
    incoming = defaultdict(int)
    for edge in spec.get("edges", []):
        outgoing[edge["source"]] += 1
        incoming[edge["target"]] += 1
    return all(value <= 1 for value in outgoing.values()) and all(value <= 1 for value in incoming.values())


def _layout_node_size(spec, paper_width_mm: float) -> tuple[float, float]:
    """Use a taller candidate-only box when final-size wrapping needs it."""
    width, height = node_size(spec)
    constraints = spec.get("constraints", {})
    labels = [str(node.get("label", "")) for node in spec.get("nodes", [])]
    if (constraints.get("paper_width") and labels
            and max(map(len, labels)) >= 6):
        if paper_width_mm <= 100 and not _is_linear_structure(spec):
            height = max(height, 2.4)
        elif paper_width_mm > 100:
            height = max(height, 1.0)
        elif paper_width_mm <= 100 and len(labels) > 6:
            height = max(height, 2.4)
    return width, height


def _plan_positions(spec, family, paper_width_mm, ranks, acyclic):
    if family == "loop" and acyclic and len(spec["nodes"]) == 4:
        layers = defaultdict(list)
        for node_id, rank in ranks.items():
            layers[rank].append(node_id)
        if len(layers) == 3 and [len(layers[rank]) for rank in sorted(layers)] == [1, 2, 1]:
            # The diamond graph is planar around the four cardinal positions
            # when the source and sink oppose each other, with both parallel
            # branches on the other axis. Array order alone put one branch
            # across the center of the other in the reviewed loop candidate.
            radius = max(2.5, len(spec["nodes"]) * 0.6)
            center = radius + 1.5
            source, branch_rank, target = [layers[rank] for rank in sorted(layers)]
            upper, lower = sorted(branch_rank)
            return {source[0]: (center-radius, center),
                    upper: (center, center+radius),
                    lower: (center, center-radius),
                    target[0]: (center+radius, center)}
    width, height = _layout_node_size(spec, paper_width_mm)
    constraints = spec.get("constraints", {})
    candidate_eval = bool(constraints.get("paper_width"))
    labels = [str(node.get("label", "")) for node in spec.get("nodes", [])]
    dense = len(labels) >= 5 or (labels and max(map(len, labels)) >= 12)
    linear = _is_linear_structure(spec)
    # Keep genuinely linear pipelines vertical in a narrow column. A branched
    # or feedback workflow needs the regular routed layout; stacking every
    # node vertically can create a pathological tall single-column canvas.
    vertical_pipeline = (family == "pipeline" and acyclic and linear
                         and paper_width_mm <= 100 and len(spec.get("nodes", [])) <= 6)
    if paper_width_mm <= 100 and candidate_eval and acyclic and linear and len(spec.get("nodes", [])) <= 6:
        return {node_id: (0.0, -index * (height + 0.45))
                for index, node_id in enumerate(sorted(ranks, key=lambda item: (ranks[item], item)))}
    if paper_width_mm <= 100 and family == "pipeline" and (not linear or len(spec.get("nodes", [])) > 6):
        # A single horizontal row makes final-size node boxes too narrow for
        # wrapped labels. A compact three-column grid keeps the same nodes and
        # edges while giving each label usable physical width and height.
        columns = 3
        ordered = sorted((node["id"] for node in spec["nodes"]), key=str)
        return {node_id: ((index % columns - (columns - 1) / 2) * (width + 1.9),
                          -(index // columns) * (height + 2.0))
                for index, node_id in enumerate(ordered)}
    if vertical_pipeline:
        # Final-size single-column figures need a real vertical canvas.  The
        # legacy pipeline layout kept all nodes on one horizontal baseline,
        # making the fixed node boxes collapse when scaled to 85 mm.
        return {node_id: (0.0, -index * (height + 2.0))
                for index, node_id in enumerate(sorted(ranks, key=lambda item: (ranks[item], item)))}
    if paper_width_mm > 100 and family in {"swimlane", "hierarchy"} and not spec.get("edges"):
        # A containment-only group has no rank direction to communicate. Keep
        # its members on one horizontal row in the wider column so the group
        # box does not become an artificial half-metre-tall figure.
        ordered = sorted(spec["nodes"], key=lambda node: node["id"])
        return {node["id"]: ((index - (len(ordered) - 1) / 2) * (width + 1.2), 0.0)
                for index, node in enumerate(ordered)}
    if family not in {"swimlane", "hierarchy"} or not acyclic:
        return layout_nodes(spec, family=family)
    layers = defaultdict(list)
    for node_id, rank in ranks.items():
        layers[rank].append(node_id)
    positions = {}
    vertical_group_layout = paper_width_mm <= 100
    for rank, ids in layers.items():
        for index, node_id in enumerate(sorted(ids)):
            offset = index - (len(ids)-1)/2
            positions[node_id] = ((rank*(width+1.9), -offset*(height+1.8)) if paper_width_mm > 100 and not vertical_group_layout
                                  else (offset*(width+1.2), -rank*(height+2.0)))
    return positions


_NORMALS = {"east": (1, 0), "west": (-1, 0), "north": (0, 1), "south": (0, -1)}
_OPPOSITE = {"east": "west", "west": "east", "north": "south", "south": "north"}


def _port(box, side, offset):
    l, b, r, t = box
    point = {"east": (r, b+(t-b)*offset), "west": (l, b+(t-b)*offset),
             "north": (l+(r-l)*offset, t), "south": (l+(r-l)*offset, b)}[side]
    return {"side": side, "offset": offset, "point": point}


def _allocate_ports(spec, positions, boxes, roles, scale, vertical, spread_sides=False):
    requests = defaultdict(list)
    edges = spec.get("edges", [])
    for i, edge in enumerate(edges):
        source, target = edge["source"], edge["target"]
        sx, sy = positions[source]
        tx, ty = positions[target]
        if roles[i] == "feedback":
            # Pick an outer side with clear outward rays before reserving ports.
            preferred = ["west", "east", "north", "south"] if vertical else (["east", "west", "north", "south"] if sx >= tx else ["west", "east", "north", "south"])
            def ray_obstacles(side):
                dx, dy = _NORMALS[side]
                return sum(_enters_box(positions[node], (positions[node][0]+dx*1000, positions[node][1]+dy*1000), box)
                           for node in (source, target) for other, box in boxes.items() if other != node)
            if not vertical and sx > tx and abs(sy-ty) < boxes[source][3]-boxes[source][1]:
                # A right-to-left feedback edge should leave the source on
                # its exterior side. A north stub would force the visibility
                # grid to climb and then fold back over that same stub when
                # the source node sits close to the top boundary.
                sides = ("east", "south") if roles[i] == "feedback" and len(spec.get("nodes", [])) <= 4 else ("north", "south")
            elif not vertical and sx < tx and abs(sy-ty) < boxes[source][3]-boxes[source][1]:
                sides = ("east", "north")
            else:
                side = min(preferred, key=ray_obstacles)
                sides = (side, side)
        else:
            if abs(tx-sx) >= abs(ty-sy):
                side = "east" if tx >= sx else "west"
            else:
                side = "north" if ty >= sy else "south"
            sides = (side, _OPPOSITE[side])
        for node, other, endpoint, side in [(source, target, "source_port", sides[0]), (target, source, "target_port", sides[1])]:
            requests[node, side].append((i, endpoint, other))
    ports = [{} for _ in edges]
    # A long fan-out along a row should leave on the outer side of its source.
    # Sending it through the same east port bank as the short next-node edge
    # made the reviewed pipeline route circle back around the coordinator.
    if not vertical:
        for node, side in list(requests):
            entries = requests[node, side]
            if side != "east" or len(entries) < 2:
                continue
            row_sources = [entry for entry in entries if entry[1] == "source_port"
                           and abs(positions[entry[2]][1]-positions[node][1]) < boxes[node][3]-boxes[node][1]]
            if len(row_sources) > 1:
                farthest = max(row_sources, key=lambda entry: positions[entry[2]][0]-positions[node][0])
                entries.remove(farthest)
                requests[node, "north"].append(farthest)
    # Fixed legacy centers can place several unrelated relations on one side
    # of a node. Spread those terminal groups across adjacent sides before
    # routing; this keeps the centers unchanged while removing false junctions.
    if spread_sides:
        for node, side in list(requests):
            entries = requests[node, side]
            if len(entries) <= 1 or not all(entry[1] == "source_port" for entry in entries):
                continue
            alternatives = [candidate for candidate in ("north", "south", "east", "west") if candidate != side]
            for entry in entries[1:]:
                destination = min(alternatives, key=lambda candidate: len(requests[node, candidate]))
                requests[node, destination].append(entry)
            requests[node, side] = entries[:1]

    # Move overflow to adjacent sides rather than compressing terminal spacing.
    for node, side in list(requests):
        entries = requests[node, side]
        box = boxes[node]
        length = (box[3]-box[1]) if side in {"east", "west"} else (box[2]-box[0])
        capacity = max(1, int(length*0.6*scale/2.2)+1)
        while len(entries) > capacity:
            entry = entries.pop()
            adjacent = ["north", "south"] if side in {"east", "west"} else ["east", "west"]
            destination = min(adjacent, key=lambda s: len(requests[node, s]))
            requests[node, destination].append(entry)
    for (node, side), entries in requests.items():
        axis = 1 if side in {"east", "west"} else 0
        entries.sort(key=lambda x: (positions[x[2]][axis], -math.dist(positions[node], positions[x[2]]),
                                    edges[x[0]]["source"], edges[x[0]]["target"], edges[x[0]].get("label", ""), x[1]))
        for index, (edge_index, endpoint, _) in enumerate(entries):
            offset = 0.5 if len(entries) == 1 else 0.2 + 0.6*index/(len(entries)-1)
            ports[edge_index][endpoint] = _port(boxes[node], side, offset)
    if spread_sides:
        # In the reviewed fixed layout, both parallel agents sit above the
        # answer node, which is to their left. Splitting the two incoming
        # terminals between west and north leaves a separate west departure
        # and west arrival for the answer-to-retriever feedback.
        for feedback_index, edge in enumerate(edges):
            if roles[feedback_index] != "feedback":
                continue
            sink, retriever = edge["source"], edge["target"]
            incoming = [(index, item) for index, item in enumerate(edges)
                        if roles[index] == "forward" and item["target"] == sink]
            if len(incoming) != 2 or not any(item["source"] == retriever for _, item in incoming):
                continue
            other_index, other_edge = next((index, item) for index, item in incoming if item["source"] != retriever)
            retriever_index = next(index for index, item in incoming if item["source"] == retriever)
            if (positions[sink][1] < positions[retriever][1]
                    and abs(positions[other_edge["source"]][1]-positions[retriever][1]) < _EPS
                    and positions[sink][0] < positions[retriever][0] < positions[other_edge["source"]][0]):
                ports[retriever_index]["target_port"] = _port(boxes[sink], "west", 0.75)
                ports[other_index]["target_port"] = _port(boxes[sink], "north", 0.25)
                ports[feedback_index]["source_port"] = _port(boxes[sink], "west", 0.5)
                ports[feedback_index]["target_port"] = _port(boxes[retriever], "west", 0.35)
    return ports


def _grid_route(start, end, boxes, occupied, reserved, bounds, scale, outer_side=None, *, avoid_junctions=False):
    """Visibility-grid routing, ordered by crossings, bends, then length."""
    gap = 2.2/scale
    # A terminal stub needs to clear the node, but on a narrow single-column
    # canvas it must not consume the entire inter-node gap.
    stub = min(3.2/scale, 0.22)
    source, target = start["point"], end["point"]
    def outer(port):
        dx, dy = _NORMALS[port["side"]]
        return (port["point"][0]+dx*stub, port["point"][1]+dy*stub)
    a, b = outer(start), outer(end)
    source_normal = _NORMALS[start["side"]]

    def leaves_source(point, next_point):
        if math.dist(point, a) >= _EPS:
            return True
        return ((next_point[0]-point[0])*source_normal[0]
                + (next_point[1]-point[1])*source_normal[1]) >= -_EPS

    occupied_segments = [seg for route in occupied for seg in _segments(route)]
    reserved_segments = [seg for route in reserved for seg in _segments(route)]

    def clear(p, q):
        if any(_enters_box(p, q, box) for box in boxes.values()):
            return False
        # Terminal reservation is used to choose distinct ports, but a nearby
        # terminal stub is not a solid obstacle: treating every stub as one
        # makes a narrow but valid adjacent-node gap unroutable.
        for c, d in occupied_segments:
            length, distance, _ = _parallel_overlap(p, q, c, d)
            if length > _EPS and distance < gap-_EPS:
                return False
            # A route may not terminate on an interior point of another
            # route. In fixed-position layouts this otherwise creates a
            # false junction that looks like a shared channel.
            if avoid_junctions and _crosses(p, q, c, d):
                return False
        return True

    def cost(route):
        segments = _segments(route)
        return (sum(_crosses(p, q, c, d) for p, q in segments for c, d in occupied_segments),
                len(segments)-1, sum(math.dist(p, q) for p, q in segments))

    l, bottom, r, top = bounds
    left_lane, right_lane, bottom_lane, top_lane = l+3/scale, r-3/scale, bottom+3/scale, top-10/scale
    if outer_side == "west":
        left_lane = min(left_lane, (a[0]+l)/2)
    elif outer_side == "east":
        right_lane = max(right_lane, (a[0]+r)/2)
    elif outer_side == "south":
        bottom_lane = min(bottom_lane, (a[1]+bottom)/2)
    elif outer_side == "north":
        top_lane = max(top_lane, (a[1]+top)/2)
    candidates = [
        [source, a, (b[0], a[1]), b, target],
        [source, a, (a[0], b[1]), b, target],
    ]
    for x in [(a[0]+b[0])/2, left_lane, right_lane]:
        candidates.append([source, a, (x, a[1]), (x, b[1]), b, target])
    for y in [(a[1]+b[1])/2, bottom_lane, top_lane]:
        candidates.append([source, a, (a[0], y), (b[0], y), b, target])
    if outer_side:
        corridor = {"north": top_lane, "south": bottom_lane, "east": right_lane, "west": left_lane}[outer_side]
        if outer_side in {"east", "west"}:
            # Lateral feedback routes first move to the exterior, then use a
            # perimeter lane before approaching the target. The direct
            # corridor otherwise cuts through a fan-in route near the source.
            # Keep a south-entering feedback lane below the ordinary forward
            # bottom corridor; reusing that corridor creates a long shared
            # segment in the pipeline candidate.
            target_lane = top_lane if end["side"] == "north" else bottom + 0.5/scale
            candidates.insert(0, [source, a, (corridor, a[1]), (corridor, target_lane),
                                  (b[0], target_lane), b, target])
        axis = 1 if outer_side in {"north", "south"} else 0
        candidates = [route for route in candidates if any(abs(p[axis]-corridor) < _EPS for p in route)]
    valid = []
    for route in candidates:
        compact = compact_route(route)
        if (all(clear(p, q) for p, q in _segments(compact))
                and all(leaves_source(p, q) for p, q in zip(compact, compact[1:]))):
            valid.append(compact)
    if valid:
        best = min(valid, key=cost)
        # Parallel reuse and node penetration have already been rejected by
        # ``clear``.  A perpendicular crossing is a visible, finite cost and
        # is preferable to falling through to a route that doubles back over
        # its own terminal stub.
        return best

    xs = {source[0], a[0], b[0], target[0], left_lane, right_lane}
    ys = {source[1], a[1], b[1], target[1], bottom_lane, top_lane}
    for bl, bb, br, bt in boxes.values():
        xs.update((bl-stub, br+stub))
        ys.update((bb-stub, bt+stub))
    for p, q in occupied_segments + reserved_segments:
        xs.update((p[0]-gap, p[0]+gap, q[0]-gap, q[0]+gap))
        ys.update((p[1]-gap, p[1]+gap, q[1]-gap, q[1]+gap))
    xs = sorted({round(x, 9) for x in xs if l+_EPS < x < r-_EPS} | {a[0], b[0]})
    ys = sorted({round(y, 9) for y in ys if bottom+_EPS < y < top-6/scale} | {a[1], b[1]})
    xindex, yindex = {x: i for i, x in enumerate(xs)}, {y: i for i, y in enumerate(ys)}
    # Outer feedback must visit its reserved exterior corridor.
    corridor = {"north": top_lane, "south": bottom_lane, "east": right_lane, "west": left_lane}.get(outer_side)
    corridor_axis = 1 if outer_side in {"north", "south"} else 0
    def on_corridor(p):
        return corridor is None or abs(p[corridor_axis]-corridor) < _EPS
    direction = 0 if start["side"] in {"east", "west"} else 1
    root = (a, direction, on_corridor(a))
    distances, previous = {root: (0, 0, 0.0)}, {}
    queue = [((0, 0, 0.0), root)]
    finish = None
    clear_cache = {}
    while queue:
        distance, state = heapq.heappop(queue)
        if distance != distances[state]:
            continue
        p, direction, visited = state
        if p == b and visited:
            finish = state
            break
        i, j = xindex[p[0]], yindex[p[1]]
        neighbors = [(xs[k], p[1]) for k in (i-1, i+1) if 0 <= k < len(xs)] + [(p[0], ys[k]) for k in (j-1, j+1) if 0 <= k < len(ys)]
        for q in neighbors:
            # Returning from the first outside point to the source boundary
            # creates a visible short stub before the actual detour.
            if math.dist(q, source) < _EPS:
                continue
            if not leaves_source(p, q):
                continue
            key = tuple(sorted((p, q)))
            if key not in clear_cache:
                clear_cache[key] = clear(p, q)
            if not clear_cache[key]:
                continue
            new_direction = 0 if abs(q[1]-p[1]) < _EPS else 1
            weight = (distance[0]+sum(_crosses(p, q, c, d) for c, d in occupied_segments),
                      distance[1]+(new_direction != direction), distance[2]+math.dist(p, q))
            next_state = (q, new_direction, visited or on_corridor(q))
            if weight < distances.get(next_state, (math.inf, math.inf, math.inf)):
                distances[next_state], previous[next_state] = weight, state
                heapq.heappush(queue, (weight, next_state))
    if finish is None:
        return None
    path = [target, b]
    while finish in previous:
        finish = previous[finish]
        path.append(finish[0])
    path.append(source)
    path = compact_route(list(reversed(path)))
    return path if all(clear(p, q) for p, q in _segments(path)) else None


def _measure_text(text, size, font):
    from matplotlib.backends.backend_agg import RendererAgg
    from matplotlib.font_manager import FontProperties
    renderer = RendererAgg(1, 1, 72)
    width, height, descent = renderer.get_text_width_height_descent(text, FontProperties(fname=font, size=size), False)
    # The preview uses centered line boxes, not an ink-only bbox.
    return width*25.4/72, max(height+descent, size*1.2)*25.4/72


def _text_box(text, center, size, font, scale, padding_mm=0.6):
    w, h = _measure_text(text, size, font)
    w, h = (w+2*padding_mm)/scale, (h+2*padding_mm)/scale
    x, y = center
    return {"text": text, "box": (x-w/2, y-h/2, x+w/2, y+h/2), "anchor": center, "font_size_pt": size}


def _arrow(route, scale):
    a, tip = route[-2:]
    distance = math.dist(a, tip)
    dx, dy = (tip[0]-a[0])/distance, (tip[1]-a[1])/distance
    length, half_width = 2.0/scale, 0.75/scale
    return [tip, (tip[0]-dx*length-dy*half_width, tip[1]-dy*length+dx*half_width),
            (tip[0]-dx*length+dy*half_width, tip[1]-dy*length-dx*half_width)]


def polygon_box(polygon):
    xs, ys = zip(*polygon)
    return min(xs), min(ys), max(xs), max(ys)


def build_route_plan(spec: dict[str, Any], *, family: str, paper_width_mm: float,
                     positions: dict[str, Point] | None = None) -> dict[str, Any]:
    """Plan presentation geometry without changing any semantic Spec fields.

    Explicit centers are never rescaled. All physical distances refer to the one
    final-size transform recorded in the returned plan. Unroutable edges remain
    represented and produce an error instead of falling back to old paths.
    """
    from matplotlib.font_manager import FontProperties, findfont
    if paper_width_mm <= 20:
        raise ValueError("paper width must exceed the 20 mm total exterior margin")
    ranks, roles, acyclic = _forward_structure(spec)
    supplied_positions = positions is not None
    positions = dict(positions) if supplied_positions else _plan_positions(spec, family, paper_width_mm, ranks, acyclic)
    width, height = _layout_node_size(spec, paper_width_mm)
    constraints = spec.get("constraints", {})
    candidate_eval = bool(constraints.get("paper_width"))
    labels = [str(node.get("label", "")) for node in spec.get("nodes", [])]
    dense = len(labels) >= 5 or (labels and max(map(len, labels)) >= 12)
    linear = _is_linear_structure(spec)
    vertical_layout = paper_width_mm <= 100
    boxes = {node: (x-width/2, y-height/2, x+width/2, y+height/2) for node, (x, y) in positions.items()}
    xmin, ymin = min(b[0] for b in boxes.values()), min(b[1] for b in boxes.values())
    xmax, ymax = max(b[2] for b in boxes.values()), max(b[3] for b in boxes.values())
    scale = (paper_width_mm-20)/(xmax-xmin)
    bounds = (xmin-10/scale, ymin-10/scale, xmax+10/scale, ymax+20/scale)
    style = spec.get("style", {})
    font = findfont(FontProperties(family=[style.get("font_family", "Noto Sans SC"), "Microsoft YaHei", "DejaVu Sans"]))
    plan = {"positions": positions, "node_boxes": boxes, "node_size_units": [width, height],
            "node_size_px": [width * 100, height * 100], "group_boxes": {}, "group_titles": [], "routes": [],
            "bounds": bounds, "paper_width_mm": paper_width_mm, "mm_per_unit": scale, "font_path": font,
            "node_font_size_pt": max(8.0, min(float(style.get("font_sizes", {}).get("node", 9.5)), 9.5)),
            "line_width_pt": max(0.8, float(style.get("edge", {}).get("width", 1.0))), "findings": []}
    if not acyclic:
        plan["findings"].append({"code": "presentation_ambiguous", "severity": "warning", "message": "data-flow skeleton is cyclic; existing node positions retained"})
    for group in spec.get("groups", []):
        members = [boxes[n] for n in group["children"] if n in boxes]
        if not members:
            continue
        box = (min(b[0] for b in members)-2/scale, min(b[1] for b in members)-2/scale,
               max(b[2] for b in members)+2/scale, max(b[3] for b in members)+6/scale)
        plan["group_boxes"][group["id"]] = box
        # Reserve a small physical halo around the glyphs.  The route planner
        # uses this box as an obstacle, so the halo also accounts for line
        # width and font rasterization differences in final-size exports.
        vertical_group = (vertical_layout and family in {"hierarchy", "swimlane"}
                          and candidate_eval)
        title_anchor = (((box[0] + 2.0/scale), box[3]-1.0/scale)
                        if vertical_group else ((box[0]+box[2])/2, box[3]-1.0/scale))
        title = _text_box(group["label"], title_anchor, 8, font, scale, 0.6)
        # The narrow vertical-group anchor is left-biased, while the renderer
        # centers the glyphs around it. Nudge only the title box into the
        # already fixed canvas bounds; do not enlarge or rescale the figure.
        margin = 0.5 / scale
        title_left, _, title_right, _ = title["box"]
        shift = max(0.0, bounds[0] + margin - title_left)
        if title_right + shift > bounds[2] - margin:
            shift = bounds[2] - margin - title_right
        if abs(shift) > _EPS:
            title = _text_box(group["label"], (title["anchor"][0] + shift, title["anchor"][1]), 8, font, scale, 0.6)
        plan["group_titles"].append(title)
    if spec.get("title"):
        plan["title"] = _text_box(spec["title"], ((xmin+xmax)/2, ymax+17/scale), 10, font, scale, 0)
    ports = _allocate_ports(spec, positions, boxes, roles, scale,
                            vertical_layout and not supplied_positions,
                            spread_sides=supplied_positions)
    forward = [e for i, e in enumerate(spec.get("edges", [])) if roles[i] == "forward"]
    out_count, in_count = defaultdict(int), defaultdict(int)
    for edge in forward:
        out_count[edge["source"]] += 1
        in_count[edge["target"]] += 1
    for i, edge in enumerate(spec.get("edges", [])):
        plan["routes"].append({"edge_index": i, "source": edge["source"], "target": edge["target"], "role": roles[i],
                               "fan_out": roles[i] == "forward" and out_count[edge["source"]] > 1,
                               "fan_in": roles[i] == "forward" and in_count[edge["target"]] > 1,
                               **ports[i], "points": [], "label_box": None, "arrow_polygon": []})
    order = sorted(range(len(roles)), key=lambda i: (roles[i] == "feedback", math.dist(positions[spec["edges"][i]["source"]], positions[spec["edges"][i]["target"]]),
                                                   spec["edges"][i]["source"], spec["edges"][i]["target"], spec["edges"][i].get("label", "")))
    occupied = []
    for i in order:
        route = plan["routes"][i]
        reserved = []
        for j in order:
            if j == i:
                continue
            for endpoint in ("source_port", "target_port"):
                port = ports[j][endpoint]
                dx, dy = _NORMALS[port["side"]]
                p = port["point"]
                reserved.append([p, (p[0]+dx*3.2/scale, p[1]+dy*3.2/scale)])
        routing_boxes = dict(boxes)
        title_clearance = 0.0
        routing_boxes.update({
            f"group-title-{j}": (
                t["box"][0] - title_clearance,
                t["box"][1] - title_clearance,
                t["box"][2] + title_clearance,
                t["box"][3] + title_clearance,
            )
            for j, t in enumerate(plan["group_titles"])
        })
        points = _grid_route(route["source_port"], route["target_port"], routing_boxes, occupied, reserved, bounds, scale,
                             route["source_port"]["side"] if route["role"] == "feedback" else None,
                             avoid_junctions=True)
        if points is None:
            # Dense branch layouts can exhaust every non-crossing corridor.
            # Keep the edge represented and let the critic report a real
            # crossing instead of producing an unresolved or missing edge.
            points = _grid_route(route["source_port"], route["target_port"], routing_boxes, occupied, reserved, bounds, scale,
                                 route["source_port"]["side"] if route["role"] == "feedback" else None,
                                 avoid_junctions=False)
        if points is None:
            plan["findings"].append({"code": "routing_unresolved", "severity": "error", "edge_index": i, "message": "no independent route through the available corridors"})
            continue
        route["points"], route["arrow_polygon"] = points, _arrow(points, scale)
        occupied.append(points)
    for route, edge in zip(plan["routes"], spec.get("edges", [])):
        if not edge.get("label") or not route["points"]:
            continue
        size = max(8.0, float(style.get("font_sizes", {}).get("edge", 8)))
        text_width, text_height = _measure_text(edge["label"], size, font)
        candidates = []
        for a, b in _segments(route["points"]):
            horizontal = abs(a[1]-b[1]) < _EPS
            required = (text_width+2.4 if horizontal else text_height+2.4)/scale
            if math.dist(a, b) < required:
                continue
            fractions = (0.5, 0.35, 0.65, 0.2, 0.8) if route["role"] == "feedback" else (0.5, 0.35, 0.65)
            for fraction in fractions:
                base = (a[0]+(b[0]-a[0])*fraction, a[1]+(b[1]-a[1])*fraction)
                # Labels sit beside the segment. Trying both sides allows
                # parallel condition routes to retain their own readable box.
                normal = (0.0, 1.0) if horizontal else (1.0, 0.0)
                offsets = [2.0/scale, -2.0/scale, 4.0/scale, -4.0/scale,
                           6.0/scale, -6.0/scale, 8.0/scale, -8.0/scale,
                           10.0/scale, -10.0/scale]
                for offset in offsets:
                    anchor = (base[0]+normal[0]*offset, base[1]+normal[1]*offset)
                    label = _text_box(edge["label"], anchor, size, font, scale)
                    box = label["box"]
                    if (box[0] < bounds[0] or box[2] > bounds[2]
                            or box[1] < bounds[1] or box[3] > bounds[3]):
                        continue
                    obstacles = list(boxes.values()) + [t["box"] for t in plan["group_titles"]]
                    if plan.get("title"):
                        obstacles.append(plan["title"]["box"])
                    obstacles += [polygon_box(r["arrow_polygon"]) for r in plan["routes"] if r["arrow_polygon"]]
                    obstacles += [r["label_box"]["box"] for r in plan["routes"] if r["label_box"]]
                    if any(box_distance(box, other)*scale < 1.0-_EPS for other in obstacles):
                        continue
                    if any(segment_box_distance(c, d, box)*scale < 1.0-_EPS
                           for c, d in _segments(route["points"])):
                        continue
                    if any(segment_box_distance(c, d, box)*scale < 1.0-_EPS for other in plan["routes"] if other is not route for c, d in _segments(other["points"])):
                        continue
                    own_distance = min(segment_box_distance(c, d, box) for c, d in _segments(route["points"]))
                    other_distance = min(
                        (segment_box_distance(c, d, box)
                         for other in plan["routes"] if other is not route
                         for c, d in _segments(other["points"])),
                        default=math.inf,
                    )
                    # A condition belongs to the feedback route only when it
                    # is physically closer to that route than to every other
                    # route.  This prevents the pipeline label from appearing
                    # to annotate the nearby retrieval-to-answer edge.
                    ownership_required = route["role"] == "feedback" and not supplied_positions
                    if ownership_required and other_distance <= own_distance + 0.25/scale:
                        continue
                    ownership_priority = -(other_distance - own_distance) if route["role"] == "feedback" else 0.0
                    candidates.append((0 if route["role"] == "feedback" else 1,
                                       ownership_priority, not horizontal, -math.dist(a, b), abs(offset), label))
        if candidates:
            route["label_box"] = min(candidates, key=lambda c: c[:3])[-1]
        else:
            plan["findings"].append({"code": "routing_unresolved", "severity": "error", "edge_index": route["edge_index"], "message": "no label location with 1 mm clearance at final font size"})
    return plan


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

    def reverse_route_overlap(left_route, right_route):
        def horizontal_segments(route):
            for start, end in zip(route, route[1:]):
                if abs(start[1] - end[1]) < 1e-8 and abs(start[0] - end[0]) > 1e-8:
                    yield min(start[0], end[0]), max(start[0], end[0]), start[1], start[0] < end[0]

        def vertical_segments(route):
            for start, end in zip(route, route[1:]):
                if abs(start[0] - end[0]) < 1e-8 and abs(start[1] - end[1]) > 1e-8:
                    yield min(start[1], end[1]), max(start[1], end[1]), start[0], start[1] < end[1]

        horizontal_conflict = any(
            left[2] == right[2]
            and left[3] != right[3]
            and min(left[1], right[1]) - max(left[0], right[0]) > 1e-8
            for left in horizontal_segments(left_route)
            for right in horizontal_segments(right_route)
        )
        vertical_conflict = any(
            left[2] == right[2]
            and left[3] != right[3]
            and min(left[1], right[1]) - max(left[0], right[0]) > 1e-8
            for left in vertical_segments(left_route)
            for right in vertical_segments(right_route)
        )
        return horizontal_conflict or vertical_conflict

    def add_route(route, source, target):
        """Append a route, detouring a later edge when it reverses a lane."""
        if any(reverse_route_overlap(route, previous) for previous in routes):
            left = min(box[0] for box in boxes) - clearance
            right = max(box[2] for box in boxes) + clearance
            route_points = [point for previous in routes for point in previous]
            top = max([box[3] for box in boxes] + [point[1] for point in route_points]) + clearance + 0.22
            bottom = min([box[1] for box in boxes] + [point[1] for point in route_points]) - clearance - 0.22
            alternatives = []
            if source[1] < target[1]:
                alternatives.extend([
                    [(source[0], source[1] - height / 2), (source[0], bottom), (target[0] - width / 2, bottom), (target[0] - width / 2, target[1])],
                    [(source[0], source[1] - height / 2), (source[0], bottom), (target[0] + width / 2, bottom), (target[0] + width / 2, target[1])],
                ])
            elif source[1] > target[1]:
                alternatives.extend([
                    [(source[0], source[1] + height / 2), (source[0], top), (target[0] - width / 2, top), (target[0] - width / 2, target[1])],
                    [(source[0], source[1] + height / 2), (source[0], top), (target[0] + width / 2, top), (target[0] + width / 2, target[1])],
                ])
            else:
                alternatives.extend([
                    [(source[0], source[1] + height / 2), (source[0], top), (target[0] - width / 2, top), (target[0] - width / 2, target[1])],
                    [(source[0], source[1] + height / 2), (source[0], top), (target[0] + width / 2, top), (target[0] + width / 2, target[1])],
                ])
            alternatives.extend([
                [(source[0] + width / 2, source[1]), (right, source[1]), (right, target[1]), (target[0] + width / 2, target[1])],
                [(source[0] - width / 2, source[1]), (left, source[1]), (left, target[1]), (target[0] - width / 2, target[1])],
                [(source[0], source[1] + height / 2), (source[0], top), (target[0], top), (target[0], target[1] + height / 2)],
                [(source[0], source[1] - height / 2), (source[0], bottom), (target[0], bottom), (target[0], target[1] - height / 2)],
            ])
            for alternative in alternatives:
                if all(clear(start, end) for start, end in zip(alternative, alternative[1:])) and not any(reverse_route_overlap(alternative, previous) for previous in routes):
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
