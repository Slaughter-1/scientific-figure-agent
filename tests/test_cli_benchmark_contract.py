from __future__ import annotations

import json
from pathlib import Path

from figure_agent import cli


def test_generate_benchmark_accepts_r2_envelope(tmp_path, monkeypatch):
    cases_path = tmp_path / "holdout.json"
    cases_path.write_text(
        json.dumps(
            {
                "status": "ready",
                "cases": [
                    {
                        "task_id": "r2_sequence_01",
                        "category": "sequence",
                        "source_text": "A then B.",
                        "provenance": {"source_kind": "new"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_generate(cases, output_dir, *, paper_widths):
        captured.update(cases=cases, output_dir=output_dir, paper_widths=paper_widths)
        return Path(output_dir)

    monkeypatch.setattr(cli, "generate_benchmark", fake_generate)
    assert cli.main(["generate-benchmark", "--cases", str(cases_path), "--output-dir", str(tmp_path / "out")]) == 0
    assert captured["cases"] == [{"id": "r2_sequence_01", "category": "sequence", "text": "A then B."}]
    assert captured["paper_widths"] == ("single_column", "double_column")


def test_generate_benchmark_preserves_legacy_flat_contract(tmp_path, monkeypatch):
    cases_path = tmp_path / "legacy.json"
    cases_path.write_text(json.dumps([{"id": "legacy-1", "category": "branch", "text": "A or B."}]), encoding="utf-8")
    captured = {}

    def fake_generate(cases, output_dir, *, paper_widths):
        captured["cases"] = cases
        return Path(output_dir)

    monkeypatch.setattr(cli, "generate_benchmark", fake_generate)
    assert cli.main(["generate-benchmark", "--cases", str(cases_path), "--output-dir", str(tmp_path / "out"), "--paper-widths", "single_column"]) == 0
    assert captured["cases"] == [{"id": "legacy-1", "category": "branch", "text": "A or B."}]


def test_cli_module_exposes_main_entrypoint():
    assert callable(cli.main)
