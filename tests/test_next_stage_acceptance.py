import json
from pathlib import Path


def test_render_all_creates_local_artifacts_and_manifest(tmp_path):
    from figure_agent.cli import main

    code = main(["render", "--spec", "examples/m0/workflow.json", "--backend", "all", "--output-dir", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "figure.drawio").exists()
    assert (tmp_path / "figure.figma-scene.json").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["spec_sha256"]
    assert manifest["artifacts"]["figma"]["status"] == "unavailable"


def test_render_unknown_backend_returns_partial_failure(tmp_path):
    from figure_agent.cli import main

    code = main(["render", "--spec", "examples/m0/workflow.json", "--backend", "unknown", "--output-dir", str(tmp_path)])
    assert code == 2
    assert (tmp_path / "manifest.json").exists()
