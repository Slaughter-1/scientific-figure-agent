from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .backends.figma_backend import compile_figma_scene
from .layouts import build_route_plan
from .parity import compare_semantics, extract_figma_semantics
from .spec import require_valid_spec
from .visual_styles import get_visual_style


class FigmaM0Transport(Protocol):
    """Explicit bridge contract; MCP/API schema is supplied by the caller."""

    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]: ...

    def readback(self, identity: str) -> dict[str, Any]: ...

    def export(self, identity: str, formats: list[str], output_dir: str) -> dict[str, Any]: ...


def m0_spec() -> dict[str, Any]:
    return {
        "schema_version": "0.1", "figure_type": "workflow", "title": "Figma M0 Agent Loop",
        "layout": {"direction": "left-to-right", "spacing": 24},
        "nodes": [
            {"id": "query", "label": "用户问题", "type": "data"},
            {"id": "retriever", "label": "检索器", "type": "tool"},
            {"id": "generator", "label": "生成器", "type": "model"},
            {"id": "answer", "label": "答案", "type": "data"},
        ],
        "edges": [
            {"source": "query", "target": "retriever", "type": "data_flow"},
            {"source": "retriever", "target": "generator", "type": "data_flow"},
            {"source": "generator", "target": "answer", "type": "data_flow"},
            {"source": "generator", "target": "retriever", "type": "control_flow", "label": "若证据不足"},
        ],
        "groups": [{"id": "agent-loop", "label": "Agent loop", "children": ["retriever", "generator"]}],
        "style": {"colors": {"data": "#F2F4F7", "tool": "#DDF7EE", "model": "#EDE9FE"}},
    }


def _m0_route_plan(spec: dict[str, Any]) -> dict[str, Any]:
    """Reuse the existing RoutePlan for the M0 bundle; no routing algorithm changes here."""
    style = get_visual_style(spec.get("style", {}).get("variant", "editorial"))
    paper_width_mm = 85.0 if spec.get("constraints", {}).get("paper_width") == "single_column" else 180.0
    return build_route_plan(spec, family=style.get("layout_family", "pipeline"), paper_width_mm=paper_width_mm)


def run_figma_m0(output_dir: str | Path, transport: FigmaM0Transport | None = None) -> dict[str, Any]:
    """Create an auditable local M0 bundle; remote success requires all bridge methods."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    spec = m0_spec()
    require_valid_spec(spec)
    (output / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    route_plan = _m0_route_plan(spec)
    (output / "route-plan.json").write_text(json.dumps(route_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    scene = compile_figma_scene(spec, route_plan=route_plan)
    (output / "local-scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    parity = compare_semantics(spec, extract_figma_semantics(scene))
    (output / "parity.json").write_text(json.dumps({"status": "pass" if not parity else "fail", "findings": parity}, ensure_ascii=False, indent=2), encoding="utf-8")
    schema = {"protocol": "FigmaM0Transport", "methods": ["write_scene(scene)", "readback(file_or_frame)", "export(file_or_frame, ['svg','pdf'], output_dir)"], "remote_status": "unavailable", "edge_kind": "VECTOR", "geometry_source": "route_plan"}
    (output / "transport-schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    result: dict[str, Any] = {"status": "unavailable", "spec": str(output / "spec.json"), "scene": str(output / "local-scene.json"), "parity": str(output / "parity.json"), "route_plan": str(output / "route-plan.json"), "file_or_frame": None}
    if transport is not None:
        try:
            remote = transport.write_scene(scene)
            identity = remote.get("file_or_frame") if isinstance(remote, dict) else None
            if remote.get("status") != "connected" or not identity:
                raise ValueError("write_scene must return status=connected and file_or_frame")
            readback = transport.readback(identity)
            exports = transport.export(identity, ["svg", "pdf"], str(output))
            result.update({"status": "connected", "file_or_frame": identity, "create": remote, "readback": readback, "exports": exports})
            schema["remote_status"] = "connected"
        except Exception as exc:
            result.update({"status": "error", "error": str(exc)})
    (output / "whoami.json").write_text(json.dumps({"status": result["status"], "source": "injected_transport"}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "create-result.json").write_text(json.dumps(result.get("create", result), ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "readback.json").write_text(json.dumps(result.get("readback", {"status": "not_available"}), ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "smoke.log").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "transport-schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
