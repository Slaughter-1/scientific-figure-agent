from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def extract_drawio_semantics(path: str | Path) -> dict[str, Any]:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    nodes = {}
    edges = set()
    for cell in root.findall(".//mxCell"):
        cell_id = cell.get("id")
        if cell.get("vertex") == "1" and cell_id and not cell_id.startswith("group-"):
            nodes[cell_id] = cell.get("value", "")
        if cell.get("edge") == "1":
            edges.add((cell.get("source"), cell.get("target")))
    return {"nodes": nodes, "edges": sorted(edges)}


def extract_figma_semantics(scene: dict[str, Any]) -> dict[str, Any]:
    nodes = {node["source_id"]: node.get("name", "") for node in scene.get("nodes", []) if node.get("kind") == "RECTANGLE" and node.get("source_id")}
    edges = sorted((node.get("source"), node.get("target")) for node in scene.get("nodes", []) if node.get("kind") == "LINE")
    return {"nodes": nodes, "edges": edges}


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
    expected_edges = {(edge["source"], edge["target"]) for edge in spec.get("edges", [])}
    actual_edges = set(tuple(edge) for edge in artifact.get("edges", []))
    for source, target in sorted(expected_edges - actual_edges):
        findings.append({"code": "missing_edge", "source_id": source, "message": f"missing edge: {source}->{target}"})
    for source, target in sorted(actual_edges - expected_edges):
        findings.append({"code": "unexpected_edge", "source_id": source or "", "message": f"unexpected edge: {source}->{target}"})
    return findings
