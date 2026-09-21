from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Noto Sans SC", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42


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
        series = data.get("series") or [{"name": "series", "y": y, "y_error": data.get("y_error")}]
        width = 0.8 / len(series)
        positions = list(range(len(x)))
        for index, item in enumerate(series):
            offsets = [position + (index - (len(series) - 1) / 2) * width for position in positions]
            ax.bar(offsets, item["y"], width=width, yerr=item.get("y_error"), capsize=3 if item.get("y_error") else 0, label=item.get("name"), color=("#2563EB" if index == 0 else "#94A3B8"))
        ax.set_xticks(positions, x)
        if len(series) > 1:
            ax.legend(frameon=False)
    elif kind == "line":
        x, y = data["x"], data["y"]
        if len(x) != len(y):
            raise ValueError("plot data x and y must have equal lengths")
        series = data.get("series") or [{"name": "series", "y": y, "y_error": data.get("y_error")}]
        for index, item in enumerate(series):
            ax.errorbar(x, item["y"], yerr=item.get("y_error"), capsize=3 if item.get("y_error") else 0, marker="o", color=("#2563EB" if index == 0 else "#94A3B8"), linewidth=1.6, label=item.get("name"))
        if len(series) > 1:
            ax.legend(frameon=False)
    elif kind == "scatter":
        x, y = data["x"], data["y"]
        if len(x) != len(y):
            raise ValueError("plot data x and y must have equal lengths")
        series = data.get("series") or [{"name": "series", "y": y, "y_error": data.get("y_error")}]
        for index, item in enumerate(series):
            ax.errorbar(x, item["y"], yerr=item.get("y_error"), fmt="o", capsize=3 if item.get("y_error") else 0, color=("#2563EB" if index == 0 else "#94A3B8"), label=item.get("name"))
        if len(series) > 1:
            ax.legend(frameon=False)
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
    significance = data.get("significance")
    if significance and kind in {"bar", "line", "scatter"}:
        values = data.get("y", [])
        for x_value, y_value, marker in zip(data.get("x", []), values, significance):
            if marker:
                ax.annotate(marker, (x_value, y_value), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)
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
