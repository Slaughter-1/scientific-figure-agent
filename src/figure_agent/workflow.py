from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .candidates import generate_candidates
from .parser import parse_method_text
from .planner import classify_figure
from .templates import search_templates


_UNCERTAIN_MARKERS = ("可能", "可选", "未来工作", "有望", "potential", "optional", "might", "could")


def _uncertain_label(label: str) -> str:
    return re.sub(r"^(?:可能|可选|potentially|optional)\s*(?:使用|包含|采用)?", "", label, flags=re.IGNORECASE).strip() or label


def extract_evidence(text: str, entity: str) -> list[dict[str, Any]]:
    """Return source quotes and stable paragraph locations for an entity."""
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    if not paragraphs:
        paragraphs = [part.strip() for part in text.replace("。", "。\n").splitlines() if part.strip()]
    return [{"source": "input_text", "quote": paragraph, "location": f"paragraph_{index}"} for index, paragraph in enumerate(paragraphs, 1) if entity in paragraph]


def build_figure_contract(text: str, *, target_figure_type: str | None = None) -> dict[str, Any]:
    spec = parse_method_text(text)
    figure_type = target_figure_type or classify_figure(text)
    labels = [node["label"] for node in spec["nodes"]]
    uncertain = [node for node in spec["nodes"] if any(marker in node.get("label", "").lower() or marker in node.get("evidence", [{}])[0].get("quote", "").lower() for marker in _UNCERTAIN_MARKERS)]
    uncertain_labels = {node["label"] for node in uncertain}
    optional_labels = [_uncertain_label(node["label"]) for node in uncertain]
    required_labels = [label for label in labels if label not in uncertain_labels]
    labels_by_id = {node["id"]: node["label"] for node in spec["nodes"]}
    edges = [{key: edge[key] for key in ("source", "target", "type", "label") if key in edge} for edge in spec["edges"] if labels_by_id.get(edge["source"]) not in uncertain_labels and labels_by_id.get(edge["target"]) not in uncertain_labels]
    needs_review: list[dict[str, str]] = list(spec.get("needs_review", []))
    if len(labels) < 2:
        needs_review.append({"code": "insufficient_stages", "message": "At least two explicit stages are needed for a reliable diagram."})
    for node in uncertain:
        needs_review.append({"code": "uncertain_entity", "target": node["label"], "message": f"Entity '{node['label']}' is uncertain and needs user review."})
    return {
        "figure_goal": "method_overview", "target_figure_type": figure_type,
        "required_labels": required_labels, "optional_nodes": optional_labels, "required_edges": edges,
        "evidence_gaps": [{"target": node["label"], "evidence": node.get("evidence", [])} for node in uncertain],
        "evidence_coverage": round(sum(bool(node.get("evidence")) for node in spec["nodes"]) / max(len(labels), 1), 3),
        "needs_review": needs_review,
    }


def contract_findings(spec: dict[str, Any], contract: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Check required semantics without inventing missing scientific content."""
    contract = contract if contract is not None else spec.get("metadata", {}).get("figure_contract", {})
    labels = {node.get("label") for node in spec.get("nodes", [])}
    findings = [{"code": "contract_required_node_missing", "severity": "error", "target": label, "message": f"Contract requires node: {label}"} for label in contract.get("required_labels", []) if label not in labels]
    for required in contract.get("required_edges", []):
        target = f"{required.get('source')}->{required.get('target')}"
        matches = [edge for edge in spec.get("edges", []) if all(edge.get(key, "") == required[key] for key in ("source", "target", "type", "label") if key in required)]
        if not matches:
            findings.append({"code": "contract_required_edge_missing", "severity": "error", "target": target, "message": f"Contract edge, direction, type or condition not satisfied: {required}"})
    return findings


def compile_spec_with_contract(spec: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Compile only contract-approved semantic nodes into a candidate draft.

    Uncertain entities remain visible in ``needs_review`` metadata, but are not
    silently promoted to confirmed scientific modules.
    """
    optional = set(contract.get("optional_nodes", []))
    nodes = [node for node in spec.get("nodes", []) if node.get("label") not in optional and _uncertain_label(str(node.get("label", ""))) not in optional]
    ids = {node["id"] for node in nodes}
    compiled = dict(spec)
    compiled["nodes"] = nodes
    compiled["edges"] = [edge for edge in spec.get("edges", []) if edge.get("source") in ids and edge.get("target") in ids]
    compiled["figure_type"] = contract.get("target_figure_type") or compiled.get("figure_type", "workflow")
    compiled["needs_review"] = [*spec.get("needs_review", []), *contract.get("needs_review", [])]
    compiled["metadata"] = {**spec.get("metadata", {}), "figure_contract": contract}
    compiled["groups"] = [{**group, "children": [node_id for node_id in group.get("children", []) if node_id in ids]} for group in spec.get("groups", [])]
    compiled["groups"] = [group for group in compiled["groups"] if group["children"]]
    compiled["needs_review"].extend(contract_findings(compiled, contract))
    return compiled


def generate_from_text(text: str, output_dir: str | Path, *, count: int = 3, template_policy: str = "open_license_first", target_figure_type: str | None = None, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = parse_method_text(text)
    contract = contract or build_figure_contract(text, target_figure_type=target_figure_type)
    spec = compile_spec_with_contract(spec, contract)
    templates = search_templates(contract["target_figure_type"], policy=template_policy, limit=count)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figure-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates = generate_candidates(spec, output_dir, count=count, templates=templates)
    return {"contract": contract, "candidates": candidates}
