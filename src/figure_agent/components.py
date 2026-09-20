from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


_ELEMENTS = {
    "tool": ["database", "search_arrow", "document_stack"],
    "model": ["model_block", "input_arrow", "output_arrow"],
    "data": ["document_stack", "data_arrow"],
    "storage": ["database", "read_write_arrow"],
    "process": ["process_box", "input_arrow", "output_arrow"],
    "decision": ["decision_node", "branch_arrows"],
}


def _prompt(node: dict[str, Any], color: str) -> str:
    role = node.get("type", "process")
    elements = ", ".join(_ELEMENTS.get(role, ["clean module shape"]))
    return (
        "Create one editable academic vector component for an LLM/NLP/Agent paper.\n"
        f"Component role: {role}.\nRequired visual elements: {elements}.\n"
        "Canvas: 320 × 180 px.\n"
        f"Text: {node.get('label', '')}. Background accent: {color}.\n"
        "Style: white background, thin gray stroke, restrained blue accent, Arial-like sans-serif labels, no 3D, no gradients, no decorative text.\n"
        "Output: transparent SVG or editable Figma/Draw.io component.\n"
        "Do not add any module or label that is not listed."
    )


def build_component_package(spec: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    colors = spec.get("style", {}).get("colors", {})
    components = []
    prompts: list[str] = ["# Component Prompts", ""]
    for node in spec.get("nodes", []):
        color = colors.get(node.get("type"), "#E8EEF7")
        prompt = _prompt(node, color)
        components.append({
            "component_id": node["id"], "role": node.get("type", "process"), "text": [node.get("label", "")],
            "required_elements": _ELEMENTS.get(node.get("type"), ["clean module shape"]),
            "layout": {"width": 320, "height": 180, "padding": 24},
            "style": {"background": color, "stroke": "#64748B", "font": "Arial"},
            "prompt": prompt,
            "asset_refs": [],
        })
        prompts.extend([f"## {node['id']}: {node.get('label', '')}", "", "```text", prompt, "```", ""])
    manifest = {"schema_version": "0.1", "components": components, "asset_refs": []}
    manifest_path = output_dir / "component-manifest.json"
    prompts_path = output_dir / "component-prompts.md"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    prompts_path.write_text("\n".join(prompts), encoding="utf-8")
    return {"manifest": str(manifest_path), "prompts": str(prompts_path)}


def register_asset(path: str | Path, *, source: str = "user_upload", license_status: str = "unknown") -> dict[str, Any]:
    path = Path(path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"asset does not exist: {path}")
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in {"svg", "png", "pdf", "drawio", "json"}:
        raise ValueError(f"unsupported asset format: {fmt or 'unknown'}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    width = height = None
    if fmt == "svg":
        text = path.read_text(encoding="utf-8", errors="replace")
        width_match = re.search(r'\bwidth=["\']([0-9.]+)', text)
        height_match = re.search(r'\bheight=["\']([0-9.]+)', text)
        width = float(width_match.group(1)) if width_match else None
        height = float(height_match.group(1)) if height_match else None
    return {
        "asset_id": digest[:16], "path": str(path), "format": fmt, "sha256": digest,
        "source": source, "license": license_status, "editable": fmt in {"svg", "drawio", "json"},
        "width": int(width) if width is not None and width.is_integer() else width,
        "height": int(height) if height is not None and height.is_integer() else height,
    }


def attach_assets_to_spec(spec: dict[str, Any], assets_by_component: dict[str, dict[str, Any]]) -> dict[str, Any]:
    attached = deepcopy(spec)
    attached.setdefault("asset_refs", [])
    for node in attached.get("nodes", []):
        asset = assets_by_component.get(node.get("id"))
        if not asset:
            continue
        node.setdefault("asset_refs", []).append(asset["asset_id"])
        if asset["asset_id"] not in {item.get("asset_id") for item in attached["asset_refs"] if isinstance(item, dict)}:
            attached["asset_refs"].append(asset)
    return attached
