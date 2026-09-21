from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .critic import critique_spec
from .layouts import layout_edges, layout_nodes
from .spec import require_valid_spec
from .visual_styles import available_layout_families, get_visual_style


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


def _has_cycle(spec: dict[str, Any]) -> bool:
    indexes = {node["id"]: index for index, node in enumerate(spec.get("nodes", []))}
    graph = {node_id: [] for node_id in indexes}
    for edge in spec.get("edges", []):
        source, target = edge.get("source"), edge.get("target")
        if source in graph:
            graph[source].append(target)
        if target in indexes and source in indexes and indexes[target] <= indexes[source]:
            return True
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        if any(visit(child) for child in graph[node_id] if child in graph):
            return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in graph)


def _has_branch(spec: dict[str, Any]) -> bool:
    outgoing: dict[str, int] = {}
    for edge in spec.get("edges", []):
        outgoing[edge["source"]] = outgoing.get(edge["source"], 0) + 1
    return any(count > 1 for count in outgoing.values())


def _visual_groups(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Add presentation-only swimlanes without inventing semantic nodes."""
    buckets = {"Data & Evidence": [], "Agent Core": []}
    for node in spec.get("nodes", []):
        bucket = "Data & Evidence" if node.get("type") in {"data", "storage"} else "Agent Core"
        buckets[bucket].append(node["id"])
    return [{"id": f"visual-group-{index}", "label": label, "children": children} for index, (label, children) in enumerate(buckets.items(), 1) if len(children) >= 2]


def _design_description(family: str, has_cycle: bool, has_branch: bool) -> dict[str, Any]:
    descriptions = {
        "pipeline": {"family": "editorial", "rationale": "以主流程为视觉主轴，适合方法步骤和单栏阅读。", "best_for": ["线性方法", "单栏论文"], "tradeoffs": ["分支较多时需要更多横向空间"]},
        "swimlane": {"family": "swimlane", "rationale": "用阶段分区组织输入、处理和输出，适合双栏论文和模块较多的方法图。", "best_for": ["阶段化流程", "双栏论文"], "tradeoffs": ["节点较少时会显得留白偏多"]},
        "loop": {"family": "loop", "rationale": "用环形布局突出反馈和迭代关系，避免把 Agent loop 压成直线。", "best_for": ["RAG 迭代", "Agent planning loop"], "tradeoffs": ["需要较大的画布", "阅读顺序依赖箭头"]},
        "hierarchy": {"family": "hierarchy", "rationale": "用层级排列强调主模块、工具和数据之间的视觉分组。", "best_for": ["多模块架构", "分支流程"], "tradeoffs": ["线性流程不需要反馈回路"]},
    }
    design = dict(descriptions[family])
    if not has_cycle and family == "hierarchy":
        design["tradeoffs"] = ["线性流程不需要反馈回路", "层级关系来自现有节点顺序，不代表新增语义"]
    if has_branch and family == "pipeline":
        design["tradeoffs"].append("分支会以共享主轴显示")
    return design


def generate_candidates(spec: dict[str, Any], output_dir: str | Path, *, count: int = 3, templates: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if not 1 <= count <= 3:
        raise ValueError("count must be between 1 and 3")
    require_valid_spec(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    has_cycle, has_branch = _has_cycle(spec), _has_branch(spec)
    families = available_layout_families(spec.get("figure_type", "workflow"), has_cycle, has_branch)
    results: list[dict[str, Any]] = []
    for index in range(count):
        candidate_id = f"candidate_{index + 1:02d}"
        candidate_spec = deepcopy(spec)
        candidate_spec["candidate_id"] = candidate_id
        family = families[index % len(families)]
        style = get_visual_style(family, paper_width=candidate_spec.get("constraints", {}).get("paper_width", "double_column"))
        candidate_spec["layout"] = {**candidate_spec.get("layout", {}), "direction": "top-to-bottom" if family == "swimlane" else "left-to-right", "spacing": 30 if family == "swimlane" else 36}
        candidate_spec["style"] = {**candidate_spec.get("style", {}), **style, "font_family": style["font"]["family"], "font_sizes": {"title": style["font"]["title_size"], "node": style["font"]["node_size"]}, "stroke": "#355070", "arrow_color": "#56718C", "group_fill": style["surface"]["background"], "colors": style["colors"]}
        if family in {"hierarchy", "swimlane"} and not candidate_spec.get("groups"):
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
        positions = layout_nodes(candidate_spec, family=style["layout_family"])
        routes = layout_edges(candidate_spec, positions, family=style["layout_family"])
        design = _design_description(style["layout_family"], has_cycle, has_branch)
        design["family"] = family
        score = _score(candidate_spec, template)
        score.update({"layout_distinctiveness": round(0.82 if family != "pipeline" and (has_cycle or has_branch) else 0.72, 3), "visual_readability": 1.0 if len(candidate_spec.get("nodes", [])) <= 9 else 0.75, "semantic_preservation": 1.0})
        result = {
            "candidate_id": candidate_id, "template_ref": template.get("id") if template else None,
            "spec": candidate_spec, "spec_path": str(candidate_dir / "figure-spec.json"), "artifacts": artifacts,
            "design": design, "preview_fingerprint": {"node_positions": {key: list(value) for key, value in positions.items()}, "edge_routes": [[list(point) for point in route] for route in routes], "style_variant": family},
            "scores": score, "review_findings": critique_spec(candidate_spec),
        }
        (candidate_dir / "figure-spec.json").write_text(json.dumps(candidate_spec, ensure_ascii=False, indent=2), encoding="utf-8")
        (candidate_dir / "candidate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(result)
    (output_dir / "candidates.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
