from __future__ import annotations

import json
import hashlib
import mimetypes
import zipfile
import uuid
import re
from functools import wraps
from threading import RLock
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover - exercised when optional web deps are absent
    raise RuntimeError("Install the 'web' extra to use the local web API") from exc

from ..request import FigureRequest
from ..templates import search_templates
from ..workflow import build_figure_contract, generate_from_text, contract_findings
from ..artifacts import build_task_evidence_manifest, file_record, verify_package, write_task_evidence_manifest
from ..reviews import identify_issues, resolve_issue
from ..visual_critic import critique_spec_geometry
from ..license import check_export_license
from ..critic import critique_spec
from ..spec import require_valid_spec
from .store import TaskStore


mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def create_app(data_dir: str | Path = "figure-agent-data") -> FastAPI:
    data_root = Path(data_dir)
    store = TaskStore(data_root)
    app = FastAPI(title="Scientific Figure Agent", version="0.1.0")
    app.state.store = store
    mutation_lock = RLock()

    def serialized(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with mutation_lock:
                return function(*args, **kwargs)
        return wrapped

    def candidate_directory(task_id: str, candidate_id: str) -> Path:
        if store.get_task(task_id) is None:
            raise KeyError(task_id)
        if not isinstance(candidate_id, str) or not re.fullmatch(r"candidate_\d{2}", candidate_id):
            raise ValueError("candidate_id is invalid")
        return data_root / "tasks" / task_id / "candidates" / candidate_id

    def public_candidate(task_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
        result = dict(candidate)
        artifacts = {}
        for key, value in candidate.get("artifacts", {}).items():
            path = Path(value)
            try:
                relative = path.relative_to(data_root / "tasks" / task_id)
                artifacts[key] = f"/api/tasks/{task_id}/files/{relative.as_posix()}"
            except ValueError:
                artifacts[key] = None
        result["artifacts"] = artifacts
        return result

    def _spec_hash(spec: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _contract_conflicts(spec: dict[str, Any]) -> list[dict[str, str]]:
        return contract_findings(spec)

    def refresh_task_manifest(task_id: str, **kwargs: Any) -> tuple[Path, dict[str, Any]]:
        task = store.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return write_task_evidence_manifest(
            data_root / "tasks" / task_id,
            task_id=task_id,
            status=task.get("status"),
            request=task.get("request"),
            review_actions=store.list_review_actions(task_id),
            selected_candidate=store.selected_candidate_binding(task_id),
            **kwargs,
        )

    def materialize_review_action(task_id: str, action: dict[str, Any]) -> dict[str, Any] | None:
        """Apply a semantic review action using a staged revision directory."""
        action_name = action.get("action")
        supported = {"remove_node", "lock_node", "unlock_node", "mark_needs_evidence", "resolve_needs_evidence", "dismiss_review"}
        if action_name not in supported:
            return None
        candidate_id = action.get("candidate_id") or store.selected_candidate(task_id)
        if not isinstance(candidate_id, str):
            return None  # historical record-only behavior has no candidate context
        candidate_dir = candidate_directory(task_id, candidate_id)
        candidate_path = candidate_dir / "candidate.json"
        if not candidate_path.exists():
            raise KeyError(f"candidate not found: {candidate_id}")
        previous_result = json.loads(candidate_path.read_text(encoding="utf-8"))
        spec_path = Path(previous_result["spec_path"])
        if action.get("base_revision") is not None and action["base_revision"] != previous_result.get("revision_id"):
            raise PermissionError("stale base_revision; reload the current candidate")
        if action.get("base_version") is not None and action["base_version"] != previous_result.get("revision_number"):
            raise PermissionError("stale base_version; reload the current candidate")
        current = json.loads(spec_path.read_text(encoding="utf-8"))
        if _spec_hash(current) != previous_result.get("spec_sha256"):
            raise PermissionError("current Spec hash does not match the published revision")
        old_spec = json.loads(json.dumps(current, ensure_ascii=False))
        identify_issues(current, previous_result["revision_id"])
        revision_number = int(previous_result.get("revision_number", 1)) + 1
        revision_id = f"{candidate_id}-r{uuid.uuid4().hex[:10]}"
        target = action.get("target")
        node = next((item for item in current.get("nodes", []) if item.get("id") == target or item.get("label") == target), None)
        if node is None and action_name not in {"dismiss_review"}:
            raise ValueError(f"review target not found: {target}")
        if action_name == "remove_node":
            if node.get("locked"):
                raise PermissionError("node is locked; unlock it before removal")
            node_id = node["id"]
            current["nodes"] = [item for item in current["nodes"] if item.get("id") != node_id]
            current["edges"] = [edge for edge in current.get("edges", []) if edge.get("source") != node_id and edge.get("target") != node_id]
            current["groups"] = [{**group, "children": [child for child in group.get("children", []) if child != node_id]} for group in current.get("groups", [])]
            current["groups"] = [group for group in current["groups"] if group["children"]]
            for issue in list(current.get("needs_review", [])):
                if issue.get("target") in {node_id, target}:
                    resolve_issue(current, issue, resolution="no_longer_applicable", reason=action.get("reason") or "Node removed by user", evidence=[], revision_id=revision_id)
        elif action_name in {"lock_node", "unlock_node"}:
            node["locked"] = action_name == "lock_node"
        elif action_name == "mark_needs_evidence":
            finding = {"code": "needs_evidence", "target": node["id"], "message": action.get("reason", "Evidence required before export")}
            if not any(item.get("code") == finding["code"] and item.get("target") == finding["target"] for item in current.get("needs_review", [])):
                current["needs_review"] = [*current.get("needs_review", []), finding]
        elif action_name in {"resolve_needs_evidence", "dismiss_review"}:
            matches = [issue for issue in current.get("needs_review", []) if (issue["issue_id"] == action["issue_id"] if action.get("issue_id") else issue.get("target") in {target, node.get("id") if node else target} and (action_name != "resolve_needs_evidence" or issue.get("code") == "needs_evidence"))]
            if len(matches) != 1:
                raise ValueError("identify exactly one unresolved issue using issue_id")
            issue = matches[0]
            if issue.get("code", "").startswith("contract_required_"):
                raise ValueError("Contract conflicts require an amended Contract, not dismissal")
        if action_name == "resolve_needs_evidence":
            evidence = action.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("evidence must be a non-empty list")
            content = store.get_task(task_id)["request"].get("content", "")
            for reference in evidence:
                if not isinstance(reference, dict) or not str(reference.get("source", "")).strip() or not str(reference.get("quote", "")).strip():
                    raise ValueError("each evidence entry requires non-empty source and quote")
                if reference.get("source") == "input_text" and reference["quote"] not in content:
                    raise ValueError("evidence quote is not present in task input")
                if reference.get("source") != "input_text" and not reference.get("location"):
                    raise ValueError("external evidence requires a source location")
            node["evidence"] = [*node.get("evidence", []), *evidence]
            resolve_issue(current, issue, resolution="evidence_added", reason=action.get("reason") or "Added source evidence", evidence=evidence, revision_id=revision_id)
        elif action_name == "dismiss_review":
            if not str(action.get("reason", "")).strip():
                raise ValueError("reason is required to dismiss a review finding")
            resolve_issue(current, issue, resolution="dismissed", reason=action["reason"], evidence=[], revision_id=revision_id)
        conflicts = _contract_conflicts(current)
        current.setdefault("needs_review", [])
        current["needs_review"].extend(finding for finding in conflicts if not any(item.get("code") == finding["code"] and item.get("target") == finding["target"] for item in current["needs_review"]))
        identify_issues(current, revision_id)
        require_valid_spec(current)
        current["revision_id"] = revision_id
        revision_dir = candidate_dir / "revisions" / revision_id
        revision_dir.mkdir(parents=True, exist_ok=False)
        try:
            if current.get("figure_type") == "plot":
                from ..backends.plot_backend import render_plot_spec
                rendered = render_plot_spec(current, revision_dir, "figure")
            else:
                from ..backends.drawio_backend import render_drawio_spec
                rendered = render_drawio_spec(current, revision_dir, "figure")
        except Exception as exc:
            _atomic_json(revision_dir / "revision-error.json", {"revision_id": revision_id, "status": "failed", "error": str(exc)})
            raise OSError(f"revision render failed: {exc}") from exc
        expected_formats = {"svg", "pdf", "png"} | ({"drawio"} if current.get("figure_type") != "plot" else set())
        if expected_formats - set(rendered) or not all(Path(path).exists() and Path(path).stat().st_size > 0 for path in rendered.values()):
            raise OSError("revision render did not produce complete artifacts")
        result = previous_result
        result.update({"spec": current, "revision_id": revision_id, "revision_number": revision_number, "spec_sha256": _spec_hash(current), "spec_path": str(revision_dir / "figure-spec.json"), "artifacts": {key: str(value) for key, value in rendered.items()}, "artifact_records": {key: file_record(path) for key, path in rendered.items()}, "review_findings": critique_spec(current) + (critique_spec_geometry(current) if current.get("figure_type") != "plot" else [])})
        _atomic_json(revision_dir / "figure-spec.json", current)
        _atomic_json(revision_dir / "candidate.json", result)
        store.save_version_snapshot(task_id, "figure-spec-before-review", old_spec)
        review_result = store.record_review_action(task_id, {**action, "applied": True, "base_revision": old_spec.get("revision_id"), "revision_id": revision_id, "spec_sha256": result["spec_sha256"]})
        _atomic_json(candidate_dir / "figure-spec.json", current)
        _atomic_json(candidate_path, result)
        candidates_path = candidate_dir.parent / "candidates.json"
        candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        if isinstance(candidates, dict):
            candidates = candidates.get("candidates", [])
        for index, candidate in enumerate(candidates):
            if candidate.get("candidate_id") == candidate_id:
                candidates[index] = result
        _atomic_json(candidates_path, candidates)
        store.save_version_snapshot(task_id, "figure-spec-after-review", current)
        return {"review": review_result, "candidate": public_candidate(task_id, result)}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/tasks", status_code=201)
    def create_task(request: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = FigureRequest.from_dict(request).to_dict()
            result = store.create_task(normalized)
            refresh_task_manifest(result["task_id"])
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return store.list_tasks()

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.post("/api/tasks/{task_id}/status")
    def update_status(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = store.update_status(task_id, payload.get("status", ""), payload.get("error"))
            refresh_task_manifest(task_id)
            return result
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/analyze")
    @serialized
    def analyze_task(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        content = task["request"].get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=422, detail="analysis currently requires textual content")
        try:
            store.update_status(task_id, "analyzing")
            contract = build_figure_contract(content, target_figure_type=task["request"].get("target_figure_type"))
            contract_path = data_root / "tasks" / task_id / "figure-contract.json"
            contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
            store.update_status(task_id, "created")
            refresh_task_manifest(task_id)
            return {"task_id": task_id, "contract": contract, "path": str(contract_path)}
        except (OSError, ValueError) as exc:
            store.update_status(task_id, "failed", str(exc))
            refresh_task_manifest(task_id)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/search-templates")
    def search_task_templates(task_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        payload = payload or {}
        try:
            return search_templates(str(payload.get("query", "workflow")), policy=str(payload.get("policy", "open_license_first")), limit=int(payload.get("limit", 3)))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/generate-candidates")
    @serialized
    def generate_task_candidates(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        content = task["request"].get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=422, detail="candidate generation currently requires textual content")
        output_dir = data_root / "tasks" / task_id / "candidates"
        for path in output_dir.glob("candidate_*/candidate.json"):
            if any(node.get("locked") for node in json.loads(path.read_text(encoding="utf-8")).get("spec", {}).get("nodes", [])):
                raise HTTPException(status_code=409, detail="unlock nodes before regenerating candidates")
        try:
            store.update_status(task_id, "generating_candidates")
            contract_path = data_root / "tasks" / task_id / "figure-contract.json"
            saved_contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.exists() else None
            result = generate_from_text(content, output_dir, count=task["request"].get("candidate_count", 3), template_policy=task["request"].get("template_policy", "open_license_first"), target_figure_type=task["request"].get("target_figure_type"), contract=saved_contract)
            contract_path.write_text(json.dumps(result["contract"], ensure_ascii=False, indent=2), encoding="utf-8")
            store.update_status(task_id, "awaiting_review")
            refresh_task_manifest(task_id)
            return {"task_id": task_id, "contract": result["contract"], "candidate_count": len(result["candidates"]), "candidates": [public_candidate(task_id, item) for item in result["candidates"]]}
        except (OSError, ValueError) as exc:
            store.update_status(task_id, "failed", str(exc))
            refresh_task_manifest(task_id)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/candidates")
    def get_task_candidates(task_id: str) -> dict[str, Any]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        candidates_path = data_root / "tasks" / task_id / "candidates" / "candidates.json"
        if not candidates_path.exists():
            raise HTTPException(status_code=404, detail="candidates not generated")
        return {"task_id": task_id, "candidates": [public_candidate(task_id, json.loads((candidates_path.parent / item["candidate_id"] / "candidate.json").read_text(encoding="utf-8"))) for item in json.loads(candidates_path.read_text(encoding="utf-8"))]}

    @app.post("/api/tasks/{task_id}/select-candidate")
    @serialized
    def select_candidate(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_id = payload.get("candidate_id")
        if not isinstance(candidate_id, str):
            raise HTTPException(status_code=422, detail="candidate_id is required")
        if not re.fullmatch(r"candidate_\d{2}", candidate_id):
            raise HTTPException(status_code=422, detail="candidate_id is invalid")
        candidate_dir = data_root / "tasks" / task_id / "candidates" / candidate_id
        if not (candidate_dir / "candidate.json").is_file():
            raise HTTPException(status_code=404, detail="candidate not found")
        candidate_record = json.loads((candidate_dir / "candidate.json").read_text(encoding="utf-8"))
        if payload.get("revision_id") is not None and payload["revision_id"] != candidate_record.get("revision_id"):
            raise HTTPException(status_code=409, detail="preview revision is stale; reload before selecting")
        result = store.record_review_action(task_id, {"action": "select_candidate", "candidate_id": candidate_id, "revision_id": candidate_record.get("revision_id"), "spec_sha256": candidate_record.get("spec_sha256")})
        store.update_status(task_id, "assembling")
        refresh_task_manifest(task_id)
        return {"task_id": task_id, "candidate_id": candidate_id, "review": result}

    @app.get("/api/tasks/{task_id}/manifest")
    def task_manifest(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        try:
            _, manifest = refresh_task_manifest(task_id)
            return manifest
        except (FileNotFoundError, OSError, KeyError) as exc:
            raise HTTPException(status_code=500, detail=f"task manifest failed: {exc}") from exc

    @app.post("/api/tasks/{task_id}/export")
    @serialized
    def export_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        candidate_id = payload.get("candidate_id")
        selected = store.selected_candidate_binding(task_id)
        if candidate_id is None:
            candidate_id = selected.get("candidate_id") if selected else None
        if candidate_id is None:
            raise HTTPException(status_code=409, detail="select a candidate before export")
        if not isinstance(candidate_id, str) or not re.fullmatch(r"candidate_\d{2}", candidate_id):
            raise HTTPException(status_code=422, detail="candidate_id is invalid")
        candidate_dir = data_root / "tasks" / task_id / "candidates" / candidate_id
        if not candidate_dir.is_dir():
            raise HTTPException(status_code=404, detail="candidate not found")
        if selected is None:
            raise HTTPException(status_code=409, detail="select a candidate before export")
        if selected.get("candidate_id") != candidate_id:
            raise HTTPException(status_code=409, detail=f"candidate {candidate_id} is not the selected candidate {selected.get('candidate_id')}")
        current_record = json.loads((candidate_dir / "candidate.json").read_text(encoding="utf-8"))
        if selected.get("revision_id") != current_record.get("revision_id") or selected.get("spec_sha256") != current_record.get("spec_sha256"):
            raise HTTPException(status_code=409, detail="candidate changed after selection; select the current revision again")
        spec_path = Path(current_record["spec_path"])
        if not spec_path.is_file():
            raise HTTPException(status_code=409, detail="current revision Spec is missing")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if _spec_hash(spec) != current_record.get("spec_sha256") or spec.get("revision_id") != selected.get("revision_id"):
            raise HTTPException(status_code=409, detail="current Spec differs from the confirmed revision")
        if spec.get("needs_review") or contract_findings(spec):
            raise HTTPException(status_code=409, detail="candidate has unresolved review findings")
        findings = critique_spec(spec) + check_export_license(spec)
        if spec.get("figure_type") != "plot":
            findings.extend(critique_spec_geometry(spec))
            if any(not node.get("evidence") for node in spec.get("nodes", [])):
                findings.append({"severity": "error", "code": "missing_evidence", "message": "Scientific nodes require evidence regardless of Spec version"})
        if any(item.get("severity") == "error" for item in findings):
            raise HTTPException(status_code=409, detail={"message": "publication checks failed", "findings": findings})
        required_outputs = set(task["request"].get("required_outputs", []))
        artifacts = current_record.get("artifacts", {})
        missing_outputs = sorted(required_outputs - set(artifacts))
        if missing_outputs:
            raise HTTPException(status_code=409, detail=f"candidate is missing requested outputs: {', '.join(missing_outputs)}")
        for kind, artifact_path in artifacts.items():
            path = Path(artifact_path)
            if not path.is_file() or file_record(path) != current_record.get("artifact_records", {}).get(kind):
                raise HTTPException(status_code=409, detail=f"artifact missing or changed: {kind}")
        export_dir = data_root / "tasks" / task_id / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        archive = export_dir / f"{current_record['revision_id']}-{uuid.uuid4().hex[:8]}.zip"
        staged_archive = archive.with_suffix(".tmp")
        task_root = data_root / "tasks" / task_id
        contract = spec.get("metadata", {}).get("figure_contract", {})
        contract_path = task_root / "figure-contract.json"
        if contract_path.is_file():
            contract_payload = contract_path.read_bytes()
            try:
                task_contract = json.loads(contract_payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=409, detail=f"task Contract is invalid: {exc}") from exc
            if _spec_hash(task_contract) != _spec_hash(contract):
                raise HTTPException(status_code=409, detail="task Contract differs from the confirmed candidate Contract")
        else:
            task_contract = contract
            contract_payload = json.dumps(contract, ensure_ascii=False, indent=2).encode("utf-8")
        candidate_path = spec_path.parent / "candidate.json"
        candidate_pointer_path = candidate_dir / "candidate.json"
        package_paths = [spec_path, candidate_path, candidate_pointer_path, task_root / "request.json"]
        if contract_path.is_file():
            package_paths.append(contract_path)
        package_paths.extend(Path(path) for path in artifacts.values())
        for resource in [*spec.get("asset_refs", []), *spec.get("template_refs", [])]:
            if isinstance(resource, dict) and resource.get("path"):
                package_paths.extend(Path(resource[key]) for key in ("path", "license_evidence_path"))
        if any(not path.is_file() or task_root.resolve() not in path.resolve().parents for path in package_paths):
            raise HTTPException(status_code=409, detail="package source is missing or outside the task")
        package_paths = list(dict.fromkeys(package_paths))
        package_relative_paths = {path.relative_to(task_root).as_posix() for path in package_paths}
        task_evidence_manifest = build_task_evidence_manifest(
            task_root,
            task_id=task_id,
            status=task.get("status"),
            request=task.get("request"),
            review_actions=store.list_review_actions(task_id),
            selected_candidate=selected,
            candidate_ids={candidate_id},
            include_paths=package_relative_paths,
            purpose="Evidence snapshot for the selected candidate export.",
        )
        evidence_payload = json.dumps(task_evidence_manifest, ensure_ascii=False, indent=2).encode("utf-8")
        package_files = [{"path": path.relative_to(task_root).as_posix(), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in package_paths]
        if not contract_path.is_file():
            package_files.append({"path": "figure-contract.json", "size_bytes": len(contract_payload), "sha256": hashlib.sha256(contract_payload).hexdigest()})
        package_files.append({"path": "evidence-manifest.json", "size_bytes": len(evidence_payload), "sha256": hashlib.sha256(evidence_payload).hexdigest()})
        export_manifest = {"schema_version": "1.0", "task_id": task_id, "candidate_id": candidate_id, "revision_id": current_record.get("revision_id"), "revision_number": current_record.get("revision_number"), "spec_sha256": current_record.get("spec_sha256"), "spec_path": spec_path.relative_to(task_root).as_posix(), "candidate_path": candidate_path.relative_to(task_root).as_posix(), "request_path": "request.json", "contract_path": "figure-contract.json", "contract_sha256": hashlib.sha256(contract_payload).hexdigest(), "contract_content_sha256": _spec_hash(task_contract), "evidence_manifest_path": "evidence-manifest.json", "task_manifest_path": "evidence-manifest.json", "evidence_manifest_sha256": hashlib.sha256(evidence_payload).hexdigest(), "review_actions": store.list_review_actions(task_id), "files": package_files, "template_refs": spec.get("template_refs", []), "asset_refs": spec.get("asset_refs", []), "publication_checks": findings, "export_ready": True, "publish_ready": False, "limitations": ["Independent visual and scientific review required; automated checks do not certify publication quality."]}
        store.update_status(task_id, "exporting")
        try:
            with zipfile.ZipFile(staged_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in package_paths:
                    bundle.write(path, path.relative_to(task_root))
                if not contract_path.is_file():
                    bundle.writestr("figure-contract.json", contract_payload)
                bundle.writestr("evidence-manifest.json", evidence_payload)
                bundle.writestr("manifest.json", json.dumps(export_manifest, ensure_ascii=False, indent=2))
            verification = verify_package(staged_archive)
            staged_archive.replace(archive)
            _atomic_json(archive.with_suffix(".verification.json"), verification)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            store.update_status(task_id, "failed", str(exc))
            refresh_task_manifest(task_id)
            raise HTTPException(status_code=409, detail=f"package verification failed: {exc}") from exc
        store.update_status(task_id, "completed")
        refresh_task_manifest(task_id)
        return {"task_id": task_id, "candidate_id": candidate_id, "revision_id": current_record["revision_id"], "verification": verification, "path": str(archive), "download_url": f"/api/tasks/{task_id}/files/exports/{archive.name}"}

    @app.get("/api/tasks/{task_id}/files/{file_path:path}")
    def task_file(task_id: str, file_path: str) -> FileResponse:
        task_root = (data_root / "tasks" / task_id).resolve()
        target = (task_root / file_path).resolve()
        if store.get_task(task_id) is None or task_root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(target)

    @app.post("/api/tasks/{task_id}/review-actions")
    @serialized
    def review_action(task_id: str, action: dict[str, Any]) -> dict[str, Any]:
        try:
            result = materialize_review_action(task_id, action)
            response = result if result is not None else store.record_review_action(task_id, {**action, "applied": False, "reason_not_applied": "No supported candidate mutation was requested"})
            refresh_task_manifest(task_id)
            return response
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @app.post("/api/tasks/{task_id}/assets")
    async def upload_asset(task_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        target = Path(data_dir) / "tasks" / task_id / "assets" / Path(file.filename or "upload.bin").name
        target.write_bytes(await file.read())
        result = store.register_artifact(task_id, target, "user_asset", editable=target.suffix.lower() in {".svg", ".drawio", ".json"})
        refresh_task_manifest(task_id)
        return result

    frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        @app.get("/", include_in_schema=False)
        def frontend_not_built() -> dict[str, str]:
            return {"status": "ok", "message": "Frontend is not built. Run `cd frontend; npm install; npm run dev` or `npm run build`."}

    return app
