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

REVIEW_STATES = ("clean", "needs_review", "failed")


def _needs_review_codes(payload: dict[str, Any]) -> list[str]:
    """Read ``needs_review`` codes without inventing findings the pipeline did not report."""
    items = payload.get("needs_review", [])
    if not isinstance(items, list):
        return []
    return [str(item["code"]) for item in items if isinstance(item, dict) and item.get("code")]


def summarize_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    """Partition a benchmark run into clean / needs-review / failed generations.

    Fail-closed: a missing, duplicated or unrecognised record makes the whole run
    incomplete instead of silently shrinking the denominator.
    """
    records = payload.get("records", [])
    case_ids = [record.get("case_id") for record in records]
    counts = {state: 0 for state in REVIEW_STATES}
    by_code: dict[str, int] = {}
    recognised = True
    for record in records:
        state = record.get("review_state")
        if state in counts:
            counts[state] += 1
        else:
            recognised = False
        for code in record.get("needs_review_codes") or []:
            by_code[str(code)] = by_code.get(str(code), 0) + 1
    accounted = sum(counts.values())
    complete = bool(records and recognised and all(case_ids) and len(set(case_ids)) == len(case_ids)
                    and accounted == len(records) and len(records) == payload.get("case_count"))
    return {
        "case_count": payload.get("case_count"), "record_count": len(records), "accounted_cases": accounted,
        "generated_clean": counts["clean"], "generated_with_needs_review": counts["needs_review"], "failed": counts["failed"],
        "needs_review_by_code": dict(sorted(by_code.items())), "complete": complete,
    }


def generate_benchmark(cases: list[dict[str, Any]], output: str | Path, *, paper_widths: tuple[str, ...] = ("single_column", "double_column")) -> Path:
    """Generate candidates for every independent case while preserving failures.

    Every requested column width is generated separately into its own directory,
    so a review round has one real artifact set per width instead of a single
    figure rescaled at display time.

    Review accounting is deliberately unchanged: column width is a rendering
    constraint, not a semantic one, so ``needs_review`` codes are counted once
    per case from a representative width rather than once per width. Counting
    them per width would inflate the reported totals without new findings.
    """
    from .candidates import PAPER_WIDTH_MM
    from .workflow import generate_from_text

    if not paper_widths:
        raise ValueError("paper_widths must name at least one column width")
    unsupported = [width for width in paper_widths if width not in PAPER_WIDTH_MM]
    if unsupported:
        raise ValueError(f"unsupported paper_width(s): {unsupported}; expected from {sorted(PAPER_WIDTH_MM)}")

    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for case in cases:
        case_dir = root / case["id"]
        try:
            by_width: dict[str, dict[str, Any]] = {}
            for width in paper_widths:
                by_width[width] = generate_from_text(case["text"], case_dir / width, count=3, paper_width=width)
            result = by_width[paper_widths[0]]
            widths = {
                width: {
                    "paper_width": width, "paper_width_mm": PAPER_WIDTH_MM[width], "candidate_dir": str(case_dir / width),
                    "candidates": [{"candidate_id": item.get("candidate_id"), "revision_id": item.get("revision_id"), "artifacts": item.get("artifacts", {})} for item in payload.get("candidates", [])],
                }
                for width, payload in by_width.items()
            }
            candidates = []
            for candidate in result.get("candidates", []):
                codes = _needs_review_codes(candidate.get("spec", {}))
                for finding in candidate.get("review_findings", []) or []:
                    if isinstance(finding, dict) and finding.get("code"):
                        codes.append(str(finding["code"]))
                codes = sorted(set(codes))
                candidates.append({"candidate_id": candidate.get("candidate_id"), "revision_id": candidate.get("revision_id"), "review_state": "needs_review" if codes else "clean", "needs_review_count": len(codes), "needs_review_codes": codes})
            contract_codes = _needs_review_codes(result.get("contract", {}))
            all_codes = sorted({*contract_codes, *(code for item in candidates for code in item["needs_review_codes"])})
            total = len(contract_codes) + sum(item["needs_review_count"] for item in candidates)
            records.append({"case_id": case["id"], "status": "generated", "candidate_count": len(result["candidates"]), "candidate_dir": str(case_dir), "review_state": "needs_review" if all_codes else "clean", "needs_review_count": total, "needs_review_codes": all_codes, "contract_needs_review_codes": contract_codes, "candidates": candidates, "paper_widths": list(paper_widths), "widths": widths})
        except Exception as exc:
            (case_dir / "generation-error.json").parent.mkdir(parents=True, exist_ok=True)
            (case_dir / "generation-error.json").write_text(json.dumps({"case_id": case["id"], "error": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append({"case_id": case["id"], "status": "failed", "error": str(exc), "candidate_dir": str(case_dir), "review_state": "failed", "needs_review_count": 0, "needs_review_codes": [], "contract_needs_review_codes": [], "candidates": [], "paper_widths": list(paper_widths), "widths": {}})
    payload = {"case_count": len(cases), "paper_widths": list(paper_widths), "records": records}
    payload["summary"] = summarize_benchmark(payload)
    index = root / "benchmark-run.json"
    index.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index
