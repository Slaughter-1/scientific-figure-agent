import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_reviewer_package", ROOT / "scripts" / "audit_reviewer_package.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png(*, text=None):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    chunks = [chunk(b"IHDR", ihdr)]
    if text is not None:
        chunks.append(chunk(b"tEXt", b"Comment\0" + text.encode("utf-8")))
    chunks.append(chunk(b"IEND", b""))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _blank_package(tmp_path, *, png_text=None):
    reviewer = tmp_path / "reviewer"
    images = reviewer / "images"
    images.mkdir(parents=True)
    metrics = [
        "semantic_correct",
        "no_overlap_or_clipping",
        "text_readability",
        "arrow_clarity",
        "information_hierarchy",
        "paper_aesthetics",
    ]
    rows = []
    for index in range(1, 121):
        width = "single_column" if index <= 60 else "double_column"
        rows.append(
            {
                "blind_id": f"B{index:03d}",
                "paper_width": width,
                **{metric: None for metric in metrics},
                "hard_failures": [],
                "notes": "",
                "reviewer": "",
                "reviewed_at": "",
            }
        )
        (images / f"B{index:03d}.png").write_bytes(_png(text=png_text))
    (reviewer / "blank-scores.json").write_text(
        json.dumps({"row_count": 120, "rows": rows}), encoding="utf-8"
    )
    (reviewer / "index.html").write_text("<h1>匿名评审</h1>", encoding="utf-8")
    return reviewer


def test_audit_accepts_complete_blank_package(tmp_path):
    module = _audit_module()
    result = module.audit_reviewer_package(_blank_package(tmp_path))
    assert result["row_count"] == 120
    assert result["width_counts"] == {"single_column": 60, "double_column": 60}


def test_audit_rejects_identity_in_filename(tmp_path):
    module = _audit_module()
    reviewer = _blank_package(tmp_path)
    (reviewer / "images" / "B001.png").rename(reviewer / "images" / "candidate_01.png")
    with pytest.raises(module.ReviewerPackageAuditError, match="path"):
        module.audit_reviewer_package(reviewer)


def test_audit_rejects_png_text_metadata_leak(tmp_path):
    module = _audit_module()
    reviewer = _blank_package(tmp_path, png_text="candidate_id=candidate_01")
    with pytest.raises(module.ReviewerPackageAuditError, match="PNG metadata"):
        module.audit_reviewer_package(reviewer)


def test_audit_rejects_incomplete_or_duplicate_blind_ids(tmp_path):
    module = _audit_module()
    reviewer = _blank_package(tmp_path)
    path = reviewer / "blank-scores.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rows"][-1]["blind_id"] = payload["rows"][-2]["blind_id"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.ReviewerPackageAuditError, match="blind_id"):
        module.audit_reviewer_package(reviewer)
