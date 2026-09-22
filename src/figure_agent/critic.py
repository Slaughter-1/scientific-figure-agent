from __future__ import annotations

from copy import deepcopy
from typing import Any
import re

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
    # Semantic safety net: if the source evidence explicitly describes a
    # branch, loop, or parallel operation, a collapsed linear graph must be
    # surfaced before it reaches a candidate score or export gate.
    evidence_text = " ".join(
        str(item.get("quote", ""))
        for node in nodes if isinstance(node, dict)
        for item in node.get("evidence", []) if isinstance(node.get("evidence", []), list)
        if isinstance(item, dict)
    )
    metadata = spec.get("metadata", {}) if isinstance(spec.get("metadata"), dict) else {}
    source_text = str(metadata.get("source_text", ""))
    edge_rows = [edge for edge in spec.get("edges", []) if isinstance(edge, dict)]
    edge_evidence = " ".join(
        str(item.get("quote", ""))
        for edge in edge_rows if isinstance(edge, dict)
        for item in edge.get("evidence", []) if isinstance(edge.get("evidence", []), list)
        if isinstance(item, dict)
    )
    # Node labels are often short ("检索器"), while the structural cue lives
    # only in the original paragraph. Always inspect the full provenance text.
    evidence_text = " ".join(part for part in (source_text, evidence_text, edge_evidence) if part)
    outgoing: dict[str, int] = {}
    incoming: dict[str, int] = {}
    for edge in edge_rows:
        outgoing[edge.get("source")] = outgoing.get(edge.get("source"), 0) + 1
        incoming[edge.get("target")] = incoming.get(edge.get("target"), 0) + 1
    branch_cue = re.search(r"根据.+?(?:分为|选择)|(?:输入|结果|状态).+?时|(?:通过|失败|未通过)(?:后|才|则)|分支", evidence_text)
    if branch_cue and not any(count >= 2 for count in outgoing.values()):
        add("missing_branch_structure", "error", "Source evidence describes a condition or branch, but the graph has no fan-out.")
    feedback_cue = re.search(r"(?:回到|循环回到|退回|迭代到|写回)|返回(?:到|至)?\s*(?:检索|规划|生成|前|上|步骤|阶段)", evidence_text)
    if feedback_cue and not any(edge.get("type") == "control_flow" for edge in edge_rows):
        add("missing_feedback_structure", "error", "Source evidence describes feedback, but the graph has no control-flow edge.")
    parallel_cue = re.search(
        r"(?<!不)(?<!未)(?<!没有)(?<!不得)(?<!不可)(?<!不能)(?<!不应)(?<!不允许)(?<!禁止)(?:并行|同时)调用|分发给|共同进入",
        evidence_text,
    )
    if parallel_cue and not any(count >= 2 for count in outgoing.values()) and not any(count >= 2 for count in incoming.values()):
        add("missing_parallel_structure", "error", "Source evidence describes parallel work, but fan-out/fan-in is absent.")
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
