from __future__ import annotations

from typing import Any
from pathlib import Path
from datetime import datetime
import hashlib
import re


def _audit_item(item: Any, kind: str) -> list[dict[str, str]]:
    if not isinstance(item, dict):
        return [{"code": "license_review_required", "severity": "error", "message": f"{kind} record is not an object"}]
    identifier = str(item.get("id", item.get("asset_id", "unknown")))
    status = item.get("approval_status", item.get("license", "unknown"))
    findings: list[dict[str, str]] = []
    if status not in {"approved", "verified", "project_owned"}:
        findings.append({"code": "license_review_required", "severity": "error", "message": f"{kind} {identifier} needs explicit license approval"})
    required = ("source_url", "license_evidence_url", "retrieved_at") if kind == "template" else ("source", "license_evidence_url", "retrieved_at")
    for field in required:
        if not isinstance(item.get(field), str) or not item[field].strip():
            findings.append({"code": "license_evidence_missing", "severity": "error", "message": f"{kind} {identifier} is missing {field}"})
    embedded = bool(item.get("embedded", kind == "asset"))
    # Catalogue-only references carry no imported bytes. Assets and any template
    # with a local payload must bind approval to both content and license bytes.
    if kind == "asset" or embedded or item.get("path"):
        for field in ("source_url", "license", "retrieved_at"):
            if not isinstance(item.get(field), str) or not item[field].strip() or item[field].lower() in {"unknown", "rejected", "verified"}:
                findings.append({"code": "license_evidence_missing", "severity": "error", "message": f"{identifier}: invalid {field}"})
        try:
            datetime.fromisoformat(item.get("retrieved_at", "").replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError):
            findings.append({"code": "license_evidence_missing", "severity": "error", "message": f"{identifier}: invalid retrieval time"})
        if item.get("hash_scope") != "file_bytes":
            findings.append({"code": "content_identity_missing", "severity": "error", "message": f"{identifier}: hash must cover file bytes"})
        for path_key, hash_key, prefix in (("path", "content_sha256", "content_identity"), ("license_evidence_path", "license_evidence_sha256", "license_evidence")):
            expected = item.get(hash_key)
            try:
                if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                    raise ValueError("missing SHA-256")
                payload = Path(item[path_key]).read_bytes()
                if not payload or hashlib.sha256(payload).hexdigest() != expected:
                    findings.append({"code": f"{prefix}_mismatch", "severity": "error", "message": f"{identifier}: {path_key} changed since approval"})
            except (KeyError, ValueError, TypeError, OSError):
                findings.append({"code": f"{prefix}_missing", "severity": "error", "message": f"{identifier}: missing verified {path_key}"})
    return findings


def check_export_license(manifest: dict[str, Any]) -> list[dict[str, str]]:
    """Return blocking findings for resources that are not publication-ready."""
    findings: list[dict[str, str]] = []
    for collection, kind in ((manifest.get("template_refs", []), "template"), (manifest.get("asset_refs", []), "asset")):
        for item in collection:
            findings.extend(_audit_item(item, kind))
    return findings
