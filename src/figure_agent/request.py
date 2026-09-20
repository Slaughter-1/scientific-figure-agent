from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

INPUT_TYPES = {"paper_text", "figure_caption", "csv", "json", "existing_spec", "user_assets"}
FIGURE_TYPES = {"architecture", "workflow", "graph", "plot"}
TEMPLATE_POLICIES = {"open_license_first", "broad_search", "local_only"}
PAPER_WIDTHS = {"single_column", "double_column", "custom"}


@dataclass
class FigureRequest:
    input_type: str
    content: Any
    figure_goal: str = "method_overview"
    target_figure_type: str | None = None
    audience: str = "paper"
    paper_width: str = "double_column"
    style: str = "academic_clean"
    required_outputs: list[str] = field(default_factory=lambda: ["svg", "pdf", "png", "drawio"])
    template_policy: str = "open_license_first"
    candidate_count: int = 3
    user_assets: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FigureRequest":
        if not isinstance(value, dict):
            raise ValueError("request must be an object")
        input_type = value.get("input_type")
        if input_type not in INPUT_TYPES:
            raise ValueError(f"input_type must be one of: {', '.join(sorted(INPUT_TYPES))}")
        content = value.get("content")
        if content is None or (isinstance(content, str) and not content.strip()):
            raise ValueError("content must be non-empty")
        figure_type = value.get("target_figure_type")
        if figure_type is not None and figure_type not in FIGURE_TYPES:
            raise ValueError("target_figure_type is unsupported")
        paper_width = value.get("paper_width", "double_column")
        if paper_width not in PAPER_WIDTHS:
            raise ValueError("paper_width is unsupported")
        policy = value.get("template_policy", "open_license_first")
        if policy not in TEMPLATE_POLICIES:
            raise ValueError("template_policy is unsupported")
        candidate_count = value.get("candidate_count", 3)
        if not isinstance(candidate_count, int) or not 1 <= candidate_count <= 3:
            raise ValueError("candidate_count must be an integer between 1 and 3")
        return cls(
            input_type=input_type, content=content, figure_goal=value.get("figure_goal", "method_overview"),
            target_figure_type=figure_type, audience=value.get("audience", "paper"), paper_width=paper_width,
            style=value.get("style", "academic_clean"), required_outputs=list(value.get("required_outputs", ["svg", "pdf", "png", "drawio"])),
            template_policy=policy, candidate_count=candidate_count, user_assets=list(value.get("user_assets", [])),
            constraints=dict(value.get("constraints", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
