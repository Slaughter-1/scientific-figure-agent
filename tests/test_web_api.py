from fastapi.testclient import TestClient


def _request():
    return {"input_type": "paper_text", "content": "Query → Retriever → Generator", "figure_goal": "method_overview"}


def test_local_api_creates_and_persists_task(tmp_path):
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
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
