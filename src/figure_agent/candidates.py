from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .critic import critique_spec
from .spec import require_valid_spec


def _score(spec: dict[str, Any], template: dict[str, Any] | None) -> dict[str, float]:
    nodes = spec.get("nodes", [])
    evidence = sum(1 for node in nodes if node.get("evidence")) if nodes else 1
    findings = critique_spec(spec)
    errors = sum(1 for finding in findings if finding["severity"] == "error")
    return {
        "evidence_coverage": round(evidence / max(len(nodes), 1), 3),
        "structural_validity": 1.0 if errors == 0 else 0.0,
        "readability": 1.0 if len(nodes) <= 9 else 0.75,
        "style_consistency": 1.0 if spec.get("style", {}).get("theme", "academic_clean") == "academic_clean" else 0.8,
        "license_safety": 1.0 if not template or template.get("license") in {"verified", "project_owned"} else 0.0,
    }


def _visual_groups(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Add presentation-only swimlanes without inventing semantic nodes."""
    buckets = {"Data & Evidence": [], "Agent Core": []}
    for node in spec.get("nodes", []):
        bucket = "Data & Evidence" if node.get("type") in {"data", "storage"} else "Agent Core"
        buckets[bucket].append(node["id"])
    return [{"id": f"visual-group-{index}", "label": label, "children": children} for index, (label, children) in enumerate(buckets.items(), 1) if len(children) >= 2]


def generate_candidates(spec: dict[str, Any], output_dir: str | Path, *, count: int = 3, templates: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if not 1 <= count <= 3:
        raise ValueError("count must be between 1 and 3")
    require_valid_spec(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    variants = [
        {
            "direction": "left-to-right", "spacing": 24,
            "style": {"theme": "academic_clean", "variant": "editorial", "stroke": "#355070", "arrow_color": "#56718C", "group_fill": "#F8FAFC", "font_family": "Noto Sans SC", "font_sizes": {"title": 13, "node": 9}, "node_width": 180, "node_height": 72,
                "colors": {"process": "#E8F1FF", "data": "#F8FAFC", "tool": "#DDF7EE", "model": "#EDE9FE", "storage": "#FFF4D6", "decision": "#FFE4E6"}},
        },
        {
            "direction": "top-to-bottom", "spacing": 30,
            "style": {"theme": "academic_clean", "variant": "blueprint", "stroke": "#1D4ED8", "arrow_color": "#2563EB", "group_fill": "#EFF6FF", "font_family": "Noto Sans SC", "font_sizes": {"title": 13, "node": 9}, "node_width": 190, "node_height": 72,
                "colors": {"process": "#DBEAFE", "data": "#EFF6FF", "tool": "#E0E7FF", "model": "#DDD6FE", "storage": "#CFFAFE", "decision": "#FEF3C7"}},
        },
        {
            "direction": "left-to-right", "spacing": 42,
            "style": {"theme": "academic_clean", "variant": "hierarchy", "stroke": "#475569", "arrow_color": "#334155", "group_fill": "#F1F5F9", "font_family": "Noto Sans SC", "font_sizes": {"title": 14, "node": 9}, "node_width": 190, "node_height": 76,
                "colors": {"process": "#F1F5F9", "data": "#E0F2FE", "tool": "#CCFBF1", "model": "#F3E8FF", "storage": "#FEF3C7", "decision": "#FFE4E6"}},
        },
    ]
    results: list[dict[str, Any]] = []
    for index in range(count):
        candidate_id = f"candidate_{index + 1:02d}"
        candidate_spec = deepcopy(spec)
        candidate_spec["candidate_id"] = candidate_id
        variant = variants[index]
        candidate_spec["layout"] = {**candidate_spec.get("layout", {}), "direction": variant["direction"], "spacing": variant["spacing"]}
        candidate_spec["style"] = {**candidate_spec.get("style", {}), **variant["style"]}
        if variant["style"].get("variant") == "hierarchy" and not candidate_spec.get("groups"):
            candidate_spec["groups"] = _visual_groups(candidate_spec)
        if templates and index < len(templates):
            candidate_spec["template_refs"] = [templates[index]]
        require_valid_spec(candidate_spec)
        candidate_dir = output_dir / candidate_id
        if candidate_spec.get("figure_type") == "plot":
            from .backends.plot_backend import render_plot_spec

            rendered = render_plot_spec(candidate_spec, candidate_dir, "figure")
        else:
            from .backends.drawio_backend import render_drawio_spec

            rendered = render_drawio_spec(candidate_spec, candidate_dir, "figure")
        artifacts = {key: str(value) for key, value in rendered.items()}
        template = templates[index] if templates and index < len(templates) else None
        result = {
            "candidate_id": candidate_id, "template_ref": template.get("id") if template else None,
            "spec": candidate_spec, "spec_path": str(candidate_dir / "figure-spec.json"), "artifacts": artifacts,
            "scores": _score(candidate_spec, template), "review_findings": critique_spec(candidate_spec),
        }
        (candidate_dir / "figure-spec.json").write_text(json.dumps(candidate_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        (candidate_dir / "candidate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(result)
    (output_dir / "candidates.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
