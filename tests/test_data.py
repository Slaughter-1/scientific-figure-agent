import json


def test_load_csv_preserves_columns_rows_and_provenance(tmp_path):
    from figure_agent.data import load_table

    path = tmp_path / "结果.csv"
    path.write_text("\ufeff方法,准确率\n基线,0.71\n我们的模型,0.83\n", encoding="utf-8-sig")
    table = load_table(path)
    assert table["columns"] == ["方法", "准确率"]
    assert table["rows"][1]["准确率"] == "0.83"
    assert table["provenance"]["format"] == "csv"


def test_load_json_records_returns_same_table_shape(tmp_path):
    from figure_agent.data import load_table

    path = tmp_path / "results.json"
    path.write_text(json.dumps([{"method": "A", "score": 1}]), encoding="utf-8")
    table = load_table(path)
    assert table["columns"] == ["method", "score"]
    assert table["rows"] == [{"method": "A", "score": 1}]
    assert table["provenance"]["format"] == "json"


def test_load_json_requires_records_array(tmp_path):
    import pytest

    from figure_agent.data import load_table

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"results": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="records"):
        load_table(path)
