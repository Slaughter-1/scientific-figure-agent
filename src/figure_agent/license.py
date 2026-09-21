from __future__ import annotations

from typing import Any


def check_export_license(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Return blocking findings for resources that are not publication-ready."""
    findings: list[dict[str, str]] = []
    for collection, kind in ((manifest.get("template_refs", []), "template"), (manifest.get("asset_refs", []), "asset")):
        for item in collection:
            status = item.get("approval_status", item.get("license", "unknown")) if isinstance(item, dict) else "unknown"
            if status in {"review_required", "unknown", None}:
                identifier = item.get("id", item.get("asset_id", "unknown")) if isinstance(item, dict) else "unknown"
                findings.append({"code": "license_review_required", "severity": "error", "message": f"{kind} {identifier} needs license review"})
    return findings
