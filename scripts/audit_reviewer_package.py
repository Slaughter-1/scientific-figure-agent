"""Audit a frozen reviewer package before independent delivery.

This is a preflight gate for an already-created package. It does not generate
figures, rewrite files, or evaluate scores.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path
from typing import Any
import zlib


EXPECTED_WIDTHS = ("single_column", "double_column")
RUBRIC = (
    "semantic_correct",
    "no_overlap_or_clipping",
    "text_readability",
    "arrow_clarity",
    "information_hierarchy",
    "paper_aesthetics",
)
ALLOWED_ROW_KEYS = frozenset(
    {"blind_id", "paper_width", *RUBRIC, "hard_failures", "notes", "reviewer", "reviewed_at"}
)
TEXT_EXTENSIONS = {".json", ".html", ".csv"}
LEAK_PATTERNS = (
    re.compile(r"\bcase[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\bcandidate[_ -]?id\b", re.IGNORECASE),
    re.compile(r"\brevision(?:[_ -]?id)?\b", re.IGNORECASE),
    re.compile(r"\brecommend(?:ation)?\b", re.IGNORECASE),
    re.compile(r"\bheuristic(?:[_ -]?score)?\b", re.IGNORECASE),
    re.compile(r"\bspec[_ -]?sha256\b", re.IGNORECASE),
    re.compile(r"\b(?:auto[_ -]?)?scores?\b", re.IGNORECASE),
    re.compile(r"\bcandidate[_ -]?[0-9]{1,3}\b", re.IGNORECASE),
)
ALLOWED_FILES = {"blank-scores.json", "index.html"}


class ReviewerPackageAuditError(ValueError):
    """Raised when a reviewer package violates the delivery contract."""


def _raise(message: str) -> None:
    raise ReviewerPackageAuditError(message)


def _leaks(value: str) -> list[str]:
    return [pattern.pattern for pattern in LEAK_PATTERNS if pattern.search(value)]


def _audit_relative_path(relative: Path) -> None:
    normalized = relative.as_posix()
    if normalized in ALLOWED_FILES:
        return
    if relative.parent.as_posix() == "images" and re.fullmatch(r"B[0-9]{3}\.png", relative.name):
        return
    _raise(f"path is not blind-safe: {normalized}")


def _png_text_chunks(path: Path) -> list[str]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        _raise(f"invalid PNG signature: {path.name}")
    offset = 8
    texts: list[str] = []
    while offset < len(data):
        if offset + 12 > len(data):
            _raise(f"truncated PNG chunk: {path.name}")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            _raise(f"truncated PNG data: {path.name}")
        payload = data[start:end]
        if kind == b"tEXt":
            texts.append(payload.decode("latin-1", errors="replace"))
        elif kind == b"zTXt":
            separator = payload.find(b"\x00")
            if separator >= 0 and separator + 2 <= len(payload) and payload[separator + 1] == 0:
                try:
                    texts.append(payload[:separator].decode("latin-1") + "\x00" + zlib.decompress(payload[separator + 2 :]).decode("utf-8", errors="replace"))
                except zlib.error:
                    _raise(f"invalid PNG zTXt metadata: {path.name}")
        elif kind == b"iTXt":
            texts.append(payload.decode("utf-8", errors="replace"))
        elif kind == b"eXIf":
            texts.append(payload.decode("latin-1", errors="replace"))
        offset = end + 4
        if kind == b"IEND":
            break
    return texts


def _load_rows(reviewer: Path) -> list[dict[str, Any]]:
    path = reviewer / "blank-scores.json"
    if not path.is_file():
        _raise("missing reviewer/blank-scores.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _raise(f"cannot read blank-scores.json: {exc}")
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or payload.get("row_count") != len(rows):
        _raise("blank-scores row_count does not match rows")
    if len(rows) != 120:
        _raise(f"expected 120 blank rows, found {len(rows)}")
    expected_ids = {f"B{index:03d}" for index in range(1, 121)}
    actual_ids = {row.get("blind_id") for row in rows if isinstance(row, dict)}
    if actual_ids != expected_ids or len(actual_ids) != len(rows):
        _raise("blind_id set is missing, duplicated, or outside B001-B120")
    if any(not isinstance(row, dict) or set(row) != ALLOWED_ROW_KEYS for row in rows):
        _raise("blank row contains an unknown or identity-bearing field")
    if any(
        any(row.get(metric) is not None for metric in RUBRIC)
        or row.get("hard_failures")
        or row.get("notes")
        or row.get("reviewer")
        or row.get("reviewed_at")
        for row in rows
    ):
        _raise("reviewer package is not blank")
    width_counts = {width: sum(row.get("paper_width") == width for row in rows) for width in EXPECTED_WIDTHS}
    if any(count != 60 for count in width_counts.values()) or sum(width_counts.values()) != len(rows):
        _raise(f"paper_width set is incomplete: {width_counts}")
    return rows


def audit_reviewer_package(reviewer_dir: str | Path) -> dict[str, Any]:
    """Validate paths, textual content, PNG metadata, and blank row coverage."""
    reviewer = Path(reviewer_dir)
    if not reviewer.is_dir():
        _raise(f"reviewer directory not found: {reviewer}")
    rows = _load_rows(reviewer)
    paths = [path for path in reviewer.rglob("*") if path.is_file()]
    for path in paths:
        relative = path.relative_to(reviewer)
        _audit_relative_path(relative)
        if path.suffix.lower() in TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="replace")
            leaked = _leaks(text)
            if leaked:
                _raise(f"text leakage in {relative.as_posix()}: {leaked}")
        if path.suffix.lower() == ".png":
            for metadata in _png_text_chunks(path):
                leaked = _leaks(metadata)
                if leaked:
                    _raise(f"PNG metadata leakage in {relative.as_posix()}: {leaked}")
    expected_images = {Path("images") / f"B{index:03d}.png" for index in range(1, 121)}
    actual_images = {path.relative_to(reviewer) for path in paths if path.suffix.lower() == ".png"}
    if actual_images != expected_images:
        _raise("image set does not exactly match B001.png-B120.png")
    return {
        "reviewer_dir": reviewer.as_posix(),
        "row_count": len(rows),
        "width_counts": {width: sum(row["paper_width"] == width for row in rows) for width in EXPECTED_WIDTHS},
        "image_count": len(actual_images),
        "text_files_scanned": sum(path.suffix.lower() in TEXT_EXTENSIONS for path in paths),
        "png_metadata_scanned": len(actual_images),
        "blind": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a reviewer package without generating or scoring it.")
    parser.add_argument("reviewer_dir", type=Path)
    args = parser.parse_args()
    try:
        result = audit_reviewer_package(args.reviewer_dir)
    except ReviewerPackageAuditError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
