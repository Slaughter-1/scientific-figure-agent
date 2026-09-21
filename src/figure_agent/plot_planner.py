from __future__ import annotations

from typing import Any

from .spec import require_valid_spec


_KINDS = {"bar", "line", "scatter", "heatmap"}


def _number(value: Any, column: str, row_number: int) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"column '{column}' has an empty value at row {row_number}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"column '{column}' is not numeric at row {row_number}") from exc


def build_plot_spec(
    table: dict[str, Any], *, kind: str, x_column: str | None = None,
    y_column: str | None = None, matrix_columns: list[str] | None = None,
    title: str | None = None, y_error_column: str | None = None,
    significance_column: str | None = None, x_label: str | None = None,
    y_label: str | None = None,
) -> dict[str, Any]:
    if kind not in _KINDS:
        raise ValueError(f"unsupported plot kind: {kind}")
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not isinstance(columns, list) or not isinstance(rows, list) or not rows:
        raise ValueError("table must contain columns and at least one row")
    if kind == "heatmap":
        selected = matrix_columns or []
        missing = [column for column in selected if column not in columns]
        if not selected:
            raise ValueError("heatmap requires matrix_columns")
        if missing:
            raise ValueError(f"missing table columns: {', '.join(missing)}")
        matrix = [[_number(row.get(column), column, index) for column in selected] for index, row in enumerate(rows, 1)]
        data = {"kind": kind, "matrix": matrix, "source_columns": selected}
    else:
        if not x_column or not y_column:
            raise ValueError(f"{kind} requires x_column and y_column")
        y_columns = [item.strip() for item in y_column.split(",") if item.strip()]
        if not y_columns:
            raise ValueError(f"{kind} requires at least one y column")
        error_columns = [item.strip() for item in y_error_column.split(",") if item.strip()] if y_error_column else []
        if error_columns and len(error_columns) not in {1, len(y_columns)}:
            raise ValueError("y_error_column must contain one column or one column per y series")
        requested = [x_column, *y_columns, *error_columns] + ([significance_column] if significance_column else [])
        missing = [column for column in requested if column not in columns]
        if missing:
            raise ValueError(f"missing table columns: {', '.join(missing)}")
        x = [row.get(x_column) for row in rows]
        source_columns = [x_column, *y_columns, *error_columns] + ([significance_column] if significance_column else [])
        series = []
        for index, column in enumerate(y_columns):
            item = {"name": column, "y": [_number(row.get(column), column, row_number) for row_number, row in enumerate(rows, 1)], "source_column": column}
            if error_columns:
                error_column = error_columns[0] if len(error_columns) == 1 else error_columns[index]
                item["y_error"] = [_number(row.get(error_column), error_column, row_number) for row_number, row in enumerate(rows, 1)]
                item["y_error_column"] = error_column
            series.append(item)
        data = {"kind": kind, "x": x, "y": series[0]["y"], "source_columns": source_columns}
        if len(series) > 1:
            data["series"] = series
        elif error_columns:
            data["y_error"] = series[0]["y_error"]
        if significance_column:
            data["significance"] = [str(row.get(significance_column) or "") for row in rows]
        if x_label:
            data["x_label"] = x_label
        if y_label:
            data["y_label"] = y_label
    spec = {
        "schema_version": "0.1", "figure_type": "plot", "title": title or "Generated Plot",
        "layout": {"direction": "left-to-right", "spacing": 24}, "nodes": [], "edges": [], "groups": [],
        "data": data, "provenance": table.get("provenance", {}),
        "style": {"theme": "academic_clean", "colors": {"baseline": "#94A3B8", "ours": "#2563EB"}},
    }
    require_valid_spec(spec)
    return spec
