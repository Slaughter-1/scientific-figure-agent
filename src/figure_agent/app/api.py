from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import FileResponse
except ImportError as exc:  # pragma: no cover - exercised when optional web deps are absent
    raise RuntimeError("Install the 'web' extra to use the local web API") from exc

from ..request import FigureRequest
from ..templates import search_templates
from ..workflow import build_figure_contract, generate_from_text
from .store import TaskStore


def create_app(data_dir: str | Path = "figure-agent-data") -> FastAPI:
    data_root = Path(data_dir)
    store = TaskStore(data_root)
    app = FastAPI(title="Scientific Figure Agent", version="0.1.0")
    app.state.store = store

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

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/tasks", status_code=201)
    def create_task(request: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = FigureRequest.from_dict(request).to_dict()
            return store.create_task(normalized)
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
            return store.update_status(task_id, payload.get("status", ""), payload.get("error"))
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/analyze")
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
            return {"task_id": task_id, "contract": contract, "path": str(contract_path)}
        except (OSError, ValueError) as exc:
            store.update_status(task_id, "failed", str(exc))
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
    def generate_task_candidates(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        content = task["request"].get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=422, detail="candidate generation currently requires textual content")
        output_dir = data_root / "tasks" / task_id / "candidates"
        try:
            store.update_status(task_id, "generating_candidates")
            result = generate_from_text(content, output_dir, count=task["request"].get("candidate_count", 3), template_policy=task["request"].get("template_policy", "open_license_first"))
            store.update_status(task_id, "awaiting_review")
            return {"task_id": task_id, "contract": result["contract"], "candidate_count": len(result["candidates"]), "candidates": [public_candidate(task_id, item) for item in result["candidates"]]}
        except (OSError, ValueError) as exc:
            store.update_status(task_id, "failed", str(exc))
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/candidates")
    def get_task_candidates(task_id: str) -> dict[str, Any]:
        if store.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="task not found")
        candidates_path = data_root / "tasks" / task_id / "candidates" / "candidates.json"
        if not candidates_path.exists():
            raise HTTPException(status_code=404, detail="candidates not generated")
        return {"task_id": task_id, "candidates": [public_candidate(task_id, item) for item in json.loads(candidates_path.read_text(encoding="utf-8"))]}

    @app.post("/api/tasks/{task_id}/select-candidate")
    def select_candidate(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_id = payload.get("candidate_id")
        if not isinstance(candidate_id, str):
            raise HTTPException(status_code=422, detail="candidate_id is required")
        result = store.record_review_action(task_id, {"action": "select_candidate", "candidate_id": candidate_id})
        store.update_status(task_id, "assembling")
        return {"task_id": task_id, "candidate_id": candidate_id, "review": result}

    @app.get("/api/tasks/{task_id}/manifest")
    def task_manifest(task_id: str) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        task_root = data_root / "tasks" / task_id
        files = []
        for path in task_root.rglob("*"):
            if path.is_file() and path.name != "request.json":
                files.append({"path": str(path.relative_to(task_root)), "size_bytes": path.stat().st_size})
        return {"task_id": task_id, "status": task["status"], "request": task["request"], "files": sorted(files, key=lambda item: item["path"])}

    @app.post("/api/tasks/{task_id}/export")
    def export_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        candidate_id = payload.get("candidate_id", "candidate_01")
        if not isinstance(candidate_id, str) or not candidate_id.startswith("candidate_"):
            raise HTTPException(status_code=422, detail="candidate_id is invalid")
        candidate_dir = data_root / "tasks" / task_id / "candidates" / candidate_id
        if not candidate_dir.is_dir():
            raise HTTPException(status_code=404, detail="candidate not found")
        export_dir = data_root / "tasks" / task_id / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        archive = export_dir / f"{candidate_id}.zip"
        store.update_status(task_id, "exporting")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in candidate_dir.rglob("*"):
                if path.is_file():
                    bundle.write(path, path.relative_to(candidate_dir.parent.parent))
            manifest = task_manifest(task_id)
            bundle.writestr("task-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        store.update_status(task_id, "completed")
        return {"task_id": task_id, "candidate_id": candidate_id, "path": str(archive), "download_url": f"/api/tasks/{task_id}/files/exports/{archive.name}"}

    @app.get("/api/tasks/{task_id}/files/{file_path:path}")
    def task_file(task_id: str, file_path: str) -> FileResponse:
        task_root = (data_root / "tasks" / task_id).resolve()
        target = (task_root / file_path).resolve()
        if store.get_task(task_id) is None or task_root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(target)

    @app.post("/api/tasks/{task_id}/review-actions")
    def review_action(task_id: str, action: dict[str, Any]) -> dict[str, Any]:
        try:
            return store.record_review_action(task_id, action)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task not found") from exc

    @app.post("/api/tasks/{task_id}/assets")
    async def upload_asset(task_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        target = Path(data_dir) / "tasks" / task_id / "assets" / Path(file.filename or "upload.bin").name
        target.write_bytes(await file.read())
        return store.register_artifact(task_id, target, "user_asset", editable=target.suffix.lower() in {".svg", ".drawio", ".json"})

    return app
