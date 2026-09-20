from __future__ import annotations

import re
from typing import Any

from .spec import require_valid_spec

_ARROW_SPLIT = re.compile(r"\s*(?:→|->|=>)\s*")
_CLAUSE_SPLIT = re.compile(r"[，,。；;。]\s*")
_LEADING = re.compile(r"^(?:系统)?(?:首先|然后|接着|再|最后|最终)?")


def _clean_clause(clause: str, *, strip_leading: bool = True) -> str:
    clause = clause.strip()
    if strip_leading:
        clause = _LEADING.sub("", clause)
    clause = re.sub(r"^(?:通过|利用|使用|对|将)", "", clause)
    clause = clause.strip()
    if "模块" in clause:
        return clause[: clause.index("模块") + 2]
    if "模型" in clause:
        return clause[: clause.index("模型") + 2]
    if clause.startswith("接收"):
        return clause[2:].strip()
    if clause.startswith("存入"):
        return clause[2:].strip()
    if clause.startswith("输出"):
        return clause.strip()
    if clause.startswith("输入"):
        return clause.strip()
    return clause


def _node_type(label: str) -> str:
    if any(token in label.lower() for token in ("模型", "llm", "gpt")):
        return "model"
    if any(token in label.lower() for token in ("工具", "tool", "search", "code")):
        return "tool"
    if any(token in label for token in ("库", "数据库", "database", "storage")):
        return "storage"
    if any(token in label for token in ("文本", "数据", "query", "answer", "结果", "输入", "输出")):
        return "data"
    return "process"


def parse_method_text(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    arrow_delimited = _ARROW_SPLIT.search(text) is not None
    raw_clauses = _ARROW_SPLIT.split(text) if arrow_delimited else _CLAUSE_SPLIT.split(text)
    labels = []
    evidence_by_label: dict[str, str] = {}
    for raw in raw_clauses:
        label = _clean_clause(raw, strip_leading=not arrow_delimited)
        if label and label not in labels:
            labels.append(label)
            evidence_by_label[label] = raw.strip()
    nodes = [
        {"id": f"node_{index}", "label": label, "type": _node_type(label), "evidence": [{"source": "input_text", "quote": evidence_by_label[label]}]}
        for index, label in enumerate(labels)
    ]
    edges = [
        {"source": nodes[index]["id"], "target": nodes[index + 1]["id"], "type": "data_flow"}
        for index in range(len(nodes) - 1)
    ]
    spec = {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "title": "Generated Workflow",
        "layout": {"direction": "left-to-right", "spacing": 24},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
        "style": {"theme": "academic_clean", "colors": {"process": "#E8EEF7", "data": "#F2F4F7"}},
    }
    require_valid_spec(spec)
    return spec
