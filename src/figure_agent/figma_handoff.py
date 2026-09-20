from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import spec_sha256
from .backends.figma_backend import compile_figma_scene
from .spec import load_spec, require_valid_spec


def build_figma_handoff(
    spec_path: str | Path,
    output_dir: str | Path,
    *,
    connection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a candidate into a local Figma scene and auditable handoff manifest."""
    spec_path = Path(spec_path)
    output_dir = Path(output_dir)
    spec = load_spec(spec_path)
    require_valid_spec(spec)
    scene = compile_figma_scene(spec)
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_path = output_dir / "figure.figma-scene.json"
    scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

    result: dict[str, Any] = {
        "status": "unavailable",
        "scene": str(scene_path),
        "spec": str(spec_path),
        "spec_sha256": spec_sha256(spec),
        "native_node_kinds": sorted({str(node.get("kind")) for node in scene["nodes"]}),
        "node_count": len(scene["nodes"]),
        "file_or_frame": None,
    }
    if connection is not None:
        if connection.get("status") != "connected":
            raise ValueError("Figma connection status must be connected")
        if not connection.get("file_or_frame"):
            raise ValueError("connected Figma handoff must include file_or_frame")
        result.update(connection)
    (output_dir / "figma-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
