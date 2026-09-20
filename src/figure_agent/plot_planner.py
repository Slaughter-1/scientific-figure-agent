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
        requested = [x_column, y_column] + ([y_error_column] if y_error_column else [])
        missing = [column for column in requested if column not in columns]
        if missing:
            raise ValueError(f"missing table columns: {', '.join(missing)}")
        x = [row.get(x_column) for row in rows]
        y = [_number(row.get(y_column), y_column, index) for index, row in enumerate(rows, 1)]
        data = {"kind": kind, "x": x, "y": y, "source_columns": [x_column, y_column]}
        if y_error_column:
            data["y_error"] = [_number(row.get(y_error_column), y_error_column, index) for index, row in enumerate(rows, 1)]
            data["source_columns"].append(y_error_column)
    spec = {
        "schema_version": "0.1", "figure_type": "plot", "title": title or "Generated Plot",
        "layout": {"direction": "left-to-right", "spacing": 24}, "nodes": [], "edges": [], "groups": [],
        "data": data, "provenance": table.get("provenance", {}),
        "style": {"theme": "academic_clean", "colors": {"baseline": "#94A3B8", "ours": "#2563EB"}},
    }
    require_valid_spec(spec)
    return spec
