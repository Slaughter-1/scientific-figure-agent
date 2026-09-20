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


def render_plot_spec(spec: dict[str, Any], output_dir: str | Path, stem: str = "plot") -> dict[str, Path]:
    """Render a plot Figure Spec using a small deterministic Matplotlib backend."""
    from figure_agent.spec import require_valid_spec

    require_valid_spec(spec)
    data = spec["data"]
    kind = data["kind"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3.6, 2.6), constrained_layout=True)
    if kind == "bar":
        x, y = data["x"], data["y"]
        if len(x) != len(y):
            raise ValueError("plot data x and y must have equal lengths")
        ax.bar(x, y, color="#2563EB")
    elif kind == "line":
        x, y = data["x"], data["y"]
        if len(x) != len(y):
            raise ValueError("plot data x and y must have equal lengths")
        ax.plot(x, y, marker="o", color="#2563EB", linewidth=1.6)
    elif kind == "scatter":
        x, y = data["x"], data["y"]
        if len(x) != len(y):
            raise ValueError("plot data x and y must have equal lengths")
        ax.scatter(x, y, color="#2563EB", s=28)
    elif kind == "heatmap":
        matrix = data["matrix"]
        if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
            raise ValueError("heatmap matrix must be rectangular and non-empty")
        image = ax.imshow(matrix, cmap="Blues", aspect="auto")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    else:
        raise ValueError(f"unsupported plot kind: {kind}")
    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    if spec.get("title"):
        ax.set_title(spec["title"])
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
