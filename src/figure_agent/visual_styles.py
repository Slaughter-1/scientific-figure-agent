from __future__ import annotations

from copy import deepcopy
from typing import Any


_FONT_FALLBACKS = {
    "zh": ("Noto Sans SC", ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"]),
    "en": ("Arial", ["Inter", "DejaVu Sans"]),
    "auto": ("Noto Sans SC", ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"]),
}


_STYLES: dict[str, dict[str, Any]] = {
    "editorial": {
        "layout_family": "pipeline",
        "surface": {"background": "#FFFFFF", "canvas_padding": 28},
        "node": {"width": 180, "height": 72, "radius": 14, "shadow": "subtle"},
        "edge": {"routing": "orthogonal", "width": 1.6, "arrow": "filled"},
        "colors": {"process": "#E8F1FF", "data": "#F8FAFC", "tool": "#DDF7EE", "model": "#EDE9FE", "storage": "#FFF4D6", "decision": "#FFE4E6"},
    },
    "swimlane": {
        "layout_family": "swimlane",
        "surface": {"background": "#F8FAFC", "canvas_padding": 34},
        "node": {"width": 210, "height": 76, "radius": 10, "shadow": "none"},
        "edge": {"routing": "orthogonal", "width": 1.4, "arrow": "open"},
        "colors": {"process": "#DBEAFE", "data": "#EFF6FF", "tool": "#E0E7FF", "model": "#DDD6FE", "storage": "#CFFAFE", "decision": "#FEF3C7"},
    },
    "blueprint": {
        "layout_family": "swimlane",
        "surface": {"background": "#F8FAFC", "canvas_padding": 36},
        "node": {"width": 200, "height": 72, "radius": 8, "shadow": "none"},
        "edge": {"routing": "orthogonal", "width": 1.5, "arrow": "open"},
        "colors": {"process": "#DBEAFE", "data": "#EFF6FF", "tool": "#E0E7FF", "model": "#DDD6FE", "storage": "#CFFAFE", "decision": "#FEF3C7"},
    },
    "loop": {
        "layout_family": "loop",
        "surface": {"background": "#FFFFFF", "canvas_padding": 40},
        "node": {"width": 190, "height": 76, "radius": 20, "shadow": "soft"},
        "edge": {"routing": "curved_feedback", "width": 1.8, "arrow": "filled"},
        "colors": {"process": "#F1F5F9", "data": "#E0F2FE", "tool": "#CCFBF1", "model": "#F3E8FF", "storage": "#FEF3C7", "decision": "#FFE4E6"},
    },
    "hierarchy": {
        "layout_family": "hierarchy",
        "surface": {"background": "#FFFFFF", "canvas_padding": 32},
        "node": {"width": 195, "height": 78, "radius": 16, "shadow": "subtle"},
        "edge": {"routing": "elbow", "width": 1.5, "arrow": "filled"},
        "colors": {"process": "#F1F5F9", "data": "#E0F2FE", "tool": "#CCFBF1", "model": "#F3E8FF", "storage": "#FEF3C7", "decision": "#FFE4E6"},
    },
}


def resolve_font_family(language: str) -> tuple[str, list[str]]:
    """Return an editable primary font and deterministic fallbacks."""
    return _FONT_FALLBACKS.get(language.lower(), _FONT_FALLBACKS["auto"])


def get_visual_style(variant: str, *, language: str = "auto", paper_width: str = "double_column") -> dict[str, Any]:
    """Return a serializable style token set for one candidate family."""
    if variant not in _STYLES:
        raise ValueError(f"unsupported visual style: {variant}")
    primary, fallbacks = resolve_font_family(language)
    style = deepcopy(_STYLES[variant])
    scale = {"single_column": 0.88, "double_column": 1.0, "custom": 1.0}.get(paper_width, 1.0)
    style["font"] = {"family": primary, "fallbacks": fallbacks, "title_size": round(14 * scale, 1), "node_size": round(9.5 * scale, 1), "annotation_size": round(8 * scale, 1)}
    style["variant"] = variant
    style["theme"] = "academic_clean"
    return style


def available_layout_families(figure_type: str, has_cycle: bool, has_branch: bool) -> list[str]:
    """Order candidate families by the structure present in the Figure Spec."""
    if figure_type == "plot":
        return ["editorial", "swimlane", "hierarchy"]
    if has_cycle:
        return ["editorial", "swimlane", "loop"]
    if has_branch:
        return ["editorial", "hierarchy", "swimlane"]
    return ["editorial", "swimlane", "hierarchy"]
