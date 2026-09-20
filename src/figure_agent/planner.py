from __future__ import annotations

from typing import Any


def classify_figure(input_data: str | dict[str, Any]) -> str:
    """Classify common research-figure inputs without inventing semantic content."""
    if isinstance(input_data, dict):
        figure_type = input_data.get("figure_type")
        if figure_type in {"architecture", "workflow", "graph", "plot"}:
            return figure_type
        if isinstance(input_data.get("data"), dict) and input_data["data"].get("kind"):
            return "plot"
        raise ValueError("input dict must contain a supported figure_type")
    if not isinstance(input_data, str) or not input_data.strip():
        raise ValueError("input must be a non-empty string or spec dict")
    text = input_data.casefold()
    if any(token in text for token in ("架构", "系统架构", "模块连接", "architecture")):
        return "architecture"
    if any(token in text for token in ("依赖关系", "dependency graph", "graph")):
        return "graph"
    if any(token in text for token in ("实验结果", "柱状图", "折线图", "散点图", "热力图", "benchmark", "accuracy")):
        return "plot"
    return "workflow"
