from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


def extract_drawio_semantics(path: str | Path) -> dict[str, Any]:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    nodes = {}
    groups: dict[str, list[str]] = {}
    edges = []
    edge_labels = []
    for cell in root.findall(".//mxCell"):
        cell_id = cell.get("id")
        if cell.get("vertex") == "1" and cell_id and not cell_id.startswith("group-"):
            nodes[cell_id] = cell.get("value", "")
            if cell.get("data-group"):
                groups.setdefault(cell.get("data-group"), []).append(cell_id)
        if cell.get("edge") == "1":
            pair = (cell.get("source"), cell.get("target"))
            edges.append(pair)
            edge_labels.append((*pair, cell.get("value", "")))
    return {"nodes": nodes, "edges": sorted(edges), "edge_labels": sorted(edge_labels), "groups": {key: sorted(value) for key, value in groups.items()}}


def extract_figma_semantics(scene: dict[str, Any]) -> dict[str, Any]:
    nodes = {node["source_id"]: node.get("name", "") for node in scene.get("nodes", []) if node.get("kind") == "RECTANGLE" and node.get("source_id")}
    edge_nodes = [node for node in scene.get("nodes", []) if node.get("kind") in {"LINE", "VECTOR"}]
    edges = sorted((node.get("source"), node.get("target")) for node in edge_nodes)
    edge_labels = sorted((node.get("source"), node.get("target"), node.get("label", "")) for node in edge_nodes)
    groups = {node["source_id"]: sorted(node.get("children", [])) for node in scene.get("nodes", []) if node.get("kind") == "FRAME" and node.get("source_id") and node.get("children")}
    return {"nodes": nodes, "edges": edges, "edge_labels": edge_labels, "groups": groups}


def compare_semantics(spec: dict[str, Any], artifact: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_nodes = {node["id"]: node["label"] for node in spec.get("nodes", [])}
    actual_nodes = artifact.get("nodes", {})
    for source_id, label in expected_nodes.items():
        if source_id not in actual_nodes:
            findings.append({"code": "missing_node", "source_id": source_id, "message": f"missing node: {source_id}"})
        elif actual_nodes[source_id] != label:
            findings.append({"code": "label_mismatch", "source_id": source_id, "message": f"label mismatch for {source_id}"})
    for source_id in actual_nodes:
        if source_id not in expected_nodes:
            findings.append({"code": "unexpected_node", "source_id": source_id, "message": f"unexpected node: {source_id}"})
    expected_edges = [(edge["source"], edge["target"]) for edge in spec.get("edges", [])]
    actual_edges = [tuple(edge) for edge in artifact.get("edges", [])]
    expected_counts, actual_counts = Counter(expected_edges), Counter(actual_edges)
    for source, target in sorted((expected_counts - actual_counts).elements()):
        findings.append({"code": "missing_edge", "source_id": source, "message": f"missing edge: {source}->{target}"})
    for source, target in sorted((actual_counts - expected_counts).elements()):
        findings.append({"code": "unexpected_edge", "source_id": source or "", "message": f"unexpected edge: {source}->{target}"})
    expected_labels = [(edge["source"], edge["target"], edge.get("label", "")) for edge in spec.get("edges", [])]
    actual_labels = [tuple(edge) for edge in artifact.get("edge_labels", [])]
    for source, target, label in sorted((Counter(expected_labels) - Counter(actual_labels)).elements()):
        findings.append({"code": "missing_edge_label", "source_id": source, "message": f"missing label for {source}->{target}: {label}"})
    for source, target, label in sorted((Counter(actual_labels) - Counter(expected_labels)).elements()):
        findings.append({"code": "unexpected_edge_label", "source_id": source or "", "message": f"unexpected label for {source}->{target}: {label}"})
    expected_groups = {group["id"]: sorted(group["children"]) for group in spec.get("groups", [])}
    actual_groups = artifact.get("groups", {})
    for group_id, children in expected_groups.items():
        if actual_groups.get(group_id) != children:
            findings.append({"code": "group_mismatch", "source_id": group_id, "message": f"group membership mismatch for {group_id}"})
    return findings
