from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .candidates import generate_candidates
from .parser import parse_method_text
from .planner import classify_figure
from .templates import search_templates


def build_figure_contract(text: str, *, target_figure_type: str | None = None) -> dict[str, Any]:
    spec = parse_method_text(text)
    figure_type = target_figure_type or classify_figure(text)
    labels = [node["label"] for node in spec["nodes"]]
    edges = [{"source": edge["source"], "target": edge["target"]} for edge in spec["edges"]]
    needs_review: list[dict[str, str]] = []
    if len(labels) < 2:
        needs_review.append({"code": "insufficient_stages", "message": "At least two explicit stages are needed for a reliable diagram."})
    return {
        "figure_goal": "method_overview", "target_figure_type": figure_type,
        "required_labels": labels, "required_edges": edges,
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
