from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TEMPLATE_RECORDS: list[dict[str, Any]] = [
    {
        "id": "drawio_official_architecture", "source_url": "https://www.drawio.com/docs/manual/templates/template-diagrams/",
        "source_type": "drawio_official", "license": "verified", "editable": True,
        "supported_types": ["architecture", "workflow", "graph"], "style_tags": ["academic_clean", "left_to_right"],
        "components": ["module_box", "group_frame", "arrow"], "preview_url": None, "download_url": None, "restrictions": [],
    },
    {
        "id": "mermaid_official_architecture", "source_url": "https://mermaid.js.org/syntax/architecture",
        "source_type": "mermaid_official", "license": "verified", "editable": True,
        "supported_types": ["architecture", "workflow"], "style_tags": ["academic_clean", "text_first"],
        "components": ["service", "group", "edge"], "preview_url": None, "download_url": None, "restrictions": [],
    },
    {
        "id": "scientific_figure_agent_academic_clean", "source_url": "https://github.com/Slaughter-1/scientific-figure-agent",
        "source_type": "project_builtin", "license": "project_owned", "editable": True,
        "supported_types": ["architecture", "workflow", "graph", "plot"], "style_tags": ["academic_clean", "paper"],
        "components": ["module_box", "group_frame", "arrow", "plot_panel"], "preview_url": None, "download_url": None, "restrictions": [],
    },
    {
        "id": "figma_community_flowchart", "source_url": "https://www.figma.com/templates/",
        "source_type": "figma_community", "license": "review_required", "editable": True,
        "supported_types": ["workflow", "architecture"], "style_tags": ["flowchart", "community"],
        "components": ["frame", "text", "connector"], "preview_url": None, "download_url": None,
        "restrictions": ["Verify the individual community file license before publication."],
    },
]


def search_templates(query: str, *, policy: str = "open_license_first", limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty")
    if policy not in {"open_license_first", "broad_search", "local_only"}:
        raise ValueError("unsupported template policy")
    tokens = {token.casefold() for token in query.replace("_", " ").split() if token.strip()}
    matches: list[dict[str, Any]] = []
    for record in TEMPLATE_RECORDS:
        haystack = " ".join([record["id"], record["source_type"], *record["supported_types"], *record["style_tags"], *record["components"]]).casefold()
        if tokens and not any(token in haystack for token in tokens):
            continue
        if policy == "open_license_first" and record["license"] not in {"verified", "project_owned"}:
            continue
        if policy == "local_only" and record["source_type"] != "project_builtin":
            continue
        result = dict(record)
        result["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        result["match_reason"] = "query token matched template metadata"
        matches.append(result)
    return matches[: max(0, limit)]
