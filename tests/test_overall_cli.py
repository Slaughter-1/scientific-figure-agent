import json


def test_generate_cli_creates_contract_and_three_candidates(tmp_path):
    from figure_agent.cli import main

    source = tmp_path / "method.md"
    source.write_text("Query → Retriever → Generator", encoding="utf-8")
    output = tmp_path / "generated"
    assert main(["generate", "--input", str(source), "--output-dir", str(output)]) == 0
    assert (output / "figure-contract.json").exists()
    assert (output / "candidate_01" / "figure.svg").exists()
    assert len(json.loads((output / "candidates.json").read_text(encoding="utf-8"))) == 3


def test_search_templates_cli_returns_audited_records(capsys):
    from figure_agent.cli import main

    assert main(["search-templates", "--query", "architecture"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload and payload[0]["source_url"]


def test_analyze_cli_writes_figure_contract(tmp_path, capsys):
    from figure_agent.cli import main

    source = tmp_path / "method.md"
    source.write_text("Query → Retriever → Generator", encoding="utf-8")
    assert main(["analyze", "--input", str(source)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_figure_type"] == "workflow"


def test_package_and_inspect_cli_commands(tmp_path, capsys):
    from figure_agent.cli import main

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "planner", "label": "Planner", "type": "process"}],
        "edges": [], "groups": [], "style": {},
    }), encoding="utf-8")
    package_dir = tmp_path / "package"
    assert main(["package", "--spec", str(spec), "--output-dir", str(package_dir)]) == 0
    assert (package_dir / "component-manifest.json").exists()
    capsys.readouterr()
    svg = tmp_path / "figure.svg"
    svg.write_text('<svg width="100" height="80"><text>x</text></svg>', encoding="utf-8")
    assert main(["inspect", "--artifact", str(svg)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_push_figma_cli_creates_handoff_manifest(tmp_path, capsys):
    from figure_agent.cli import main

    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "schema_version": "0.1",
        "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "planner", "label": "Planner", "type": "process"}],
        "edges": [], "groups": [], "style": {},
    }), encoding="utf-8")
    output = tmp_path / "figma"
    assert main(["push-figma", "--spec", str(spec), "--output-dir", str(output)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unavailable"
    assert (output / "figure.figma-scene.json").exists()
    assert (output / "figma-manifest.json").exists()
