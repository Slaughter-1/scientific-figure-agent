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
