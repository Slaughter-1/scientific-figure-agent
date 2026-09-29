#!/usr/bin/env python3
"""D/R3 真实外部素材端到端验收：一正三负，全部经由产品 HTTP 入口。

正例：上传素材与许可证 -> 登记(pending_review) -> 未审核即导出被拒 -> 显式审核(approved)
      -> 按新修订重新选择 -> 正式导出 -> 重新读取 ZIP 核对素材与许可证字节。

负例（各自独立数据目录，互不污染正例）：
  1 未审核许可：登记后不审核就导出。
  2 缺失许可证证据：没有证据文件却试图审核。
  3 审核后素材字节被改动：审核通过后替换磁盘上的素材。

三个负例都必须被拒绝，并如实记录拒绝实际发生在登记、审核还是导出阶段。

Usage:
  python scripts/run_asset_acceptance.py --data-dir outputs/D-asset-acceptance
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
DEFAULT_PACK = "inputs/RC2_D_Real_Asset_Pack"

#: 上游原件身份，取自素材包 source/provenance.json。脚本只核对，绝不改写。
EXPECTED_ASSET = {"name": "circle-stack.svg", "size": 576,
                  "sha256": "a3e20dd4b182fd428ab2b66c65ced2f91b5c9a4f49e39ac96c9c1e04772d23e6"}
EXPECTED_LICENSE = {"name": "Heroicons-LICENSE.txt", "size": 1071,
                    "sha256": "60e0b68c0f35c078eef3a5d29419d0b03ff84ec1df9c3f9d6e39a519a5ae7985"}
_REF = "0435d4ca364a608cc75e2f8683d374e55abbae26"
SOURCE_URL = f"https://github.com/tailwindlabs/heroicons/blob/{_REF}/optimized/24/outline/circle-stack.svg"
LICENSE_URL = f"https://github.com/tailwindlabs/heroicons/blob/{_REF}/LICENSE"

class Run:
    """记录每一条断言，局部失败也要报告全貌。"""

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


def assert_dir_is_safe(data_dir: Path) -> None:
    """既有任务与证据一律不自动清空；本脚本不提供 --reset。"""
    if data_dir.exists() and any(data_dir.iterdir()):
        existing = sorted(p.name for p in data_dir.iterdir())
        raise SystemExit(
            f"{data_dir} 已存在且非空（{len(existing)} 项，例如 {existing[:3]}）。\n"
            "为避免删除既有任务与证据，脚本不会自动清空，也不提供 --reset。\n"
            f"请改用新目录：--data-dir {data_dir.parent / (data_dir.name + '-2')}"
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pack(run: Run, pack: Path) -> dict[str, Any]:
    """先核对素材包原件，再谈登记。身份不符就不该继续。"""
    asset = pack / "assets" / EXPECTED_ASSET["name"]
    license_file = pack / "licenses" / EXPECTED_LICENSE["name"]
    identity: dict[str, Any] = {}
    for label, path, expected in (("素材", asset, EXPECTED_ASSET), ("许可证", license_file, EXPECTED_LICENSE)):
        digest, size = _sha256(path), path.stat().st_size
        # 上游 git blob id 由字节重算：能对上说明这就是上游仓库里的那份字节，
        # 而不是经过改写或换行转换后的再序列化版本。
        blob = hashlib.sha1(b"blob %d\x00" % size + path.read_bytes()).hexdigest()
        identity[label] = {"path": str(path), "sha256": digest, "size_bytes": size,
                           "upstream_git_blob_sha1": blob, "cr_count": path.read_bytes().count(b"\r")}
        run.check(f"A{1 if label == '素材' else 2} {label}原件与 provenance 一致",
                  digest == expected["sha256"] and size == expected["size"],
                  f"sha={digest[:16]} size={size}")
    return identity


def _stage_inputs(client: Any, task_id: str, pack: Path) -> dict[str, str]:
    """通过产品上传入口把原件放进任务目录（导出要求资源在任务目录内）。"""
    staged = {}
    for kind, relative, mime in (("asset", f"assets/{EXPECTED_ASSET['name']}", "image/svg+xml"),
                                 ("license", f"licenses/{EXPECTED_LICENSE['name']}", "text/plain")):
        source = pack / relative
        with open(source, "rb") as handle:
            response = client.post(f"/api/tasks/{task_id}/assets",
                                   files={"file": (source.name, handle, mime)})
        response.raise_for_status()
        staged[kind] = response.json()["path"]
    return staged


def _new_task(run: Run, text: str, count: int = 1) -> tuple[str, list[dict[str, Any]]]:
    created = run.step("创建任务", run.client.post("/api/tasks", json={
        "input_type": "paper_text", "content": text, "figure_goal": "method_overview",
        "paper_width": "double_column", "candidate_count": count,
        "required_outputs": ["svg", "pdf", "png", "drawio"]}), 201)
    task_id = created.json()["task_id"]
    run.step("分析生成 Contract", run.client.post(f"/api/tasks/{task_id}/analyze"))
    run.step("生成候选", run.client.post(f"/api/tasks/{task_id}/generate-candidates", json={}))
    candidates = run.client.get(f"/api/tasks/{task_id}/candidates").json()["candidates"]
    return task_id, candidates


def _attach(client: Any, task_id: str, candidate: dict[str, Any], staged: dict[str, str],
            *, license_name: str = "MIT", with_evidence: bool = True) -> Any:
    """登记：只记录证据，绝不在此处批准（register_asset 默认 pending_review）。"""
    payload = {"action": "attach_asset", "candidate_id": candidate["candidate_id"],
               "target": "node_0", "base_revision": candidate["revision_id"],
               "path": staged["asset"], "license": license_name,
               "source": "heroicons_v2.2.0", "source_url": SOURCE_URL,
               "license_evidence_url": LICENSE_URL}
    if with_evidence:
        payload["license_evidence_path"] = staged["license"]
    return client.post(f"/api/tasks/{task_id}/review-actions", json=payload)


def _approve(client: Any, task_id: str, candidate_id: str, revision_id: str, asset_id: str,
             staged: dict[str, str], *, license_name: str = "MIT") -> Any:
    """审核：依据用户明确同意的用途与上游 MIT 证据，显式升为 approved。"""
    return client.post(f"/api/tasks/{task_id}/review-actions", json={
        "action": "approve_asset", "candidate_id": candidate_id,
        "base_revision": revision_id, "asset_id": asset_id,
        "license": license_name, "source_url": SOURCE_URL,
        "license_evidence_url": LICENSE_URL,
        "license_evidence_path": staged["license"],
        "reason": "用户明确同意本次 D/R3 使用 Heroicons circle-stack，依据上游 MIT 许可证原文"})


def run_positive(run: Run, pack: Path, text: str, data_dir: Path) -> dict[str, Any]:
    """正例：登记 -> 未审即导出被拒 -> 显式审核 -> 重新选择 -> 正式导出 -> 重读 ZIP。"""
    client = run.client
    task_id, candidates = _new_task(run, text)
    chosen = candidates[0]
    staged = _stage_inputs(client, task_id, pack)

    task_root = (data_dir / "tasks" / task_id).resolve()
    run.check("A3 上传后素材落在该任务目录内",
              Path(staged["asset"]).is_file() and task_root in Path(staged["asset"]).resolve().parents,
              staged["asset"])
    run.check("A4 上传未改动素材字节",
              _sha256(Path(staged["asset"])) == EXPECTED_ASSET["sha256"],
              _sha256(Path(staged["asset"]))[:16])

    attached = run.step("B1 登记素材（走 register_asset）",
                        _attach(client, task_id, chosen, staged))
    v2 = attached.json()["candidate"]
    asset = v2["spec"]["asset_refs"][0]
    run.check("B2 登记后状态为 pending_review，未被默认批准",
              asset["approval_status"] == "pending_review", asset["approval_status"])
    run.check("B3 登记记录的 hash 覆盖文件字节且与上游一致",
              asset["hash_scope"] == "file_bytes" and asset["content_sha256"] == EXPECTED_ASSET["sha256"],
              f"{asset['hash_scope']} sha={asset['content_sha256'][:16]}")
    run.check("B4 许可证名称为 MIT，不是 verified/project_owned 之类的状态词",
              asset["license"] == "MIT", str(asset["license"]))

    run.step("B5 选择该修订", client.post(f"/api/tasks/{task_id}/select-candidate",
             json={"candidate_id": chosen["candidate_id"], "revision_id": v2["revision_id"]}))
    blocked = run.step("B6 素材未审核时导出必须被拒",
                       client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    codes = {item["code"] for item in blocked.json().get("detail", {}).get("findings", [])}
    run.check("B7 拒绝原因是许可待审", "license_review_required" in codes, str(sorted(codes)))

    approved_response = run.step("C1 显式审核素材许可（approved）",
                                 _approve(client, task_id, chosen["candidate_id"],
                                          v2["revision_id"], asset["asset_id"], staged))
    v3 = approved_response.json()["candidate"]
    approved_asset = v3["spec"]["asset_refs"][0]
    run.check("C2 审核后状态为 approved 且沿用同一 asset_id",
              approved_asset["approval_status"] == "approved" and approved_asset["asset_id"] == asset["asset_id"],
              f"{approved_asset['approval_status']} / {approved_asset['asset_id']}")
    run.check("C3 审核记录绑定许可证证据字节",
              approved_asset["license_evidence_sha256"] == EXPECTED_LICENSE["sha256"],
              str(approved_asset["license_evidence_sha256"])[:16])
    trail = [item.get("action") for item in client.get(f"/api/tasks/{task_id}/manifest").json().get("review_actions", [])]
    run.check("C4 登记与审核都留在审阅轨迹里",
              trail.count("attach_asset") == 1 and trail.count("approve_asset") == 1, str(trail))

    run.step("C5 按审核后的新修订重新选择", client.post(f"/api/tasks/{task_id}/select-candidate",
             json={"candidate_id": chosen["candidate_id"], "revision_id": v3["revision_id"]}))
    exported = run.step("C6 正式导出", client.post(f"/api/tasks/{task_id}/export", json={}))
    payload = exported.json()
    return _verify_export(run, Path(payload["path"]), payload, v3, approved_asset, data_dir, task_id)


def _verify_export(run: Run, archive: Path, payload: dict[str, Any], v3: dict[str, Any],
                   asset: dict[str, Any], data_dir: Path, task_id: str) -> dict[str, Any]:
    """重新读取 ZIP 本身的字节，而不是相信打包时写下的清单。"""
    from figure_agent.artifacts import verify_package

    try:
        verification = verify_package(archive)
        run.check("D1 导出包自校验通过（逐字节重算哈希）", True,
                  json.dumps(verification, ensure_ascii=False)[:160])
    except Exception as exc:  # noqa: BLE001 - 失败详情本身就是证据
        verification = {"error": f"{type(exc).__name__}: {exc}"}
        run.check("D1 导出包自校验通过（逐字节重算哈希）", False, verification["error"])

    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest = json.loads(bundle.read("manifest.json"))
        asset_entry = next((n for n in names if n.endswith(EXPECTED_ASSET["name"])), None)
        license_entry = next((n for n in names if n.endswith(EXPECTED_LICENSE["name"])), None)
        asset_bytes = bundle.read(asset_entry) if asset_entry else b""
        license_bytes = bundle.read(license_entry) if license_entry else b""

    run.check("D2 素材文件确实在包内", asset_entry is not None, str(asset_entry))
    run.check("D3 许可证全文确实在包内", license_entry is not None, str(license_entry))
    run.check("D4 包内素材字节与登记记录及上游一致",
              hashlib.sha256(asset_bytes).hexdigest() == EXPECTED_ASSET["sha256"] == asset["content_sha256"],
              f"{hashlib.sha256(asset_bytes).hexdigest()[:16]} / {len(asset_bytes)}B")
    run.check("D5 包内许可证字节与登记记录及上游一致",
              hashlib.sha256(license_bytes).hexdigest() == EXPECTED_LICENSE["sha256"] == asset["license_evidence_sha256"],
              f"{hashlib.sha256(license_bytes).hexdigest()[:16]} / {len(license_bytes)}B")
    run.check("D6 许可证正文保留 MIT 与原版权方",
              b"MIT License" in license_bytes and b"Tailwind Labs" in license_bytes,
              f"含 MIT={b'MIT License' in license_bytes}, 含权利人={b'Tailwind Labs' in license_bytes}")
    run.check("D7 清单指向当前候选与修订",
              manifest["revision_id"] == v3["revision_id"] and manifest["spec_sha256"] == v3["spec_sha256"],
              f"{manifest['revision_id']} sha匹配={manifest['spec_sha256'] == v3['spec_sha256']}")
    packaged = next((item for item in manifest.get("asset_refs", []) if item.get("asset_id") == asset["asset_id"]), None)
    run.check("D8 清单内素材记录为 approved 且许可为 MIT",
              bool(packaged) and packaged["approval_status"] == "approved" and packaged["license"] == "MIT",
              json.dumps({k: packaged.get(k) for k in ("approval_status", "license")}, ensure_ascii=False) if packaged else "缺失")
    run.check("D9 未自称可发表",
              manifest["export_ready"] is True and manifest["publish_ready"] is False,
              f"export_ready={manifest['export_ready']}, publish_ready={manifest['publish_ready']}")

    # 正式包单独留存，名字不可与负例混淆；复制而非移动，任务树保留自己的导出。
    kept = data_dir / "official-export.zip"
    shutil.copy2(archive, kept)
    run.check("D10 正式导出包单独留存且与原件逐字节相同",
              _sha256(kept) == _sha256(archive) and kept.stat().st_size == archive.stat().st_size,
              f"{kept.name} sha={_sha256(kept)[:16]} size={kept.stat().st_size}")

    return {"task_id": task_id, "revision_id": v3["revision_id"],
            "export_archive": str(archive), "official_package": str(kept),
            "official_package_sha256": _sha256(kept), "verification": verification,
            "asset_zip_entry": asset_entry, "license_zip_entry": license_entry,
            "asset_record": {k: asset.get(k) for k in
                             ("asset_id", "license", "approval_status", "source", "source_url",
                              "license_evidence_url", "hash_scope", "content_sha256",
                              "license_evidence_sha256", "retrieved_at")},
            "zip_entries": sorted(names)}


def negative_unreviewed(run: Run, pack: Path, text: str) -> dict[str, Any]:
    """负例 1：许可待审／未知，登记后不审核直接导出。"""
    client = run.client
    task_id, candidates = _new_task(run, text)
    chosen = candidates[0]
    staged = _stage_inputs(client, task_id, pack)
    attached = _attach(client, task_id, chosen, staged, license_name="unknown")
    run.check("N1.1 登记本身允许（登记只记录证据，不做批准）",
              attached.status_code == 200, str(attached.status_code))
    v2 = attached.json()["candidate"]
    client.post(f"/api/tasks/{task_id}/select-candidate",
                json={"candidate_id": chosen["candidate_id"], "revision_id": v2["revision_id"]})
    response = run.step("N1.2 未审核即导出必须被拒",
                        client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    codes = sorted({item["code"] for item in response.json().get("detail", {}).get("findings", [])})
    run.check("N1.3 拒绝原因含许可待审", "license_review_required" in codes, str(codes))
    return {"case": "未知/待审许可", "rejected": response.status_code == 409,
            "rejected_at": "导出", "status_code": response.status_code, "codes": codes,
            "asset_status": v2["spec"]["asset_refs"][0]["approval_status"]}


def negative_missing_evidence(run: Run, pack: Path, text: str) -> dict[str, Any]:
    """负例 2：没有许可证证据文件，却试图审核通过。"""
    client = run.client
    task_id, candidates = _new_task(run, text)
    chosen = candidates[0]
    staged = _stage_inputs(client, task_id, pack)
    attached = _attach(client, task_id, chosen, staged, with_evidence=False)
    v2 = attached.json()["candidate"]
    asset = v2["spec"]["asset_refs"][0]
    run.check("N2.1 缺证据时登记记录没有许可证哈希",
              asset.get("license_evidence_sha256") is None, str(asset.get("license_evidence_sha256")))

    # 证据文件从任务目录移走，审核时便无从核验。
    removed = Path(staged["license"])
    quarantine = removed.with_name(removed.name + ".removed")
    removed.replace(quarantine)
    response = run.step("N2.2 缺失许可证证据时审核必须被拒",
                        client.post(f"/api/tasks/{task_id}/review-actions", json={
                            "action": "approve_asset", "candidate_id": chosen["candidate_id"],
                            "base_revision": v2["revision_id"], "asset_id": asset["asset_id"],
                            "license": "MIT", "source_url": SOURCE_URL,
                            "license_evidence_url": LICENSE_URL,
                            "license_evidence_path": staged["license"],
                            "reason": "负例：证据文件不存在"}), 422)
    detail = str(response.json().get("detail", ""))[:200]
    run.check("N2.3 拒绝理由指向缺失的许可证证据",
              "license_evidence_path" in detail, detail)

    # 还原现场，保持该负例目录可复查。
    quarantine.replace(removed)
    client.post(f"/api/tasks/{task_id}/select-candidate",
                json={"candidate_id": chosen["candidate_id"], "revision_id": v2["revision_id"]})
    export = run.step("N2.4 该候选仍不可导出",
                      client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    codes = sorted({item["code"] for item in export.json().get("detail", {}).get("findings", [])})
    run.check("N2.5 导出拒绝原因含缺失许可证据",
              any(code.startswith("license_evidence") or code == "license_review_required" for code in codes),
              str(codes))
    return {"case": "缺失许可证证据", "rejected": response.status_code == 422,
            "rejected_at": "审核", "status_code": response.status_code,
            "detail": detail, "export_codes": codes}


def negative_bytes_changed(run: Run, pack: Path, text: str) -> dict[str, Any]:
    """负例 3：审核通过之后，磁盘上的素材字节被改动。"""
    client = run.client
    task_id, candidates = _new_task(run, text)
    chosen = candidates[0]
    staged = _stage_inputs(client, task_id, pack)
    attached = _attach(client, task_id, chosen, staged)
    v2 = attached.json()["candidate"]
    asset = v2["spec"]["asset_refs"][0]
    approved = run.step("N3.1 正常审核通过",
                        _approve(client, task_id, chosen["candidate_id"],
                                 v2["revision_id"], asset["asset_id"], staged))
    v3 = approved.json()["candidate"]
    run.check("N3.2 审核后状态为 approved",
              v3["spec"]["asset_refs"][0]["approval_status"] == "approved",
              v3["spec"]["asset_refs"][0]["approval_status"])

    client.post(f"/api/tasks/{task_id}/select-candidate",
                json={"candidate_id": chosen["candidate_id"], "revision_id": v3["revision_id"]})
    target = Path(staged["asset"])
    original = target.read_bytes()
    # 改一个描边宽度：文件仍是合法 SVG，仅字节不同，因此只有逐字节校验能发现。
    target.write_bytes(original.replace(b'stroke-width="1.5"', b'stroke-width="9.9"', 1))
    changed_sha = _sha256(target)
    run.check("N3.3 素材字节确实已改变（仍是合法 SVG）",
              changed_sha != EXPECTED_ASSET["sha256"], f"{changed_sha[:16]} != 原件")
    response = run.step("N3.4 批准后字节变化必须阻止导出",
                        client.post(f"/api/tasks/{task_id}/export", json={}), 409)
    codes = sorted({item["code"] for item in response.json().get("detail", {}).get("findings", [])})
    run.check("N3.5 拒绝原因是素材内容与批准时不一致",
              "content_identity_mismatch" in codes, str(codes))
    target.write_bytes(original)  # 还原，避免留下被篡改的素材
    run.check("N3.6 还原后素材恢复为上游原件",
              _sha256(target) == EXPECTED_ASSET["sha256"], _sha256(target)[:16])
    return {"case": "批准后素材字节被改动", "rejected": response.status_code == 409,
            "rejected_at": "导出", "status_code": response.status_code, "codes": codes,
            "tampered_sha256": changed_sha}


def run_acceptance(data_dir: Path, pack: Path, text: str = DEFAULT_TEXT,
                   verbose: bool = True) -> dict[str, Any]:
    """一正三负；每个负例独立数据目录，拒绝不会污染正例证据。"""
    from fastapi.testclient import TestClient

    from figure_agent.app.api import create_app

    assert_dir_is_safe(data_dir)
    run = Run(TestClient(create_app(data_dir=str(data_dir))), verbose=verbose)
    identity = verify_pack(run, pack)
    if verbose:
        print("\n--- 正例：登记 -> 审核 -> 引用 -> 正式导出 -> 重读 ZIP ---")
    positive = run_positive(run, pack, text, data_dir)

    negatives = []
    for index, (label, function) in enumerate((
            ("unreviewed", negative_unreviewed),
            ("missing-evidence", negative_missing_evidence),
            ("bytes-changed", negative_bytes_changed)), start=1):
        directory = data_dir.parent / f"{data_dir.name}-negative-{index}-{label}"
        assert_dir_is_safe(directory)
        if verbose:
            print(f"\n--- 负例 {index}：{label} ---")
        negative_run = Run(TestClient(create_app(data_dir=str(directory))), verbose=verbose)
        result = function(negative_run, pack, text)
        result["data_dir"] = str(directory)
        negatives.append(result)
        run.records.extend(negative_run.records)

    run.check("E1 三个负例全部被拒绝",
              len(negatives) == 3 and all(item["rejected"] for item in negatives),
              "; ".join(f"{item['case']}→{item['rejected_at']}({item['status_code']})" for item in negatives))

    return {"tested_commit": _describe_head(), "asset_pack": str(pack),
            "source_identity": identity, "positive": positive, "negatives": negatives,
            "assertions": run.records, "failures": run.failures, "all_ok": not run.failures}


def _describe_head() -> dict[str, str]:
    """记录受测提交，便于把结果钉回具体代码状态。"""
    import subprocess

    def _git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    return {"sha": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": _git("status", "--porcelain")[:400]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="outputs/D-asset-acceptance")
    parser.add_argument("--pack", default=DEFAULT_PACK, help="真实素材包目录")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--report", default=None, help="证据 JSON 写到这里")
    args = parser.parse_args(argv)

    data_dir, pack = Path(args.data_dir), Path(args.pack)
    if not (pack / "assets" / EXPECTED_ASSET["name"]).is_file():
        raise SystemExit(f"素材包不完整：{pack}")
    result = run_acceptance(data_dir, pack, text=args.text)
    report = Path(args.report) if args.report else data_dir / "asset-acceptance-evidence.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(result['assertions'])} 项断言，失败 {len(result['failures'])} 项: {result['failures']}")
    print(f"正式导出包: {result['positive']['official_package']}")
    print(f"证据: {report}")
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
