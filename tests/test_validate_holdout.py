import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "validate_holdout", ROOT / "scripts" / "validate_holdout.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _complete_cases(module):
    distribution = {
        "sequence": 4,
        "branch": 4,
        "feedback": 4,
        "parallel_merge": 4,
        "containment": 2,
        "mixed": 2,
    }
    cases = []
    for category, count in distribution.items():
        for index in range(1, count + 1):
            cases.append(
                {
                    "task_id": f"r2_{category}_{index:02d}",
                    "category": category,
                    "source_text": f"independent text {category} {index}",
                    "provenance": {
                        "source_kind": "independent_fixture",
                        "source_reference": f"source-{category}-{index}",
                        "selection_rule": "new material after semantic freeze",
                    },
                    "owner": {
                        "name_or_id": "independent-owner",
                        "role": "material custodian",
                        "not_involved_in_debugging": True,
                    },
                    "independence_attestation": {
                        "attested_by": "independent-owner",
                        "attested_at": "2026-09-26T00:00:00Z",
                        "statement": "Not involved in parser, route, or score debugging.",
                    },
                }
            )
    return {
        "round_id": "R2",
        "baseline_commit": "2d9e900fb9a7a7e827c1adbd0eff00c8a5cbb989",
        "status": "ready",
        "cases": cases,
    }


def test_pending_template_is_explicitly_accepted(tmp_path):
    module = _module()
    path = tmp_path / "r2_holdout_input.json"
    path.write_text(
        json.dumps(
            {
                "round_id": "R2",
                "baseline_commit": "2d9e900fb9a7a7e827c1adbd0eff00c8a5cbb989",
                "status": "pending_independent_material",
                "cases": [],
            }
        ),
        encoding="utf-8",
    )
    assert module.validate_holdout(path)["status"] == "pending_independent_material"
    with pytest.raises(module.HoldoutValidationError, match="20 cases"):
        module.validate_holdout(path, require_complete=True)


def test_complete_material_is_checked_for_distribution_and_provenance(tmp_path):
    module = _module()
    path = tmp_path / "r2_holdout_input.json"
    path.write_text(json.dumps(_complete_cases(module)), encoding="utf-8")
    result = module.validate_holdout(path, require_complete=True)
    assert result["status"] == "ready"
    assert result["case_count"] == 20
    assert result["category_counts"]["parallel_merge"] == 4


def test_wrong_distribution_is_rejected(tmp_path):
    module = _module()
    payload = _complete_cases(module)
    payload["cases"][-1]["category"] = "sequence"
    payload["cases"][-1]["task_id"] = "r2_sequence_05"
    path = tmp_path / "r2_holdout_input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.HoldoutValidationError, match="distribution"):
        module.validate_holdout(path, require_complete=True)
