from __future__ import annotations

from statistics import mean
import json
from pathlib import Path
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
    outgoing: dict[str, int] = {}
    for edge in actual.get("edges", []):
        outgoing[str(edge.get("source"))] = outgoing.get(str(edge.get("source")), 0) + 1
    actual_branches = sum(1 for count in outgoing.values() if count > 1)
    actual_cycles = 1 if any((edge.get("target"), edge.get("source")) in {(item.get("source"), item.get("target")) for item in actual.get("edges", [])} for edge in actual.get("edges", [])) else 0
    expected_branches = int(expected.get("branches", 0))
    expected_cycles = int(expected.get("cycles", 0))
    return {
        "node_recall": _recall(expected_nodes, actual_nodes),
        "edge_recall": _recall(expected_edges, actual_edges),
        "evidence_coverage": evidence_coverage,
        "branch_recall": 1.0 if expected_branches == 0 and actual_branches == 0 else (1.0 if expected_branches > 0 and actual_branches > 0 else 0.0),
        "cycle_recall": 1.0 if expected_cycles == 0 and actual_cycles == 0 else (1.0 if expected_cycles > 0 and actual_cycles > 0 else 0.0),
    }


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case.get("expected", {}), case.get("actual", {})) for case in cases]
    return {
        "case_count": len(results),
        "mean_node_recall": mean(item["node_recall"] for item in results) if results else 0.0,
        "mean_edge_recall": mean(item["edge_recall"] for item in results) if results else 0.0,
        "mean_evidence_coverage": mean(item["evidence_coverage"] for item in results) if results else 0.0,
        "mean_branch_recall": mean(item["branch_recall"] for item in results) if results else 0.0,
        "mean_cycle_recall": mean(item["cycle_recall"] for item in results) if results else 0.0,
        "cases": results,
    }


def build_evaluation_report(results: list[dict[str, Any]], output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"case_count": len(results), "cases": results, "mean_node_recall": mean([item.get("node_recall", 0.0) for item in results]) if results else 0.0}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
