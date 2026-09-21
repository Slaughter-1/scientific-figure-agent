from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def _table(columns: list[str], rows: list[dict[str, Any]], path: Path, fmt: str) -> dict[str, Any]:
    if not columns:
        raise ValueError("input table must contain a header or columns")
    if not rows:
        raise ValueError("input table must contain at least one records row")
    column_types = {}
    for column in columns:
        values = [row.get(column) for row in rows if row.get(column) not in (None, "")]
        numeric = bool(values)
        for value in values:
            try:
                float(value)
            except (TypeError, ValueError):
                numeric = False
                break
        column_types[column] = "number" if numeric else "category"
    return {"columns": columns, "rows": rows, "column_types": column_types, "provenance": {"source": str(path), "format": fmt}}


def normalize_table(content: str | bytes, *, format: str) -> dict[str, Any]:
    """Normalize uploaded CSV or JSON content into the load_table shape."""
    fmt = format.casefold()
    if fmt == "csv":
        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        reader = csv.DictReader(io.StringIO(text))
        columns = [column.strip() for column in (reader.fieldnames or [])]
        rows = [{column: row.get(column, "") for column in columns} for row in reader]
        return _table(columns, rows, Path("<uploaded>"), fmt)
    if fmt == "json":
        raw = content.decode("utf-8") if isinstance(content, bytes) else content
        payload = json.loads(raw)
        records = payload if isinstance(payload, list) else payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("JSON input must be a records array")
        columns = list(dict.fromkeys(column for record in records for column in record))
        rows = [{column: record.get(column, "") for column in columns} for record in records]
        return _table(columns, rows, Path("<uploaded>"), fmt)
    raise ValueError(f"unsupported table format: {format}")


def load_table(path: str | Path, format: str | None = None) -> dict[str, Any]:
    path = Path(path)
    fmt = (format or path.suffix.lstrip(".")).casefold()
    if fmt == "csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = [column.lstrip("\ufeff").strip() if column else "" for column in (reader.fieldnames or [])]
            if any(not column for column in columns):
                raise ValueError("CSV column names must be non-empty")
            rows = [{column: row.get(column, "") for column in columns} for row in reader]
        return _table(columns, rows, path, "csv")
    if fmt == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("JSON input must be a records array")
        columns: list[str] = []
        for record in records:
            for column in record:
                if column not in columns:
                    columns.append(column)
        rows = [{column: record.get(column, "") for column in columns} for record in records]
        return _table(columns, rows, path, "json")
    raise ValueError(f"unsupported table format: {fmt or 'unknown'}")
