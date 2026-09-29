#!/usr/bin/env python3
"""Run one real business loop through the product HTTP entry point.

创建任务 -> 分析 -> 生成三候选 -> 审阅修改 -> 生成新修订 -> 重新选择 -> 正式导出 -> 校验导出包

This script only calls the HTTP API; it never reaches into the pipeline internals,
so a green run is evidence about the product surface rather than about a helper.
Usage:  python scripts/run_business_loop.py --data-dir outputs/loop-acceptance
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

DEFAULT_TEXT = "文本经过分词、编码后送入分类器并输出标签"


class Loop:
    """Record every assertion so a partial failure still reports the whole picture."""

    def __init__(self, client: Any, verbose: bool = True) -> None:
        self.client = client
        self.verbose = verbose
        self.records: list[dict[str, Any]] = []

    def step(self, name: str, response: Any, expect: int = 200) -> Any:
        ok = response.status_code == expect
        self.records.append({"step": name, "status": response.status_code, "expected": expect, "ok": ok})
        if self.verbose:
            print(f"{'OK ' if ok else 'BAD'} {name}: {response.status_code} (expect {expect})")
            if not ok:
                print(f"     body: {response.text[:400]}")
        return response

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.records.append({"step": name, "status": "assert", "expected": True, "ok": bool(ok)})
        if self.verbose:
            print(f"{'OK ' if ok else 'BAD'} {name}: {detail}")
        return bool(ok)

    @property
    def failures(self) -> list[str]:
        return [record["step"] for record in self.records if not record["ok"]]


def assert_data_dir_is_safe(data_dir: Path, reset: bool = False) -> None:
    """Never silently destroy an existing run.

    The loop's own evidence (``loop-acceptance-evidence.json``), the task tree and the
    exported packages all live inside ``data_dir``. Clearing it automatically would
    delete the very artifacts a previous run produced as proof, with no way back, so a
    non-empty directory is refused unless the caller opts in explicitly.
    """
    if not data_dir.exists():
        return
    existing = sorted(p.name for p in data_dir.iterdir())
    if not existing:
        return
    if not reset:
        raise SystemExit(
            f"{data_dir} 已存在且非空（{len(existing)} 项，例如 {existing[:3]}）。\n"
            "为避免删除既有任务与证据，脚本不会自动清空。请任选其一：\n"
            f"  1) 换一个目录：--data-dir {data_dir.parent / (data_dir.name + '-2')}\n"
            "  2) 确实要丢弃该目录的内容：显式加 --reset"
        )
    shutil.rmtree(data_dir)


def run_loop(data_dir: Path, text: str = DEFAULT_TEXT, verbose: bool = True,
             reset: bool = False) -> dict[str, Any]:
    """Drive the full loop and return a machine-checkable evidence record."""
    from fastapi.testclient import TestClient

    from figure_agent.artifacts import verify_package
    from figure_agent.app.api import create_app

    assert_data_dir_is_safe(data_dir, reset=reset)
    loop = Loop(TestClient(create_app(data_dir=str(data_dir))), verbose=verbose)
    client = loop.client

    created = loop.step("1 创建任务", client.post("/api/tasks", json={
        "input_type": "paper_text", "content": text, "figure_goal": "method_overview",
        "paper_width": "double_column", "candidate_count": 3,
        "required_outputs": ["svg", "pdf", "png", "drawio"]}), 201)
    task_id = created.json()["task_id"]

    analyzed = loop.step("2 分析生成 Contract", client.post(f"/api/tasks/{task_id}/analyze"))
    contract = analyzed.json()["contract"]
    loop.check("3 Contract 覆盖输入的五个步骤",
               len(contract.get("required_labels", [])) == 5,
               str(contract.get("required_labels")))

    generated = loop.step("4 生成三候选", client.post(f"/api/tasks/{task_id}/generate-candidates", json={}))
    loop.check("5 候选数为 3", generated.json().get("candidate_count") == 3,
               str(generated.json().get("candidate_count")))
    candidates = client.get(f"/api/tasks/{task_id}/candidates").json()["candidates"]
    chosen = next(item for item in candidates if item["candidate_id"] == "candidate_02")
    rev1, num1 = chosen["revision_id"], chosen["revision_number"]

    loop.step("6 未选择即导出必须被拒", client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    loop.step("7 选择 candidate_02 (v1)", client.post(f"/api/tasks/{task_id}/select-candidate",
              json={"candidate_id": "candidate_02", "revision_id": rev1}))
    return _continue_loop(loop, task_id, candidates, chosen, rev1, num1, verify_package, data_dir)


def _continue_loop(loop, task_id, candidates, chosen, rev1, num1, verify_package, data_dir):
    client = loop.client

    marked = loop.step("8 审阅修改 mark_needs_evidence -> 新修订 v2",
                       client.post(f"/api/tasks/{task_id}/review-actions", json={
                           "action": "mark_needs_evidence", "candidate_id": "candidate_02",
                           "target": "node_2", "base_revision": rev1, "base_version": num1,
                           "reason": "编码步骤需要补充出处"}))
    v2 = marked.json()["candidate"]
    rev2, num2 = v2["revision_id"], v2["revision_number"]
    issue_id = v2["spec"]["needs_review"][0]["issue_id"]

    loop.step("9 存在未解决审阅项时导出必须被拒",
              client.post(f"/api/tasks/{task_id}/export", json={"candidate_id": "candidate_02"}), 409)

    resolved = loop.step("10 补证据 resolve_needs_evidence -> 新修订 v3",
                         client.post(f"/api/tasks/{task_id}/review-actions", json={
                             "action": "resolve_needs_evidence", "candidate_id": "candidate_02",
                             "target": "node_2", "issue_id": issue_id, "base_revision": rev2,
                             "base_version": num2, "reason": "引用输入原句",
                             "evidence": [{"source": "input_text", "quote": "编码"}]}))
    v3 = resolved.json()["candidate"]
    rev3, num3 = v3["revision_id"], v3["revision_number"]

    loop.check("11 三个修订互不相同", len({rev1, rev2, rev3}) == 3, f"{rev1} / {rev2} / {rev3}")
    loop.check("12 修订号单调递增", [num1, num2, num3] == [1, 2, 3], f"v{num1}->v{num2}->v{num3}")
    loop.check("13 v3 无未解决审阅项",
               not [item for item in v3["spec"].get("needs_review", []) if not item.get("resolution")],
               str(v3["spec"].get("needs_review")))

    loop.step("14 用旧修订再次修改必须被拒", client.post(f"/api/tasks/{task_id}/review-actions", json={
        "action": "lock_node", "candidate_id": "candidate_02", "target": "node_0",
        "base_revision": rev1}), 409)
    loop.step("15 修改后沿用旧选择导出必须被拒", client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    loop.step("16 用旧修订重新选择必须被拒", client.post(f"/api/tasks/{task_id}/select-candidate",
              json={"candidate_id": "candidate_02", "revision_id": rev1}), 409)
    loop.step("17 按新修订重新选择 (v3)", client.post(f"/api/tasks/{task_id}/select-candidate",
              json={"candidate_id": "candidate_02", "revision_id": rev3}))

    exported = loop.step("18 正式导出", client.post(f"/api/tasks/{task_id}/export", json={}))
    payload = exported.json()
    archive = Path(payload["path"])
    loop.check("19 导出绑定重新确认的修订", payload.get("revision_id") == rev3,
               f"{payload.get('revision_id')} == {rev3}")
    return _verify_package_evidence(loop, task_id, candidates, archive, payload, v3,
                                    (rev1, rev2, rev3), verify_package, data_dir)


def _verify_package_evidence(loop, task_id, candidates, archive, payload, v3, revisions,
                             verify_package, data_dir):
    client = loop.client
    rev1, rev2, rev3 = revisions

    try:
        verification = verify_package(archive)
        loop.check("20 校验导出包（重新读取 ZIP，逐字节重算哈希）", True,
                   json.dumps(verification, ensure_ascii=False)[:200])
    except Exception as exc:  # noqa: BLE001 - the failure detail is the evidence
        verification = {"error": f"{type(exc).__name__}: {exc}"}
        loop.check("20 校验导出包（重新读取 ZIP，逐字节重算哈希）", False, verification["error"])

    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest = json.loads(bundle.read("manifest.json"))

    loop.check("21 manifest 修订与导出一致",
               manifest["revision_id"] == rev3 and manifest["spec_sha256"] == v3["spec_sha256"],
               f"{manifest['revision_id']}, sha 匹配={manifest['spec_sha256'] == v3['spec_sha256']}")
    missing = [item["path"] for item in manifest["files"] if item["path"] not in names]
    loop.check("22 manifest 列出的文件都在包内", not missing, f"缺失={missing}; ZIP 条目={len(names)}")
    loop.check("23 四种产物齐全",
               {"svg", "pdf", "png", "drawio"} <= {Path(name).suffix.lstrip(".") for name in names},
               str(sorted({Path(name).suffix for name in names})))
    loop.check("24 包内只含被导出的修订",
               not [name for name in names if "/revisions/" in name and rev3 not in name],
               f"其他修订的文件={[n for n in names if '/revisions/' in n and rev3 not in n]}")
    trail = [(item.get("action"), item.get("revision_id")) for item in manifest["review_actions"]]
    loop.check("25 审阅轨迹随包留存且只含成功动作",
               trail == [("select_candidate", rev1), ("mark_needs_evidence", rev2),
                         ("resolve_needs_evidence", rev3), ("select_candidate", rev3)],
               f"{len(trail)} 条: {[action for action, _ in trail]}")
    loop.check("26 未自称可发表",
               manifest["export_ready"] is True and manifest["publish_ready"] is False,
               f"export_ready={manifest['export_ready']}, publish_ready={manifest['publish_ready']}")

    negative = _contract_negative(loop, task_id, candidates)
    official = _retain_official_package(loop, archive, data_dir)
    _tamper_negative(loop, archive, data_dir, verify_package)

    return {
        "task_id": task_id, "revisions": list(revisions),
        "export_archive": archive.name, "export_revision_id": payload.get("revision_id"),
        "official_package": official,
        "manifest_revision_id": manifest["revision_id"], "verification": verification,
        "zip_entries": sorted(names), "review_trail": [action for action, _ in trail],
        "contract_negative_codes": negative,
        "assertions": loop.records, "failures": loop.failures,
        "all_ok": not loop.failures,
    }


def _contract_negative(loop, task_id, candidates):
    """Removing a Contract-required node must block export and must not be dismissable."""
    client = loop.client
    other = next(item for item in candidates if item["candidate_id"] == "candidate_03")
    broken = loop.step("27 candidate_03 删除 Contract 必需节点",
                       client.post(f"/api/tasks/{task_id}/review-actions", json={
                           "action": "remove_node", "candidate_id": "candidate_03", "target": "node_4",
                           "base_revision": other["revision_id"], "reason": "负例：移除 Contract 必需节点"}))
    record = broken.json()["candidate"]
    codes = [item["code"] for item in record["spec"]["needs_review"]]
    loop.check("28 删除必需节点触发 Contract 冲突",
               any(code.startswith("contract_required_") for code in codes), str(codes))
    loop.step("29 选择该候选", client.post(f"/api/tasks/{task_id}/select-candidate",
              json={"candidate_id": "candidate_03", "revision_id": record["revision_id"]}))
    loop.step("30 冲突未解决时导出必须被拒", client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    loop.step("31 Contract 冲突不可被 dismiss", client.post(f"/api/tasks/{task_id}/review-actions", json={
        "action": "dismiss_review", "candidate_id": "candidate_03", "target": "输出标签",
        "issue_id": record["spec"]["needs_review"][0]["issue_id"], "reason": "试图跳过"}), 422)
    return codes


def _retain_official_package(loop, archive, data_dir):
    """Keep the real export next to the evidence, under an unmistakable name.

    The genuine package is written deep under ``tasks/<uuid>/exports/``, while the
    tamper negative lands at the top of ``data_dir``. Without this copy the only
    visible ZIP beside the evidence is the corrupted one, which invites treating the
    negative as if it were the deliverable. Copy, never move: the task tree must keep
    its own export.
    """
    kept = data_dir / "official-export.zip"
    shutil.copy2(archive, kept)
    source_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    kept_sha = hashlib.sha256(kept.read_bytes()).hexdigest()
    loop.check("33 正式导出包单独留存且与原件逐字节相同",
               kept_sha == source_sha and kept.stat().st_size == archive.stat().st_size,
               f"{kept.name} sha={kept_sha[:16]} size={kept.stat().st_size}")
    return {"path": str(kept), "source": str(archive), "sha256": kept_sha,
            "size": kept.stat().st_size}


def _tamper_negative(loop, archive, data_dir, verify_package):
    """A one-byte edit inside the ZIP must make verification fail."""
    tampered = data_dir / "tampered-negative.zip"
    with zipfile.ZipFile(archive) as source:
        payload = {name: source.read(name) for name in source.namelist()}
    victim = next(name for name in payload if name.endswith("figure-spec.json"))
    payload[victim] = payload[victim].replace(b'"nodes"', b'"NODES"', 1)
    with zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in payload.items():
            target.writestr(name, data)
    try:
        verify_package(tampered)
        loop.check("32 篡改导出包后校验必须失败", False, "校验竟然通过了")
    except Exception as exc:  # noqa: BLE001 - the raised error is the evidence
        loop.check("32 篡改导出包后校验必须失败", True, f"{type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="outputs/loop-acceptance")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--report", default=None, help="write the evidence JSON here")
    parser.add_argument("--reset", action="store_true",
                        help="discard an existing --data-dir before running; without it a "
                             "non-empty directory is refused so prior tasks and evidence survive")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    result = run_loop(data_dir, text=args.text, reset=args.reset)
    report = Path(args.report) if args.report else data_dir / "loop-acceptance.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(result['assertions'])} 项断言，失败 {len(result['failures'])} 项: {result['failures']}")
    print(f"证据: {report}")
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
