def test_inspect_svg_reports_text_and_dimensions(tmp_path):
    from figure_agent.inspect import inspect_artifact

    path = tmp_path / "figure.svg"
    path.write_text('<svg width="320" height="180"><text>A</text></svg>', encoding="utf-8")
    result = inspect_artifact(path)
    assert result["status"] == "ok"
    assert result["format"] == "svg"
    assert result["text_nodes"] == 1
    assert result["width"] == 320
