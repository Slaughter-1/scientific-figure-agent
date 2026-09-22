from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
from typing import Any
import uuid


def spec_sha256(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_record(path: str | Path) -> dict[str, Any]:
    payload = Path(path).read_bytes()
    return {"size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def _payload_sha256(payload: Any) -> str:
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _relative_path(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_existing_path(value: Any, root: Path, fallback: Path | None = None) -> Path:
    if not isinstance(value, str):
        return fallback or root
    candidate = Path(value)
    options = [candidate]
    if not candidate.is_absolute():
        options.insert(0, root / candidate)
    if fallback is not None:
        options.append(fallback)
    for option in options:
        if option.is_file():
            return option
    return options[0]


def _evidence_counts(spec: dict[str, Any]) -> dict[str, Any]:
    nodes = [node for node in spec.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in spec.get("edges", []) if isinstance(edge, dict)]
    groups = [group for group in spec.get("groups", []) if isinstance(group, dict)]
    node_evidence = sum(bool(node.get("evidence")) for node in nodes)
    edge_evidence = sum(bool(edge.get("evidence")) for edge in edges)
    group_evidence = sum(bool(group.get("evidence")) for group in groups)
    return {
        "node_count": len(nodes),
        "nodes_with_evidence": node_evidence,
        "node_evidence_coverage": round(node_evidence / max(len(nodes), 1), 3),
        "edge_count": len(edges),
        "edges_with_evidence": edge_evidence,
        "edge_evidence_coverage": round(edge_evidence / max(len(edges), 1), 3),
        "group_count": len(groups),
        "groups_with_evidence": group_evidence,
        "needs_review_count": len(spec.get("needs_review", [])) if isinstance(spec.get("needs_review", []), list) else 0,
    }


def _file_role(relative_path: str) -> str:
    if relative_path == "request.json" or relative_path.startswith("input/"):
        return "input"
    if relative_path == "figure-contract.json":
        return "contract"
    if relative_path.startswith("candidates/"):
        return "candidate"
    if relative_path.startswith("reviews/"):
        return "review"
    if relative_path.startswith("versions/"):
        return "version"
    if relative_path.startswith("assets/"):
        return "asset"
    if relative_path.startswith("exports/"):
        return "export"
    return "other"


def build_task_evidence_manifest(
    task_root: str | Path,
    *,
    task_id: str,
    status: str | None = None,
    request: dict[str, Any] | None = None,
    review_actions: list[dict[str, Any]] | None = None,
    selected_candidate: dict[str, Any] | None = None,
    candidate_ids: set[str] | None = None,
    include_paths: set[str] | None = None,
    purpose: str = "Task-level evidence and reproducibility snapshot.",
) -> dict[str, Any]:
    """Build a hash-bound evidence manifest for one task directory.

    The manifest deliberately excludes its own ``evidence-manifest.json`` file
    from ``files``. This avoids a self-referential hash while keeping every
    source, Contract, candidate revision, review record, and rendered artifact
    in one task-scoped index.
    """
    root = Path(task_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"task directory does not exist: {root}")
    request_path = root / "request.json"
    request_payload = request if request is not None else (_read_json(request_path) or {})
    review_actions = list(review_actions or [])
    if selected_candidate is None:
        selected_candidate = next(
            (
                action
                for action in reversed(review_actions)
                if action.get("action") == "select_candidate" and isinstance(action.get("candidate_id"), str)
            ),
            None,
        )

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = _relative_path(root, path)
        if relative is None or relative == "evidence-manifest.json":
            continue
        if include_paths is not None and relative not in include_paths:
            continue
        record = {"path": relative, **file_record(path), "role": _file_role(relative)}
        files.append(record)

    contract_path = root / "figure-contract.json"
    contract_payload = _read_json(contract_path) if contract_path.is_file() else None
    contract = {"path": "figure-contract.json", **file_record(contract_path)} if contract_path.is_file() else None
    if contract_payload is not None:
        contract["content_sha256"] = _payload_sha256(contract_payload)
        contract["target_figure_type"] = contract_payload.get("target_figure_type")
        contract["required_label_count"] = len(contract_payload.get("required_labels", []))
        contract["required_edge_count"] = len(contract_payload.get("required_edges", []))
        contract["needs_review_count"] = len(contract_payload.get("needs_review", []))

    source_content = request_payload.get("content")
    source = {
        "input_type": request_payload.get("input_type"),
        "request_path": "request.json" if request_path.is_file() else None,
        "request_sha256": file_record(request_path)["sha256"] if request_path.is_file() else None,
        "content_sha256": _payload_sha256(source_content) if source_content is not None else None,
        "content_bytes": len(source_content.encode("utf-8")) if isinstance(source_content, str) else None,
    }

    candidate_revisions: list[dict[str, Any]] = []
    candidates_root = root / "candidates"
    candidate_paths = sorted(candidates_root.glob("candidate_*/candidate.json")) if candidates_root.is_dir() else []
    for candidate_path in candidate_paths:
        record = _read_json(candidate_path)
        if not record:
            continue
        candidate_id = str(record.get("candidate_id", candidate_path.parent.name))
        if candidate_ids is not None and candidate_id not in candidate_ids:
            continue
        spec_path_value = record.get("spec_path")
        spec_path = _resolve_existing_path(spec_path_value, root, candidate_path.parent / "figure-spec.json")
        spec = _read_json(spec_path) if spec_path.is_file() else None
        spec_relative = _relative_path(root, spec_path) if spec_path.is_file() else None
        artifact_records: dict[str, Any] = {}
        artifact_values = record.get("artifacts") if isinstance(record.get("artifacts"), dict) else {}
        for kind, artifact_path_value in artifact_values.items():
            if not isinstance(artifact_path_value, str):
                continue
            artifact_path = _resolve_existing_path(artifact_path_value, root)
            if not artifact_path.is_file():
                continue
            relative = _relative_path(root, artifact_path)
            if relative is not None:
                artifact_records[str(kind)] = {"path": relative, **file_record(artifact_path)}
        review_findings = record.get("review_findings") if isinstance(record.get("review_findings"), list) else []
        revision = {
            "candidate_id": candidate_id,
            "candidate_path": _relative_path(root, candidate_path),
            "candidate_sha256": file_record(candidate_path)["sha256"],
            "revision_id": record.get("revision_id"),
            "revision_number": record.get("revision_number"),
            "spec_path": spec_relative,
            "spec_sha256": spec_sha256(spec) if spec is not None else record.get("spec_sha256"),
            "artifact_records": artifact_records,
            "evidence": _evidence_counts(spec or {}),
            "review_findings": sorted({str(item.get("code")) for item in review_findings if isinstance(item, dict) and item.get("code")} ),
            "template_refs": (spec or {}).get("template_refs", []),
            "asset_refs": (spec or {}).get("asset_refs", []),
        }
        provenance = (spec or {}).get("provenance", {})
        metadata = (spec or {}).get("metadata", {})
        source_text = metadata.get("source_text") if isinstance(metadata, dict) else None
        revision["provenance"] = {
            "source": provenance.get("source") if isinstance(provenance, dict) else None,
            "parser": provenance.get("parser") if isinstance(provenance, dict) else None,
            "source_text_sha256": _payload_sha256(source_text) if isinstance(source_text, str) else None,
        }
        candidate_revisions.append(revision)

    evidence_totals = {
        "candidate_count": len(candidate_revisions),
        "node_count": sum(item["evidence"]["node_count"] for item in candidate_revisions),
        "nodes_with_evidence": sum(item["evidence"]["nodes_with_evidence"] for item in candidate_revisions),
        "edge_count": sum(item["evidence"]["edge_count"] for item in candidate_revisions),
        "edges_with_evidence": sum(item["evidence"]["edges_with_evidence"] for item in candidate_revisions),
        "needs_review_count": sum(item["evidence"]["needs_review_count"] for item in candidate_revisions),
    }
    template_refs = [ref for item in candidate_revisions for ref in item.get("template_refs", [])]
    asset_refs = [ref for item in candidate_revisions for ref in item.get("asset_refs", [])]
    resource_files = {
        "assets": [item for item in files if item["role"] == "asset"],
        "reviews": [item for item in files if item["role"] == "review"],
        "versions": [item for item in files if item["role"] == "version"],
        "exports": [item for item in files if item["role"] == "export"],
    }
    return {
        "manifest_type": "scientific-figure-agent-task-evidence",
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": purpose,
        "task_id": task_id,
        "status": status,
        "manifest_path": "evidence-manifest.json",
        "manifest_policy": "evidence-manifest.json is excluded from its own files hash list.",
        "request": request_payload,
        "source": source,
        "contract": contract,
        "candidate_revisions": candidate_revisions,
        "selected_candidate": selected_candidate,
        "review_actions": review_actions,
        "evidence": evidence_totals,
        "template_refs": template_refs,
        "asset_refs": asset_refs,
        "resource_files": resource_files,
        "files": files,
        "limitations": [
            "Hashes identify this task snapshot; they do not certify scientific correctness or publication quality.",
            "Independent visual review and real Figma connectivity remain separate release gates.",
        ],
    }


def write_task_evidence_manifest(task_root: str | Path, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
    """Persist the task evidence manifest atomically and return its path/payload."""
    root = Path(task_root)
    payload = build_task_evidence_manifest(root, **kwargs)
    path = root / "evidence-manifest.json"
    temporary = root / f".evidence-manifest.{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path, payload


# Keep the shorter name discoverable for callers that already use the generic
# ``build_manifest`` vocabulary; both names produce the same task-scoped format.
build_task_manifest = build_task_evidence_manifest


def verify_package(path: str | Path) -> dict[str, Any]:
    """Re-read the actual ZIP bytes, not the source files used by the packager."""
    with ZipFile(path) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP entries")
        manifest = json.loads(bundle.read("manifest.json"))
        entries = manifest.get("files")
        if not isinstance(entries, list) or any(not isinstance(item, dict) or not isinstance(item.get("path"), str) for item in entries):
            raise ValueError("manifest files must be a list of path records")
        expected_paths = [item["path"] for item in entries]
        if len(expected_paths) != len(set(expected_paths)):
            raise ValueError("duplicate manifest file paths")
        expected = set(expected_paths)
        if set(names) != expected | {"manifest.json"}:
            raise ValueError("ZIP contents differ from manifest")
        for item in entries:
            payload = bundle.read(item["path"])
            if len(payload) != item["size_bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError(f"ZIP hash mismatch: {item['path']}")
        evidence_path = manifest.get("evidence_manifest_path")
        if evidence_path:
            if evidence_path not in expected or evidence_path not in names:
                raise ValueError("evidence manifest is missing from ZIP")
            evidence_payload = bundle.read(evidence_path)
            expected_evidence_hash = manifest.get("evidence_manifest_sha256")
            if expected_evidence_hash and hashlib.sha256(evidence_payload).hexdigest() != expected_evidence_hash:
                raise ValueError("evidence manifest hash mismatch")
            evidence = json.loads(evidence_payload)
            if evidence.get("task_id") != manifest.get("task_id"):
                raise ValueError("evidence manifest task mismatch")
            selected = evidence.get("selected_candidate") or {}
            if selected.get("candidate_id") not in {None, manifest.get("candidate_id")}:
                raise ValueError("evidence manifest candidate mismatch")
        else:
            evidence = None
        spec = json.loads(bundle.read(manifest["spec_path"]))
        record = json.loads(bundle.read(manifest["candidate_path"]))
        if spec_sha256(spec) != manifest["spec_sha256"] or record["spec_sha256"] != manifest["spec_sha256"]:
            raise ValueError("ZIP Spec identity mismatch")
        if spec.get("revision_id") != manifest["revision_id"] or record["revision_id"] != manifest["revision_id"] or record["candidate_id"] != manifest["candidate_id"]:
            raise ValueError("ZIP candidate revision mismatch")
        contract_path = manifest.get("contract_path", "figure-contract.json")
        if contract_path not in names:
            raise ValueError("ZIP Contract is missing")
        contract_bytes = bundle.read(contract_path)
        contract = json.loads(contract_bytes)
        embedded_contract = spec.get("metadata", {}).get("figure_contract", {})
        if _payload_sha256(contract) != _payload_sha256(embedded_contract):
            raise ValueError("ZIP Contract identity mismatch")
        if manifest.get("contract_sha256") and manifest["contract_sha256"] != hashlib.sha256(contract_bytes).hexdigest():
            raise ValueError("ZIP Contract file identity mismatch")
        if manifest.get("contract_content_sha256") and manifest["contract_content_sha256"] != _payload_sha256(contract):
            raise ValueError("ZIP Contract content identity mismatch")
        request_path = manifest.get("request_path", "request.json")
        request = json.loads(bundle.read(request_path))
        request_content = request.get("content")
        source_text = spec.get("metadata", {}).get("source_text")
        if source_text is not None and _payload_sha256(source_text) != _payload_sha256(request_content):
            raise ValueError("ZIP Spec source identity mismatch")
        if evidence is not None:
            source = evidence.get("source") or {}
            if source.get("request_sha256") and source["request_sha256"] != hashlib.sha256(bundle.read(request_path)).hexdigest():
                raise ValueError("evidence source request identity mismatch")
            if source.get("content_sha256") and source["content_sha256"] != _payload_sha256(request_content):
                raise ValueError("evidence source content identity mismatch")
            evidence_contract = evidence.get("contract") or {}
            if evidence_contract.get("content_sha256") and evidence_contract["content_sha256"] != _payload_sha256(contract):
                raise ValueError("evidence Contract identity mismatch")
            expected_identity = {
                "candidate_id": manifest.get("candidate_id"),
                "revision_id": manifest.get("revision_id"),
                "revision_number": manifest.get("revision_number"),
                "spec_sha256": manifest.get("spec_sha256"),
            }
            selected = evidence.get("selected_candidate") or {}
            for field, expected_value in expected_identity.items():
                if field in selected and selected.get(field) != expected_value:
                    raise ValueError(f"evidence selected {field} identity mismatch")
            revisions = evidence.get("candidate_revisions") or []
            evidence_revision = next((item for item in revisions if item.get("candidate_id") == manifest.get("candidate_id")), None)
            if evidence_revision is None:
                raise ValueError("evidence candidate revision is missing")
            for field, expected_value in expected_identity.items():
                if field in evidence_revision and evidence_revision.get(field) != expected_value:
                    raise ValueError(f"evidence candidate {field} identity mismatch")
            pointer_path = f"candidates/{manifest.get('candidate_id')}/candidate.json"
            if pointer_path in names:
                pointer = json.loads(bundle.read(pointer_path))
                for field, expected_value in expected_identity.items():
                    if pointer.get(field) != expected_value:
                        raise ValueError(f"candidate pointer {field} identity mismatch")
                pointer_hash = hashlib.sha256(bundle.read(pointer_path)).hexdigest()
                if evidence_revision.get("candidate_sha256") and evidence_revision["candidate_sha256"] != pointer_hash:
                    raise ValueError("evidence candidate file identity mismatch")
    return {"status": "verified", "file_count": len(expected), "package_sha256": file_record(path)["sha256"]}


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
