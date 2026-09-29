import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _freeze_module():
    spec = importlib.util.spec_from_file_location("freeze_visual", ROOT / "scripts/freeze_visual_rc1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blinding_check_rejects_case_and_candidate_identity(tmp_path):
    module = _freeze_module()
    (tmp_path / "blank-scores.json").write_text(json.dumps({"rows": [{"blind_id": "B001", "case_id": "pipeline_01"}]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        module.assert_reviewer_package_is_blind(tmp_path)


def test_blinding_check_rejects_machine_scores_and_recommendations(tmp_path):
    module = _freeze_module()
    (tmp_path / "index.html").write_text('<p>scores: 0.82 recommend candidate_01</p>', encoding="utf-8")
    with pytest.raises(SystemExit):
        module.assert_reviewer_package_is_blind(tmp_path)


def test_blinding_check_accepts_a_blind_id_only_package(tmp_path):
    module = _freeze_module()
    (tmp_path / "blank-scores.json").write_text(json.dumps({"row_count": 1, "rows": [{"blind_id": "B001", "paper_width": "single_column", "text_readability": None, "hard_failures": [], "reviewer": "", "reviewed_at": ""}]}), encoding="utf-8")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "B001.png").write_bytes(b"\x89PNG\r\n")
    module.assert_reviewer_package_is_blind(tmp_path)


def test_freeze_round_id_and_seed_are_parameters_not_constants():
    module = _freeze_module()
    signature = __import__("inspect").signature(module.main)
    assert {"round_id", "seed"} <= set(signature.parameters)
    assert signature.parameters["round_id"].default == "rc1"
    assert signature.parameters["seed"].default == 20260921


def test_freeze_inputs_and_widths_are_parameters_not_constants():
    """The frozen round's case/input paths and widths must be selectable."""
    module = _freeze_module()
    signature = __import__("inspect").signature(module.main)
    assert {"source", "cases_path", "widths"} <= set(signature.parameters)
    assert signature.parameters["widths"].default == ("single_column", "double_column")
    assert signature.parameters["source"].default is None
    assert signature.parameters["cases_path"].default is None


def test_freeze_normalizes_validated_s5_cases_envelope():
    module = _freeze_module()
    cases = module.normalize_cases({"status": "ready", "cases": [{
        "task_id": "r2_sequence_01",
        "source_text": "独立任务文本",
        "category": "sequence",
    }]})
    assert cases == [{
        "task_id": "r2_sequence_01",
        "source_text": "独立任务文本",
        "category": "sequence",
        "id": "r2_sequence_01",
        "text": "独立任务文本",
    }]


def test_freeze_refuses_to_overwrite_an_existing_frozen_round(tmp_path, monkeypatch):
    module = _freeze_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "outputs/visual-benchmark-r2").mkdir(parents=True)
    with pytest.raises(SystemExit) as error:
        module.main(round_id="r2")
    assert "already exists" in str(error.value)


def test_strict_thresholds_are_unchanged():
    from figure_agent import visual_eval

    source = Path(visual_eval.__file__).read_text(encoding="utf-8")
    assert 'averages["text_readability"] >= 4.5' in source
    assert 'averages["arrow_clarity"] >= 4.3' in source
    assert 'averages["paper_aesthetics"] >= 4.0' in source
