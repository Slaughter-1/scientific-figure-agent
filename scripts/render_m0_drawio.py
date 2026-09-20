from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from figure_agent.backends.drawio_backend import build_drawio_xml
from figure_agent.spec import load_spec, require_valid_spec


def render_preview(spec: dict, output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    positions = {node["id"]: (0.7 + (index % 5) * 1.9, 3.5 - (index // 5) * 1.7) for index, node in enumerate(spec["nodes"])}
    for node in spec["nodes"]:
        x, y = positions[node["id"]]
        patch = FancyBboxPatch((x, y), 1.45, 0.55, boxstyle="round,pad=0.03,rounding_size=0.08", facecolor="#E8EEF7", edgecolor="#64748B", linewidth=1.0)
        ax.add_patch(patch)
        ax.text(x + 0.725, y + 0.275, node["label"], ha="center", va="center", fontsize=8)
    for edge in spec["edges"]:
        sx, sy = positions[edge["source"]]
        tx, ty = positions[edge["target"]]
        ax.annotate("", xy=(tx, ty + 0.275), xytext=(sx + 1.45, sy + 0.275), arrowprops={"arrowstyle": "->", "color": "#475569", "linewidth": 0.8})
    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "workflow.svg", bbox_inches="tight")
    fig.savefig(output_dir / "workflow.pdf", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    spec = load_spec(ROOT / "examples/m0/workflow.json")
    require_valid_spec(spec)
    output_dir = ROOT / "outputs/m0"
    (output_dir / "workflow.drawio").write_text(build_drawio_xml(spec), encoding="utf-8")
    render_preview(spec, output_dir)
    print(f"drawio: {output_dir / 'workflow.drawio'}")
    print(f"svg: {output_dir / 'workflow.svg'}")
    print(f"pdf: {output_dir / 'workflow.pdf'}")
