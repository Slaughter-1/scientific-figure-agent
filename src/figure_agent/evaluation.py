from __future__ import annotations

from statistics import mean
from typing import Any


def _recall(expected: set[Any], actual: set[Any]) -> float:
    return 1.0 if not expected else len(expected & actual) / len(expected)


def evaluate_case(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    expected_nodes = {str(item) for item in expected.get("nodes", [])}
    actual_nodes = {str(node.get("label", node.get("id", ""))) for node in actual.get("nodes", []) if isinstance(node, dict)}
    expected_edges = {tuple(map(str, edge)) for edge in expected.get("edges", [])}
    actual_edges = {(str(edge.get("source", "")), str(edge.get("target", ""))) for edge in actual.get("edges", []) if isinstance(edge, dict)}
    evidence = actual.get("provenance") or actual.get("evidence")
    return {
        "node_recall": _recall(expected_nodes, actual_nodes),
        "edge_recall": _recall(expected_edges, actual_edges),
        "evidence_coverage": 1.0 if evidence else 0.0,
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
