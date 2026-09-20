import json


def test_plot_cli_generates_spec_artifacts_and_manifest(tmp_path):
    from figure_agent.cli import main

    source = tmp_path / "results.csv"
    source.write_text("method,accuracy\nBaseline,0.71\nOurs,0.83\n", encoding="utf-8")
    output = tmp_path / "output"
    code = main([
        "plot", "--input", str(source), "--kind", "bar", "--x", "method", "--y", "accuracy",
        "--output-dir", str(output), "--title", "Accuracy",
    ])
    assert code == 0
    assert (output / "plot-spec.json").exists()
    assert (output / "figure.pdf").exists()
    assert (output / "figure.svg").exists()
    assert (output / "figure.png").exists()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["matplotlib"]["status"] == "ok"


def test_plot_cli_missing_column_returns_nonzero_and_explains_column(tmp_path, capsys):
    from figure_agent.cli import main

    source = tmp_path / "results.csv"
    source.write_text("method,accuracy\nBaseline,0.71\n", encoding="utf-8")
    code = main([
        "plot", "--input", str(source), "--kind", "bar", "--x", "missing", "--y", "accuracy",
        "--output-dir", str(tmp_path / "output"),
    ])
    assert code == 2
    assert "missing" in capsys.readouterr().err
