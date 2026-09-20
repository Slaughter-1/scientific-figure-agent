from __future__ import annotations

from pathlib import Path
from typing import Any


def render_backends(spec: dict[str, Any], backends: list[str], output_dir: str | Path) -> dict[str, dict[str, Any]]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    for backend in backends:
        try:
            if backend == "drawio":
                from .backends.drawio_backend import render_drawio_spec

                results[backend] = {"status": "ok", **{key: str(value) for key, value in render_drawio_spec(spec, output_dir, "figure").items()}}
            elif backend == "matplotlib":
                if spec.get("figure_type") != "plot":
                    results[backend] = {"status": "skipped", "reason": "matplotlib backend requires figure_type=plot"}
                else:
                    from .backends.plot_backend import render_plot_spec

                    results[backend] = {"status": "ok", **{key: str(value) for key, value in render_plot_spec(spec, output_dir, "figure").items()}}
            elif backend == "figma":
                from .backends.figma_backend import render_figma_spec

                results[backend] = {"status": "ok", **{key: str(value) for key, value in render_figma_spec(spec, output_dir).items()}}
            else:
                results[backend] = {"status": "error", "error": f"unknown backend: {backend}"}
        except Exception as exc:
            results[backend] = {"status": "error", "error": str(exc)}
    return results
