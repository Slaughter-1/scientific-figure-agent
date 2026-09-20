import pytest


def _table():
    return {
        "columns": ["method", "accuracy", "recall"],
        "rows": [
            {"method": "Baseline", "accuracy": "0.71", "recall": "0.60"},
            {"method": "Ours", "accuracy": "0.83", "recall": "0.79"},
        ],
        "provenance": {"source": "results.csv", "format": "csv"},
    }


def test_build_bar_spec_maps_columns_and_preserves_provenance():
    from figure_agent.plot_planner import build_plot_spec

    spec = build_plot_spec(_table(), kind="bar", x_column="method", y_column="accuracy", title="Accuracy")
    assert spec["figure_type"] == "plot"
    assert spec["data"]["x"] == ["Baseline", "Ours"]
    assert spec["data"]["y"] == [0.71, 0.83]
    assert spec["data"]["source_columns"] == ["method", "accuracy"]
    assert spec["provenance"]["source"] == "results.csv"


def test_build_line_spec_rejects_missing_column_with_name():
    from figure_agent.plot_planner import build_plot_spec

    with pytest.raises(ValueError, match="missing"):
        build_plot_spec(_table(), kind="line", x_column="method", y_column="missing")


def test_build_heatmap_requires_rectangular_numeric_matrix():
    from figure_agent.plot_planner import build_plot_spec

    spec = build_plot_spec(_table(), kind="heatmap", matrix_columns=["accuracy", "recall"])
    assert spec["data"]["matrix"] == [[0.71, 0.60], [0.83, 0.79]]
    bad = {**_table(), "rows": [{"accuracy": "x", "recall": "0.5"}]}
    with pytest.raises(ValueError, match="row 1"):
        build_plot_spec(bad, kind="heatmap", matrix_columns=["accuracy", "recall"])
