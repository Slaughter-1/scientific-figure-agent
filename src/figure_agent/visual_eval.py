from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


RUBRIC = ["semantic_correct", "no_overlap_or_clipping", "text_readability", "arrow_clarity", "information_hierarchy", "paper_aesthetics"]
HARD_FAILURES = ["semantic_error", "missing_relation", "wrong_direction", "overlap", "clipping", "unreadable_text", "edge_cross_node", "missing_condition"]


def build_review_sheet(cases: list[dict[str, Any]], output: str | Path) -> Path:
    """Create a blank, independent human-review sheet for 20 cases × 3 candidates × 2 sizes."""
    rows = []
    for case in cases:
        for candidate_id in ("candidate_01", "candidate_02", "candidate_03"):
            for paper_width in ("single_column", "double_column"):
                rows.append({"case_id": case["id"], "category": case["category"], "candidate_id": candidate_id, "paper_width": paper_width, **{item: None for item in RUBRIC}, "hard_failures": [], "notes": ""})
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rubric": RUBRIC, "hard_failure_codes": HARD_FAILURES, "row_count": len(rows), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def summarize_reviews(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows", [])
    def valid(row):
        return all(type(row.get(item)) in (int, float) and math.isfinite(row[item]) and 1 <= row[item] <= 5 for item in RUBRIC) and bool(row.get("reviewer")) and bool(row.get("reviewed_at")) and isinstance(row.get("hard_failures"), list) and all(code in HARD_FAILURES for code in row["hard_failures"])
    scored = [row for row in rows if valid(row)]
    failures = sum(bool(row.get("hard_failures")) for row in rows)
    ids = [row.get("blind_id", (row.get("case_id"), row.get("candidate_id"), row.get("paper_width"))) for row in rows]
    by_width = {}
    for width in ("single_column", "double_column"):
        subset = [row for row in rows if row.get("paper_width") == width]
        complete = [row for row in subset if valid(row)]
        averages = {metric: sum(row[metric] for row in complete) / len(complete) if complete else None for metric in RUBRIC}
        ready = bool(subset and len(complete) == len(subset) and not any(row["hard_failures"] for row in subset) and averages["text_readability"] >= 4.5 and averages["arrow_clarity"] >= 4.3 and averages["paper_aesthetics"] >= 4.0)
        by_width[width] = {"row_count": len(subset), "scored_count": len(complete), "means": averages, "mean_readability": averages["text_readability"], "pass": ready}
    complete = len(rows) == payload.get("row_count") and len(set(ids)) == len(ids) and len(scored) == len(rows) and all(row.get("paper_width") in by_width for row in rows)
    return {"row_count": len(rows), "scored_count": len(scored), "hard_failure_rows": failures, "by_paper_width": by_width, "release_ready": bool(complete and all(result["pass"] for result in by_width.values()))}


def generate_benchmark(cases: list[dict[str, Any]], output: str | Path) -> Path:
    """Generate candidates for every independent case while preserving failures."""
    from .workflow import generate_from_text

    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for case in cases:
        case_dir = root / case["id"]
        try:
            result = generate_from_text(case["text"], case_dir, count=3)
            records.append({"case_id": case["id"], "status": "generated", "candidate_count": len(result["candidates"]), "candidate_dir": str(case_dir)})
        except Exception as exc:
            (case_dir / "generation-error.json").parent.mkdir(parents=True, exist_ok=True)
            (case_dir / "generation-error.json").write_text(json.dumps({"case_id": case["id"], "error": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append({"case_id": case["id"], "status": "failed", "error": str(exc), "candidate_dir": str(case_dir)})
    index = root / "benchmark-run.json"
    index.write_text(json.dumps({"case_count": len(cases), "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    return index
