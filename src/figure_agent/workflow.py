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
    edges = [{"source": edge["source"], "target": edge["target"]} for edge in spec["edges"] if labels_by_id.get(edge["source"]) not in uncertain_labels and labels_by_id.get(edge["target"]) not in uncertain_labels]
    needs_review: list[dict[str, str]] = []
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


def generate_from_text(text: str, output_dir: str | Path, *, count: int = 3, template_policy: str = "open_license_first") -> dict[str, Any]:
    spec = parse_method_text(text)
    contract = build_figure_contract(text)
    templates = search_templates(contract["target_figure_type"], policy=template_policy, limit=count)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figure-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    candidates = generate_candidates(spec, output_dir, count=count, templates=templates)
    return {"contract": contract, "candidates": candidates}
