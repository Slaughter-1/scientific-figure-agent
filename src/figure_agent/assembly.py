from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .components import attach_assets_to_spec, register_asset


def assemble_spec_with_assets(spec_path: str | Path, assets_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    spec_path, assets_dir, output_path = Path(spec_path), Path(assets_dir), Path(output_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in spec.get("nodes", [])}
    assets: dict[str, dict[str, Any]] = {}
    for path in sorted(assets_dir.iterdir()):
        if path.is_file() and path.suffix.lower().lstrip(".") in {"svg", "png", "pdf", "drawio", "json"} and path.stem in nodes:
            assets[path.stem] = register_asset(path, source="user_upload")
    result = attach_assets_to_spec(spec, assets)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
