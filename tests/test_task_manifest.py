import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


def _request():
    return {
        "input_type": "paper_text",
        "content": "用户问题经过规划器分解，检索器查询知识库，生成器输出答案。",
        "figure_goal": "method_overview",
    }


def test_task_manifest_binds_input_contract_candidates_and_evidence(tmp_path):
    from fastapi.testclient import TestClient
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/analyze").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200

    manifest = client.get(f"/api/tasks/{task_id}/manifest").json()
    assert manifest["manifest_type"] == "scientific-figure-agent-task-evidence"
    assert manifest["manifest_version"] == "1.0"
    assert manifest["task_id"] == task_id
    assert manifest["source"]["content_sha256"] == hashlib.sha256(_request()["content"].encode("utf-8")).hexdigest()
    assert manifest["contract"]["path"] == "figure-contract.json"
    assert len(manifest["candidate_revisions"]) == 3
    assert {item["candidate_id"] for item in manifest["candidate_revisions"]} == {"candidate_01", "candidate_02", "candidate_03"}
    assert all(len(item["spec_sha256"]) == 64 for item in manifest["candidate_revisions"])
    assert all(item["evidence"]["node_count"] == item["evidence"]["nodes_with_evidence"] for item in manifest["candidate_revisions"])
    assert manifest["review_actions"] == []
    assert all("sha256" in item and "size_bytes" in item for item in manifest["files"])
    assert not any(item["path"] == "evidence-manifest.json" for item in manifest["files"])


def test_export_contains_same_task_evidence_manifest(tmp_path):
    from fastapi.testclient import TestClient
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200
    response = client.post(f"/api/tasks/{task_id}/export", json={})
    assert response.status_code == 200

    with ZipFile(response.json()["path"]) as archive:
        export_manifest = json.loads(archive.read("manifest.json"))
        task_manifest_path = export_manifest["evidence_manifest_path"]
        task_manifest = json.loads(archive.read(task_manifest_path))
        assert task_manifest["task_id"] == task_id
        assert task_manifest["selected_candidate"]["candidate_id"] == "candidate_02"
        record = next(item for item in export_manifest["files"] if item["path"] == task_manifest_path)
        payload = archive.read(task_manifest_path)
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)


def test_export_rejects_task_contract_that_differs_from_confirmed_spec(tmp_path):
    from fastapi.testclient import TestClient
    from figure_agent.app.api import create_app

    client = TestClient(create_app(tmp_path))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200

    contract_path = tmp_path / "tasks" / task_id / "figure-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["required_labels"].append("未经确认的事实核查器")
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    response = client.post(f"/api/tasks/{task_id}/export", json={})
    assert response.status_code == 409
    assert "Contract" in response.text


def _rewrite_zip(source, target, mutate):
    with ZipFile(source) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(payloads["manifest.json"])
    evidence = json.loads(payloads["evidence-manifest.json"])
    mutate(evidence)
    evidence_bytes = json.dumps(evidence, ensure_ascii=False, indent=2).encode("utf-8")
    payloads["evidence-manifest.json"] = evidence_bytes
    evidence_record = next(item for item in manifest["files"] if item["path"] == "evidence-manifest.json")
    evidence_record.update(size_bytes=len(evidence_bytes), sha256=hashlib.sha256(evidence_bytes).hexdigest())
    manifest["evidence_manifest_sha256"] = evidence_record["sha256"]
    payloads["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with ZipFile(target, "w") as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)


@pytest.mark.parametrize("mutation, expected", [
    (lambda evidence: evidence["selected_candidate"].update(revision_id="candidate_02-old"), "revision"),
    (lambda evidence: evidence["source"].update(content_sha256="0" * 64), "source"),
])
def test_verify_package_rejects_evidence_identity_mismatch(tmp_path, mutation, expected):
    from fastapi.testclient import TestClient
    from figure_agent.app.api import create_app
    from figure_agent.artifacts import verify_package

    client = TestClient(create_app(tmp_path / "app"))
    task_id = client.post(f"/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200
    exported = client.post(f"/api/tasks/{task_id}/export", json={})
    assert exported.status_code == 200

    tampered = tmp_path / f"tampered-{expected}.zip"
    _rewrite_zip(exported.json()["path"], tampered, mutation)
    with pytest.raises(ValueError, match=expected):
        verify_package(tampered)


def test_verify_package_rejects_contract_identity_mismatch(tmp_path):
    from fastapi.testclient import TestClient
    from figure_agent.app.api import create_app
    from figure_agent.artifacts import spec_sha256, verify_package

    client = TestClient(create_app(tmp_path / "app"))
    task_id = client.post("/api/tasks", json=_request()).json()["task_id"]
    assert client.post(f"/api/tasks/{task_id}/generate-candidates").status_code == 200
    assert client.post(f"/api/tasks/{task_id}/select-candidate", json={"candidate_id": "candidate_02"}).status_code == 200
    exported = client.post(f"/api/tasks/{task_id}/export", json={})
    assert exported.status_code == 200

    source = Path(exported.json()["path"])
    tampered = tmp_path / "tampered-contract.zip"
    with ZipFile(source) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(payloads["manifest.json"])
    contract = json.loads(payloads["figure-contract.json"])
    contract["required_labels"].append("未经确认的事实核查器")
    contract_bytes = json.dumps(contract, ensure_ascii=False, indent=2).encode("utf-8")
    payloads["figure-contract.json"] = contract_bytes
    entry = next(item for item in manifest["files"] if item["path"] == "figure-contract.json")
    entry.update(size_bytes=len(contract_bytes), sha256=hashlib.sha256(contract_bytes).hexdigest())
    manifest["contract_sha256"] = entry["sha256"]
    manifest["contract_content_sha256"] = spec_sha256(contract)
    payloads["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with ZipFile(tampered, "w") as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)

    with pytest.raises(ValueError, match="Contract identity"):
        verify_package(tampered)
