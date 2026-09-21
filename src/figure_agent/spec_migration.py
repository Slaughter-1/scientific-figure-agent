from __future__ import annotations

from copy import deepcopy
from typing import Any

from .spec import require_valid_spec


def migrate_spec(spec: dict[str, Any], *, request_id: str | None = None, task_id: str | None = None, candidate_id: str | None = None) -> dict[str, Any]:
    """Return a backward-compatible Figure Spec 0.3 copy."""
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    migrated = deepcopy(spec)
    migrated["schema_version"] = "0.3"
    migrated.setdefault("provenance", {})
    migrated.setdefault("evidence", [])
    migrated.setdefault("constraints", {})
    migrated.setdefault("template_refs", [])
    migrated.setdefault("asset_refs", [])
    migrated.setdefault("panel", [])
    migrated.setdefault("review_notes", [])
    migrated.setdefault("needs_review", [])
    migrated.setdefault("semantic_confidence", 1.0 if all(node.get("evidence") for node in migrated.get("nodes", [])) else 0.0)
    if request_id is not None:
        migrated["request_id"] = request_id
    if task_id is not None:
        migrated["task_id"] = task_id
    if candidate_id is not None:
        migrated["candidate_id"] = candidate_id
    for node in migrated.get("nodes", []):
        node.setdefault("evidence", [])
        node.setdefault("locked", False)
        node.setdefault("confidence", 1.0 if node.get("evidence") else 0.0)
    require_valid_spec(migrated)
    return migrated
