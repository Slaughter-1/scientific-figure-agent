from fastapi.testclient import TestClient


def _request():
    return {"input_type": "paper_text", "content": "Query → Retriever → Generator", "figure_goal": "method_overview"}


def test_local_api_creates_and_persists_task(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    html = client.get("/").text
    script_path = html.split('src="', 1)[1].split('"', 1)[0]
    assert client.get(script_path).headers["content-type"].startswith("application/javascript")
    created = client.post("/api/tasks", json=_request())
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "created"
    task_id = payload["task_id"]
    assert client.get(f"/api/tasks/{task_id}").json()["request"]["input_type"] == "paper_text"
    assert len(client.get("/api/tasks").json()) == 1


def test_local_api_records_status_and_review_action(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    updated = client.post(f"/api/tasks/{task_id}/status", json={"status": "awaiting_review"})
    assert updated.status_code == 200
    action = client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "lock_node", "target": "retriever"})
    assert action.status_code == 200
    assert action.json()["action"]["target"] == "retriever"


def test_review_action_creates_a_task_version(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    action = client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "mark_needs_evidence", "target": "retriever", "reason": "需补充原文引用"})

    assert action.status_code == 200
    assert action.json()["action"]["base_version"] == 0
    versions = client.get(f"/api/tasks/{task_id}/manifest").json()["files"]
    assert any(item["path"].startswith("versions/") for item in versions)


def test_local_api_uploads_asset_and_registers_hash(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    response = client.post(f"/api/tasks/{task_id}/assets", files={"file": ("component.svg", b"<svg />", "image/svg+xml")})
    assert response.status_code == 200
    assert response.json()["editable"] is True
    assert len(response.json()["sha256"]) == 64


def test_local_api_analyzes_and_generates_candidates(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    contract = client.post(f"/api/tasks/{task_id}/analyze")
    assert contract.status_code == 200
    assert contract.json()["contract"]["target_figure_type"] == "workflow"
    generated = client.post(f"/api/tasks/{task_id}/generate-candidates")
    assert generated.status_code == 200
    assert generated.json()["candidate_count"] == 3
    assert generated.json()["candidates"][0]["design"]["family"]
    assert generated.json()["candidates"][0]["design"]["rationale"]
    assert set(generated.json()["candidates"][0]["artifacts"]) >= {"svg", "pdf", "drawio"}
    svg_url = generated.json()["candidates"][0]["artifacts"]["svg"]
    assert client.get(svg_url).status_code == 200
    assert client.get(f"/api/tasks/{task_id}").json()["status"] == "awaiting_review"
    assert client.get(f"/api/tasks/{task_id}/candidates").status_code == 200
    selected = client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"})
    assert selected.status_code == 200
    assert client.get(f"/api/tasks/{task_id}/manifest").json()["task_id"] == task_id
    exported = client.post(f"/api/tasks/{task_id}/export", json={"candidate_id": "candidate_02"})
    assert exported.status_code == 200
    assert client.get(exported.json()["download_url"]).status_code == 200


def test_export_without_candidate_uses_selected_candidate(tmp_path):
    from zipfile import ZipFile
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_03"}).status_code == 200
    exported = client.post(f"/api/tasks/{task_id}/export", json={})
    assert exported.status_code == 200
    assert exported.json()["verification"]["status"] == "verified"
    with ZipFile(exported.json()["path"]) as archive:
        assert any(name.startswith("candidates/candidate_03/") for name in archive.namelist())


def test_export_without_selection_is_blocked(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/export", json={}).status_code == 409


def test_remove_node_review_action_materializes_new_spec_and_artifacts(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200
    before = client.get(f"/api/tasks/{task_id}/files/candidates/candidate_02/figure-spec.json").json()
    assert any(node["label"] == "Retriever" for node in before["nodes"])

    response = client.post(
        f"/api/tasks/{task_id}/review-actions",
        json={"action": "remove_node", "candidate_id": "candidate_02", "target": "Retriever", "reason": "not supported"},
    )
    assert response.status_code == 200
    after = client.get(f"/api/tasks/{task_id}/files/candidates/candidate_02/figure-spec.json").json()
    assert all(node["label"] != "Retriever" for node in after["nodes"])
    assert all(edge["source"] != "node_1" and edge["target"] != "node_1" for edge in after["edges"])
    assert any(item["code"] == "contract_required_node_missing" for item in after["needs_review"])
    assert client.post(f"/api/tasks/{task_id}/export", json={}).status_code == 409
    files = client.get(f"/api/tasks/{task_id}/manifest").json()["files"]
    assert any(item["path"].startswith("versions/") and "figure-spec" in item["path"] for item in files)


def test_lock_and_needs_evidence_review_actions_update_spec(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_01"}).status_code == 200
    for action in (
        {"action": "lock_node", "candidate_id": "candidate_01", "target": "node_0"},
        {"action": "mark_needs_evidence", "candidate_id": "candidate_01", "target": "node_2", "reason": "cite source"},
    ):
        assert client.post(f"/api/tasks/{task_id}/review-actions", json=action).status_code == 200
    spec = client.get(f"/api/tasks/{task_id}/files/candidates/candidate_01/figure-spec.json").json()
    assert next(node for node in spec["nodes"] if node["id"] == "node_0")["locked"] is True
    assert any(item.get("target") == "node_2" for item in spec["needs_review"])
    assert client.post(f"/api/tasks/{task_id}/export", json={}).status_code == 409


def test_export_cannot_override_selected_candidate(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_03"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/export", json={"candidate_id": "candidate_01"}).status_code == 409


def test_explicit_candidate_export_without_selection_is_blocked(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/export", json={"candidate_id": "candidate_01"}).status_code == 409


def test_export_manifest_binds_revision_and_contains_only_current_artifacts(tmp_path):
    import hashlib
    import json
    from zipfile import ZipFile
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200
    response = client.post(f"/api/tasks/{task_id}/export", json={})
    assert response.status_code == 200
    with ZipFile(response.json()["path"]) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["candidate_id"] == "candidate_02"
        assert manifest["revision_id"]
        assert len(manifest["spec_sha256"]) == 64
        assert not any(name.startswith("candidates/candidate_01/") for name in names)
        for item in manifest["files"]:
            payload = archive.read(item["path"])
            assert hashlib.sha256(payload).hexdigest() == item["sha256"]


def test_failed_review_render_keeps_previous_revision_current(tmp_path, monkeypatch):
    from figure_agent.app.api import create_app
    import figure_agent.backends.drawio_backend as drawio_backend

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_01"}).status_code == 200
    before = client.get(f"/api/tasks/{task_id}/files/candidates/candidate_01/figure-spec.json").content
    monkeypatch.setattr(drawio_backend, "render_drawio_spec", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected render failure")))
    response = client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "remove_node", "candidate_id": "candidate_01", "target": "node_1"})
    assert response.status_code == 422
    assert client.get(f"/api/tasks/{task_id}/files/candidates/candidate_01/figure-spec.json").content == before


def test_locked_node_requires_explicit_unlock_before_removal(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_01"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "lock_node", "candidate_id": "candidate_01", "target": "node_1"}).status_code == 200
    blocked = client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "remove_node", "candidate_id": "candidate_01", "target": "node_1"})
    assert blocked.status_code == 409
    assert client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "unlock_node", "candidate_id": "candidate_01", "target": "node_1"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "remove_node", "candidate_id": "candidate_01", "target": "node_1"}).status_code == 200


def test_evidence_review_can_be_resolved_without_clearing_unrelated_findings(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_01"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "mark_needs_evidence", "candidate_id": "candidate_01", "target": "node_1", "reason": "cite retriever"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/review-actions", json={"action": "resolve_needs_evidence", "candidate_id": "candidate_01", "target": "node_1", "evidence": [{"source": "input_text", "quote": "Retriever"}]}).status_code == 200
    spec = client.get(f"/api/tasks/{task_id}/files/candidates/candidate_01/figure-spec.json").json()
    assert not any(item.get("code") == "needs_evidence" and item.get("target") == "node_1" for item in spec["needs_review"])
    assert next(node for node in spec["nodes"] if node["id"] == "node_1")["evidence"][-1]["quote"] == "Retriever"
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_01"}).status_code == 200
    assert client.post(f"/api/tasks/{task_id}/export", json={}).status_code == 200
