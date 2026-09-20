from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_bar_chart(data: dict[str, Any], output_dir: Path, stem: str) -> dict[str, Path]:
    methods = data["methods"]
    accuracy = data["accuracy"]
    if len(methods) != len(accuracy):
        raise ValueError("methods and accuracy must have equal lengths")
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3.35, 2.35), constrained_layout=True)
    ax.bar(methods, accuracy, color=["#94A3B8", "#2563EB"][: len(methods)])
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0, 1)
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig_path = output_dir / stem
    fig.savefig(fig_path.with_suffix(".pdf"))
    fig.savefig(fig_path.with_suffix(".svg"))
    fig.savefig(fig_path.with_suffix(".png"), dpi=300)
    plt.close(fig)
    return {suffix: fig_path.with_suffix(f".{suffix}") for suffix in ("pdf", "svg", "png")}
