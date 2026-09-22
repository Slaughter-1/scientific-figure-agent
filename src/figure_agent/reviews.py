"""Issue identity and auditable, single-issue resolution helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


def identify_issues(spec: dict[str, Any], revision_id: str) -> None:
    for issue in spec.get("needs_review", []):
        issue.setdefault("issue_id", str(uuid.uuid4()))
        issue.setdefault("issue_revision", revision_id)


def resolve_issue(spec: dict[str, Any], issue: dict[str, Any], *, resolution: str, reason: str, evidence: list, revision_id: str) -> None:
    spec.setdefault("review_notes", []).append({
        "issue_id": issue["issue_id"], "issue_revision": issue["issue_revision"],
        "issue": dict(issue), "resolution": resolution, "reason": reason,
        "evidence_refs": evidence, "resolved_at": datetime.now(timezone.utc).isoformat(),
        "result_revision": revision_id,
    })
    spec["needs_review"] = [item for item in spec.get("needs_review", []) if item["issue_id"] != issue["issue_id"]]
