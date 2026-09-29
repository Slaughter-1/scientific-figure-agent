#!/usr/bin/env python
"""Compare an independent Figma readback against the frozen C/R1 source scene.

Implements the geometry check in the RC2 C/R1 checklist section 5, which semantic
parity cannot cover: compare_semantics() in src/figure_agent/parity.py matches node
labels, edge endpoints and group membership only. It never inspects vertex counts or
coordinates, so an empty findings list there says nothing about whether a 5- or
6-point polyline survived the round trip.

Nothing here talks to Figma. It consumes a readback that an authorized client already
fetched, so the comparison stays auditable, re-runnable and separable from the write.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_COUNTS = {"FRAME": 2, "RECTANGLE": 4, "TEXT": 5, "VECTOR": 4}
EXPECTED_VERTICES = {0: 2, 1: 2, 2: 5, 3: 6}
EXPECTED_GROUP_CHILDREN = ["generator", "retriever"]

# Already present in the uploaded RoutePlan/scene before any remote round trip. The
# checklist forbids silently removing these and then claiming source fidelity.
SOURCE_KNOWN_FEATURES = [
    {
        "code": "edge3_self_retrace",
        "edge_index": 3,
        "message": (
            "edge:3 passes x=524.668657 -> 708.000000 -> 275.621891 at one y; the span "
            "524.668657..708.000000 (183.331343 scene units) is therefore traversed twice"
        ),
        "classification": "source_feature_not_remote_damage",
    },
]


def _add(findings: list[dict[str, Any]], code: str, message: str, **extra: Any) -> None:
    findings.append({"code": code, "message": message, **extra})


def compare_object_counts(readback: dict[str, Any], src: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    actual: dict[str, int] = {}
    for node in readback.get("nodes") or []:
        kind = str(node.get("kind") or node.get("type") or "UNKNOWN")
        actual[kind] = actual.get(kind, 0) + 1
    for kind, expected in EXPECTED_COUNTS.items():
        got = actual.get(kind, 0)
        if got != expected:
            _add(findings, "object_count_mismatch",
                 f"{kind}: expected {expected}, read back {got}", kind=kind,
                 expected=expected, actual=got)
    # A whole-figure image or one flattened SVG would show up here as missing native kinds.
    if actual.get("VECTOR", 0) == 0 and actual.get("LINE", 0) > 0:
        _add(findings, "legacy_line_edges",
             "edges came back as LINE, not VECTOR: the editable-polyline path was not used")
    for kind in ("IMAGE", "RECTANGLE_IMAGE_FILL"):
        if actual.get(kind):
            _add(findings, "raster_substitution",
                 f"readback contains {kind}, which suggests the figure was placed as an image")
    return actual


def compare_edges(readback: dict[str, Any], src: dict[str, Any], root: dict[str, Any],
                  space: str, tolerance: float, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-edge vertex count, ordered coordinates, ports and arrow direction.

    Matching counts alone is explicitly not a pass: every point is compared in order.
    """
    remote = {}
    for node in readback.get("nodes") or []:
        if str(node.get("kind") or node.get("type")) == "VECTOR":
            key = node.get("edge_index")
            if key is None and isinstance(node.get("source_id"), str) and node["source_id"].startswith("edge:"):
                key = int(node["source_id"].split(":")[1])
            if key is not None:
                remote[int(key)] = node

    rows: list[dict[str, Any]] = []
    for edge_index, expected_count in EXPECTED_VERTICES.items():
        source_node = src["vectors"].get(edge_index)
        node = remote.get(edge_index)
        row: dict[str, Any] = {"edge_index": edge_index, "expected_vertices": expected_count}
        if source_node is not None:
            row["source"] = source_node.get("source")
            row["target"] = source_node.get("target")
            row["role"] = source_node.get("role")
        if node is None:
            _add(findings, "edge_missing", f"edge:{edge_index} absent from readback", edge_index=edge_index)
            row.update({"status": "missing", "actual_vertices": None})
            rows.append(row)
            continue

        points = node.get("points") or node.get("vertices") or []
        row["actual_vertices"] = len(points)
        if len(points) != expected_count:
            _add(findings, "vertex_count_mismatch",
                 f"edge:{edge_index}: expected {expected_count} ordered points, read back {len(points)}",
                 edge_index=edge_index, expected=expected_count, actual=len(points))
            if len(points) == 2 and expected_count > 2:
                _add(findings, "polyline_flattened",
                     f"edge:{edge_index} collapsed to a straight two-point connection",
                     edge_index=edge_index)

        deltas: list[dict[str, Any]] = []
        offset = node.get("parent_chain_offset")
        for position, (expected_point, actual_point) in enumerate(zip(source_node.get("points", []), points)):
            ax, ay = point_to_root_local(actual_point, root, space, offset)
            dx, dy = ax - float(expected_point[0]), ay - float(expected_point[1])
            worst = max(abs(dx), abs(dy))
            deltas.append({"index": position, "dx": dx, "dy": dy, "max_abs": worst})
            if worst > tolerance:
                _add(findings, "point_coordinate_mismatch",
                     f"edge:{edge_index} point {position}: dx={dx:.6f} dy={dy:.6f} exceeds {tolerance}",
                     edge_index=edge_index, point_index=position, dx=dx, dy=dy)
        row["max_abs_delta"] = max((d["max_abs"] for d in deltas), default=None)
        row["point_deltas"] = deltas

        for end in ("source_port", "target_port"):
            expected_side = (source_node.get(end) or {}).get("side")
            actual_side = (node.get(end) or {}).get("side")
            row[end] = {"expected": expected_side, "actual": actual_side}
            if actual_side is None:
                _add(findings, "port_not_reported",
                     f"edge:{edge_index} {end} side not present in readback",
                     edge_index=edge_index, end=end)
            elif actual_side != expected_side:
                _add(findings, "port_mismatch",
                     f"edge:{edge_index} {end}: expected {expected_side}, read back {actual_side}",
                     edge_index=edge_index, end=end)

        marker = node.get("marker_end") or node.get("strokeCap")
        row["marker_end"] = marker
        if not marker:
            _add(findings, "arrow_not_reported",
                 f"edge:{edge_index} has no arrow terminal in readback; a custom field alone is not an arrow",
                 edge_index=edge_index)
        row.setdefault("status", "compared")
        rows.append(row)
    return rows


def looks_like_echoed_source(readback: dict[str, Any], scene: dict[str, Any]) -> bool:
    """Detect a readback that is really the pre-send scene handed straight back.

    Section 5 forbids returning the scene that was sent, so an exact node-list match
    with no Figma node ids anywhere is evidence of a non-independent read, not a pass.
    """
    nodes = readback.get("nodes") or []
    if any(node.get("node_id") for node in nodes):
        return False
    return json.dumps(nodes, sort_keys=True) == json.dumps(scene.get("nodes"), sort_keys=True)


def to_root_local(node: dict[str, Any], root: dict[str, Any], space: str) -> tuple[float, float]:
    """Return the node origin in outer-Frame local coordinates.

    Moving the Frame elsewhere on the canvas is a whole-figure translation and must not
    be read as route drift, so absolute coordinates are rebased onto the root frame. A
    client that nested nodes must either report absolute coordinates or declare the
    accumulated ancestor offset; otherwise group-relative values would be compared
    against source coordinates that are not group-relative.
    """
    x, y = float(node.get("x", 0.0)), float(node.get("y", 0.0))
    if space == "absolute_canvas":
        x -= float(root.get("x", 0.0))
        y -= float(root.get("y", 0.0))
    offset = node.get("parent_chain_offset")
    if offset:
        x += float(offset[0])
        y += float(offset[1])
    return x, y


def point_to_root_local(point: Any, root: dict[str, Any], space: str, offset: Any = None) -> tuple[float, float]:
    x, y = float(point[0]), float(point[1])
    if space == "absolute_canvas":
        x -= float(root.get("x", 0.0))
        y -= float(root.get("y", 0.0))
    if offset:
        x += float(offset[0])
        y += float(offset[1])
    return x, y


def compare_boxes(readback: dict[str, Any], src: dict[str, Any], root: dict[str, Any],
                  space: str, tolerance: float, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Business-node rectangles and the five TEXT units, in outer-Frame local coordinates."""
    remote: dict[str, dict[str, Any]] = {}
    for node in readback.get("nodes") or []:
        if node.get("source_id"):
            remote[str(node["source_id"])] = node

    rows: list[dict[str, Any]] = []
    for kind, table in (("RECTANGLE", src["rects"]), ("TEXT", src["texts"])):
        for source_id, expected in table.items():
            node = remote.get(source_id)
            row: dict[str, Any] = {"kind": kind, "source_id": source_id}
            if node is None:
                _add(findings, "object_missing", f"{kind} {source_id} absent from readback",
                     source_id=source_id)
                row["status"] = "missing"
                rows.append(row)
                continue
            x, y = to_root_local(node, root, space)
            deltas = {
                "dx": x - float(expected["x"]),
                "dy": y - float(expected["y"]),
                "dw": float(node.get("width", 0.0)) - float(expected.get("width", 0.0)),
                "dh": float(node.get("height", 0.0)) - float(expected.get("height", 0.0)),
            }
            row["deltas"] = deltas
            worst = max(abs(value) for value in deltas.values())
            row["max_abs_delta"] = worst
            if worst > tolerance:
                _add(findings, "box_mismatch",
                     f"{kind} {source_id} bounds differ by {worst:.6f} (tolerance {tolerance})",
                     source_id=source_id, **deltas)
            if kind == "TEXT":
                expected_chars = expected.get("characters")
                actual_chars = node.get("characters")
                row["characters"] = {"expected": expected_chars, "actual": actual_chars}
                if actual_chars != expected_chars:
                    _add(findings, "text_mismatch",
                         f"TEXT {source_id}: expected {expected_chars!r}, read back {actual_chars!r}",
                         source_id=source_id)
                if not node.get("editable", True):
                    _add(findings, "text_not_editable",
                         f"TEXT {source_id} came back as outlines or a non-editable unit",
                         source_id=source_id)
                row["font"] = {"family": node.get("font_family"), "size_pt": node.get("font_size_pt"),
                               "expected_size_pt": expected.get("font_size_pt")}
                if source_id == "edge:3:label":
                    expected_anchor = expected.get("anchor")
                    actual_anchor = node.get("anchor")
                    row["anchor"] = {"expected": expected_anchor, "actual": actual_anchor}
                    if actual_anchor is None:
                        _add(findings, "anchor_not_reported",
                             "edge:3:label anchor/alignment not present in readback")
                    else:
                        ax, ay = point_to_root_local(actual_anchor, root, space,
                                                     node.get("parent_chain_offset"))
                        drift = max(abs(ax - float(expected_anchor[0])), abs(ay - float(expected_anchor[1])))
                        row["anchor_max_abs_delta"] = drift
                        if drift > tolerance:
                            _add(findings, "anchor_mismatch",
                                 f"edge:3:label anchor differs by {drift:.6f}")
                    if node.get("edge_index") != expected.get("edge_index"):
                        _add(findings, "label_edge_mapping_mismatch",
                             "edge:3:label is not mapped to edge_index 3 in readback")
            row.setdefault("status", "compared")
            rows.append(row)
    return rows


def compare_group(readback: dict[str, Any], src: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Group membership must stay retriever + generator, and stay a FRAME."""
    expected = src["group"]
    node = next((n for n in (readback.get("nodes") or [])
                 if str(n.get("source_id") or "") == "agent-loop"), None)
    if node is None:
        _add(findings, "group_missing", "agent-loop frame absent from readback")
        return {"status": "missing"}
    kind = str(node.get("kind") or node.get("type"))
    children = sorted(str(child) for child in (node.get("children") or []))
    result = {"status": "compared", "kind": kind, "children": children,
              "expected_children": EXPECTED_GROUP_CHILDREN,
              "expected_kind": str(expected.get("kind")) if expected else "FRAME"}
    if kind != "FRAME":
        _add(findings, "group_kind_mismatch",
             f"agent-loop came back as {kind}; the source unit is a FRAME, not a GROUP")
    if children != EXPECTED_GROUP_CHILDREN:
        _add(findings, "group_membership_mismatch",
             f"agent-loop members: expected {EXPECTED_GROUP_CHILDREN}, read back {children}")
    if node.get("clips_content") and not node.get("cross_group_edges_intact", True):
        _add(findings, "group_clipping",
             "agent-loop clips content and the client reports cross-group geometry was cut")
    return result


def index_source(scene: dict[str, Any]) -> dict[str, Any]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for node in scene["nodes"]:
        by_kind.setdefault(node["kind"], []).append(node)
    return {
        "by_kind": by_kind,
        "vectors": {node["edge_index"]: node for node in by_kind.get("VECTOR", [])},
        "rects": {node["source_id"]: node for node in by_kind.get("RECTANGLE", [])},
        "texts": {node["source_id"]: node for node in by_kind.get("TEXT", [])},
        "group": next((n for n in by_kind.get("FRAME", []) if n.get("source_id")), None),
        "root": next((n for n in by_kind.get("FRAME", []) if not n.get("source_id")), None),
    }


def compare(readback: dict[str, Any], scene: dict[str, Any], *, tolerance: float) -> dict[str, Any]:
    src = index_source(scene)
    findings: list[dict[str, Any]] = []

    space = str(readback.get("coordinate_space") or "root_frame_local")
    if space not in {"root_frame_local", "absolute_canvas"}:
        _add(findings, "unknown_coordinate_space",
             f"readback declares coordinate_space={space!r}; cannot rebase safely")
    root = next((n for n in (readback.get("nodes") or [])
                 if str(n.get("kind") or n.get("type")) == "FRAME" and not n.get("source_id")), {})

    echoed = looks_like_echoed_source(readback, scene)
    if echoed:
        _add(findings, "readback_is_echoed_source",
             "readback node list is identical to the pre-send scene and carries no Figma node ids; "
             "this is not an independent read")

    counts = compare_object_counts(readback, src, findings)
    edges = compare_edges(readback, src, root, space, tolerance, findings)
    boxes = compare_boxes(readback, src, root, space, tolerance, findings)
    group = compare_group(readback, src, findings)

    mapped = {str(node["source_id"]): node.get("node_id")
              for node in (readback.get("nodes") or []) if node.get("source_id")}
    unmapped = sorted(key for key, value in mapped.items() if not value)
    if unmapped:
        _add(findings, "node_id_missing",
             f"no Figma node id reported for: {', '.join(unmapped)}")

    transport_fidelity = "pass" if not findings else "fail"
    return {
        "schema_version": "0.1",
        "kind": "C_R1_READBACK_COMPARISON",
        "tolerance_scene_units": tolerance,
        "tolerance_basis": "checklist-suggested execution parameter, not a source threshold or Figma standard",
        "coordinate_space": space,
        "transport_fidelity": transport_fidelity,
        "visual_inspection": "not_covered_by_this_script",
        "object_counts": {"expected": EXPECTED_COUNTS, "actual": counts},
        "group": group,
        "edges": edges,
        "boxes": boxes,
        "node_map": mapped,
        "source_known_features": SOURCE_KNOWN_FEATURES,
        "findings": findings,
        "notes": [
            "Geometry only. Visual legibility, CJK glyph coverage and label clipping need the real "
            "SVG/PDF and a rendered check, per checklist section 6.",
            "A tool-assisted pass here does not make the project's own transport connected; "
            "record the two separately.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="outputs/C-figma-case-a55e7ab/local-scene.json",
                        help="frozen source scene (defaults to the C/R1 bundle)")
    parser.add_argument("--readback", required=True,
                        help="readback-raw.json produced by an independent Figma read")
    parser.add_argument("--output", help="write comparison.json here")
    parser.add_argument("--tolerance", type=float, default=0.01,
                        help="per-coordinate tolerance in scene units (default 0.01)")
    args = parser.parse_args()

    scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    readback = json.loads(Path(args.readback).read_text(encoding="utf-8"))
    report = compare(readback, scene, tolerance=args.tolerance)

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        # Bytes, not text: this host forces core.autocrlf=true and text mode would inject CR.
        Path(args.output).write_bytes(payload.encode("utf-8") + b"\n")
    print(payload)
    return 0 if report["transport_fidelity"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
