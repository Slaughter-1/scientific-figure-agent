def test_render_bar_chart_writes_vector_and_preview_files(tmp_path):
    from figure_agent.backends.plot_backend import render_bar_chart

    outputs = render_bar_chart(
        {"methods": ["Baseline", "Ours"], "accuracy": [0.71, 0.83]},
        tmp_path,
        "benchmark",
    )
    assert outputs["pdf"].exists()
    assert outputs["svg"].exists()
    assert outputs["png"].exists()


def test_render_plot_spec_supports_line_scatter_and_heatmap(tmp_path):
    from figure_agent.backends.plot_backend import render_plot_spec

    common = {"schema_version": "0.1", "figure_type": "plot", "layout": {"direction": "left-to-right"}, "nodes": [], "edges": [], "groups": [], "style": {}}
    for kind, data in (
        ("line", {"kind": "line", "x": [1, 2, 3], "y": [0.2, 0.4, 0.35]}),
        ("scatter", {"kind": "scatter", "x": [1, 2, 3], "y": [0.2, 0.4, 0.35]}),
        ("heatmap", {"kind": "heatmap", "matrix": [[0.1, 0.2], [0.3, 0.4]]}),
    ):
        spec = {**common, "data": data}
        outputs = render_plot_spec(spec, tmp_path, kind)
        assert all(path.exists() and path.stat().st_size > 0 for path in outputs.values())
