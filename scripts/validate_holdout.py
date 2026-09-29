"""Validate R2 independent-material intake without generating or scoring cases."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_DISTRIBUTION = {
    "sequence": 4,
    "branch": 4,
    "feedback": 4,
    "parallel_merge": 4,
    "containment": 2,
    "mixed": 2,
}
EXPECTED_FIELDS = {
    "task_id",
    "category",
    "source_text",
    "provenance",
    "owner",
    "independence_attestation",
}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class HoldoutValidationError(ValueError):
    """Raised when an intake file cannot be used as R2 material."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HoldoutValidationError(message)


def _read(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HoldoutValidationError(f"cannot read intake JSON: {exc}") from exc
    _require(isinstance(payload, dict), "top-level intake value must be an object")
    return payload


def _validate_common(payload: dict[str, Any]) -> None:
    _require(payload.get("round_id") == "R2", "round_id must be R2")
    _require(isinstance(payload.get("baseline_commit"), str) and COMMIT_RE.fullmatch(payload["baseline_commit"]), "baseline_commit must be a 40-character commit SHA")


def _validate_case(case: Any, index: int) -> None:
    _require(isinstance(case, dict), f"case {index} must be an object")
    _require(set(case) == EXPECTED_FIELDS, f"case {index} has unknown or missing fields")
    category = case["category"]
    _require(category in EXPECTED_DISTRIBUTION, f"case {index} has unsupported category: {category}")
    task_id = case["task_id"]
    _require(
        isinstance(task_id, str)
        and re.fullmatch(r"r2_(sequence|branch|feedback|parallel_merge|containment|mixed)_[0-9]{2}", task_id)
        and task_id.startswith(f"r2_{category}_"),
        f"case {index} task_id/category mismatch",
    )
    _require(isinstance(case["source_text"], str) and case["source_text"].strip(), f"case {index} source_text is empty")

    provenance = case["provenance"]
    _require(isinstance(provenance, dict), f"case {index} provenance must be an object")
    _require(
        set(provenance) == {"source_kind", "source_reference", "selection_rule"}
        and all(isinstance(provenance[field], str) and provenance[field].strip() for field in provenance),
        f"case {index} provenance is incomplete",
    )

    owner = case["owner"]
    _require(isinstance(owner, dict), f"case {index} owner must be an object")
    _require(
        set(owner) == {"name_or_id", "role", "not_involved_in_debugging"}
        and isinstance(owner["name_or_id"], str)
        and bool(owner["name_or_id"].strip())
        and isinstance(owner["role"], str)
        and bool(owner["role"].strip())
        and owner["not_involved_in_debugging"] is True,
        f"case {index} owner independence is incomplete",
    )

    attestation = case["independence_attestation"]
    _require(isinstance(attestation, dict), f"case {index} independence_attestation must be an object")
    _require(
        set(attestation) == {"attested_by", "attested_at", "statement"}
        and all(isinstance(attestation[field], str) and attestation[field].strip() for field in attestation),
        f"case {index} independence_attestation is incomplete",
    )


def validate_holdout(path: str | Path, *, require_complete: bool = False) -> dict[str, Any]:
    """Validate pending intake or a complete 20-case R2 material file."""
    payload = _read(path)
    _validate_common(payload)
    status = payload.get("status")
    cases = payload.get("cases")
    _require(isinstance(cases, list), "cases must be an array")
    if status == "pending_independent_material":
        _require(not cases, "pending intake must have an empty cases array")
        if require_complete:
            raise HoldoutValidationError("20 cases are required before generation")
        return {"status": status, "case_count": 0, "category_counts": {}}

    _require(status == "ready", "status must be ready or pending_independent_material")
    _require(len(cases) == 20, f"20 cases are required, found {len(cases)}")
    for index, case in enumerate(cases, 1):
        _validate_case(case, index)
    task_ids = [case["task_id"] for case in cases]
    _require(len(set(task_ids)) == len(task_ids), "task_id values must be unique")
    counts = dict(Counter(case["category"] for case in cases))
    _require(counts == EXPECTED_DISTRIBUTION, f"category distribution is not {EXPECTED_DISTRIBUTION}: {counts}")
    return {"status": status, "case_count": len(cases), "category_counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate R2 independent material intake; never generate or score.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--require-complete", action="store_true", help="reject the pending empty template")
    args = parser.parse_args()
    try:
        result = validate_holdout(args.path, require_complete=args.require_complete)
    except HoldoutValidationError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
