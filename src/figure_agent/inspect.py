from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def inspect_artifact(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return {"status": "error", "error": f"artifact does not exist: {path}"}
    fmt = path.suffix.lower().lstrip(".")
    result: dict[str, Any] = {"status": "ok", "format": fmt, "path": str(path), "size": path.stat().st_size}
    try:
        if fmt == "svg":
            root = ET.fromstring(path.read_text(encoding="utf-8"))
            result["text_nodes"] = len(root.findall(".//{*}text"))
            for field in ("width", "height"):
                match = re.match(r"[0-9.]+", root.get(field, ""))
                if match:
                    result[field] = float(match.group())
                if result[field].is_integer():
                    result[field] = int(result[field])
            from .visual_critic import critique_artifact

            result["visual_findings"] = critique_artifact(path)
        elif fmt == "drawio":
            from .backends.drawio_backend import check_drawio_output

            errors = check_drawio_output(path, required_labels=[])
            if errors:
                result.update({"status": "error", "errors": errors})
        elif fmt == "json":
            from .visual_critic import critique_artifact

            result["visual_findings"] = critique_artifact(path)
        elif fmt not in {"pdf", "png"}:
            result["warnings"] = ["format has no specialized inspector"]
    except (OSError, ET.ParseError, UnicodeError) as exc:
        return {"status": "error", "format": fmt, "path": str(path), "error": str(exc)}
    return result
