from __future__ import annotations

import importlib.util
import shutil
import sys


def _matplotlib_info() -> dict[str, object]:
    if importlib.util.find_spec("matplotlib") is None:
        return {"installed": False, "version": None}
    import matplotlib

    return {"installed": True, "version": matplotlib.__version__}


def build_environment_report() -> dict[str, object]:
    drawio = shutil.which("drawio") or shutil.which("drawio.exe")
    return {
        "python": {"version": sys.version.split()[0], "ok": sys.version_info >= (3, 10)},
        "matplotlib": _matplotlib_info(),
        "drawio": {"executable": drawio, "plugin_fallback": True},
        "figma_mcp": {"status": "manual_smoke_required"},
    }
