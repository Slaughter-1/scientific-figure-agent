from __future__ import annotations

import hashlib
import json
from typing import Any


def spec_sha256(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_manifest(spec: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    from .license import check_export_license

    license_findings = check_export_license(spec)
    return {
        "schema_version": "0.1",
        "spec_sha256": spec_sha256(spec),
        "backends": sorted(artifacts),
        "artifacts": artifacts,
        "license_findings": license_findings,
        "publish_ready": not any(item.get("severity") == "error" for item in license_findings),
        "limitations": [
            "Backend statuses describe local execution and do not certify scientific semantic correctness."
        ],
    }
