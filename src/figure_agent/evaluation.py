from __future__ import annotations

from statistics import mean
from typing import Any


def _recall(expected: set[Any], actual: set[Any]) -> float:
    return 1.0 if not expected else len(expected & actual) / len(expected)


def evaluate_case(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    expected_nodes = {str(item) for item in expected.get("nodes", [])}
    node_label_by_id = {
        str(node.get("id")): str(node.get("label", node.get("id", "")))
        for node in actual.get("nodes", [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    actual_nodes = {str(node.get("label", node.get("id", ""))) for node in actual.get("nodes", []) if isinstance(node, dict)}
    expected_edges = {tuple(map(str, edge)) for edge in expected.get("edges", [])}
    actual_edges = {
        (
            node_label_by_id.get(str(edge.get("source")), str(edge.get("source", ""))),
            node_label_by_id.get(str(edge.get("target")), str(edge.get("target", ""))),
        )
        for edge in actual.get("edges", [])
        if isinstance(edge, dict)
    }
    nodes = [node for node in actual.get("nodes", []) if isinstance(node, dict)]
    evidenced_nodes = [node for node in nodes if node.get("evidence") or node.get("provenance")]
    evidence = actual.get("provenance") or actual.get("evidence")
    evidence_coverage = len(evidenced_nodes) / len(nodes) if nodes else (1.0 if evidence else 0.0)
    return {
        "node_recall": _recall(expected_nodes, actual_nodes),
        "edge_recall": _recall(expected_edges, actual_edges),
        "evidence_coverage": evidence_coverage,
    }


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case.get("expected", {}), case.get("actual", {})) for case in cases]
    return {
        "case_count": len(results),
        "mean_node_recall": mean(item["node_recall"] for item in results) if results else 0.0,
        "mean_edge_recall": mean(item["edge_recall"] for item in results) if results else 0.0,
        "mean_evidence_coverage": mean(item["evidence_coverage"] for item in results) if results else 0.0,
        "cases": results,
    }
