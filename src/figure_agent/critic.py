from __future__ import annotations

from copy import deepcopy
from typing import Any

from .spec import validate_spec


def critique_spec(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Return deterministic, structured quality findings for a Figure Spec."""
    findings: list[dict[str, str]] = []

    def add(code: str, severity: str, message: str) -> None:
        findings.append({"code": code, "severity": severity, "message": message})

    for error in validate_spec(spec):
        code = "invalid_spec"
        if "style" in error:
            code = "missing_style"
        add(code, "error", error)
    if not spec.get("title"):
        add("missing_title", "warning", "figure title is missing")
    nodes = spec.get("nodes", [])
    labels: dict[str, str] = {}
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        label = str(node.get("label", "")).strip().casefold()
        if label and label in labels:
            add("duplicate_label", "warning", f"nodes {labels[label]} and {node.get('id')} share label: {node.get('label')}")
        elif label:
            labels[label] = str(node.get("id"))
        if spec.get("schema_version") in {"0.2", "0.3"} and not node.get("evidence"):
            add("missing_evidence", "error", f"node {node.get('id')} has no source evidence")
    node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
    for index, edge in enumerate(spec.get("edges", []) if isinstance(spec.get("edges", []), list) else []):
        if isinstance(edge, dict) and (edge.get("source") not in node_ids or edge.get("target") not in node_ids):
            add("dangling_edge", "error", f"edges[{index}] references a missing node")
    if spec.get("figure_type") != "plot" and nodes and not spec.get("edges"):
        add("disconnected_graph", "warning", "diagram has nodes but no edges")
    return findings


def refine_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply only safe metadata repairs and return (refined spec, change codes)."""
    refined = deepcopy(spec)
    changes: list[str] = []
    if not isinstance(refined.get("style"), dict):
        refined["style"] = {}
        changes.append("add_style")
    if not refined.get("title") and refined.get("figure_type"):
        refined["title"] = str(refined["figure_type"]).replace("_", " ").title()
        changes.append("add_title")
    return refined, changes
