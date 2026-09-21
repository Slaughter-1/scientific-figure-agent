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


def test_build_bar_spec_accepts_error_column():
    from figure_agent.plot_planner import build_plot_spec

    table = {"columns": ["method", "accuracy", "std"], "rows": [
        {"method": "Baseline", "accuracy": "0.71", "std": "0.03"},
        {"method": "Ours", "accuracy": "0.83", "std": "0.02"},
    ]}
    spec = build_plot_spec(table, kind="bar", x_column="method", y_column="accuracy", y_error_column="std")
    assert spec["data"]["y_error"] == [0.03, 0.02]


def test_render_plot_spec_writes_errorbar_artifacts(tmp_path):
    from figure_agent.backends.plot_backend import render_plot_spec
    from figure_agent.plot_planner import build_plot_spec

    table = {"columns": ["method", "accuracy", "std"], "rows": [
        {"method": "Baseline", "accuracy": "0.71", "std": "0.03"},
        {"method": "Ours", "accuracy": "0.83", "std": "0.02"},
    ]}
    spec = build_plot_spec(table, kind="bar", x_column="method", y_column="accuracy", y_error_column="std")
    artifacts = render_plot_spec(spec, tmp_path)
    assert all(path.exists() for path in artifacts.values())


def test_build_plot_spec_supports_multiple_y_columns():
    from figure_agent.plot_planner import build_plot_spec

    spec = build_plot_spec(_table(), kind="line", x_column="method", y_column="accuracy,recall")
    assert [item["name"] for item in spec["data"]["series"]] == ["accuracy", "recall"]
    assert spec["data"]["series"][1]["y"] == [0.60, 0.79]
    assert spec["data"]["source_columns"] == ["method", "accuracy", "recall"]


def test_build_plot_spec_records_labels_and_significance():
    from figure_agent.plot_planner import build_plot_spec

    table = {"columns": ["method", "accuracy", "sig"], "rows": [
        {"method": "Baseline", "accuracy": "0.71", "sig": ""},
        {"method": "Ours", "accuracy": "0.83", "sig": "**"},
    ]}
    spec = build_plot_spec(table, kind="bar", x_column="method", y_column="accuracy", significance_column="sig", y_label="Accuracy (%)")
    assert spec["data"]["significance"] == ["", "**"]
    assert spec["data"]["y_label"] == "Accuracy (%)"
