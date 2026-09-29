from __future__ import annotations

import re
from typing import Any

from .spec import require_valid_spec

_ARROW_SPLIT = re.compile(r"\s*(?:→|->|=>)\s*")
_CLAUSE_SPLIT = re.compile(r"[，,。；;。]\s*")
_LEADING = re.compile(r"^(?:系统)?(?:首先|然后|接着|再|最后|最终)?")
_LOOP_MARKER = re.compile(
    r"^(?:则|然后|再)?\s*(?:loop\s+back\s+to|repeat(?:\s+until)?|循环回到|回到|返回|迭代到)\s*[:：]?\s*(.+)$",
    flags=re.IGNORECASE,
)


def _clean_clause(clause: str, *, strip_leading: bool = True) -> str:
    clause = clause.strip()
    if strip_leading:
        clause = _LEADING.sub("", clause)
    clause = re.sub(r"^(?:通过|利用|使用|对|将)", "", clause)
    clause = clause.strip()
    if "模块" in clause:
        return clause[: clause.index("模块") + 2]
    if "模型" in clause:
        model_at = clause.index("模型")
        suffix = clause[model_at + 2:]
        # Keep an explicitly named action such as ``完成模型分析`` intact.
        # Bare model nouns (``大语言模型进行规则识别``) retain the historic
        # noun normalization used by the parser and existing contracts.
        if suffix and re.search(r"(?:完成|执行|进行|生成|输出)模型", clause):
            return clause
        return clause[: model_at + 2]
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


def _expand_stage(raw: str, *, arrow_delimited: bool) -> list[str]:
    label = _clean_clause(raw, strip_leading=not arrow_delimited)
    natural_branch = re.search(r"(?:branches?\s+to|分支为|分为)\s+(.+)$", label, flags=re.IGNORECASE)
    if natural_branch:
        parts = [part.strip() for part in re.split(r"\s+(?:and|or)\s+|和|或|、|,", natural_branch.group(1)) if part.strip()]
        if len(parts) > 1:
            return [_clean_clause(part, strip_leading=False) for part in parts]
    if len(label) >= 2 and label[0] in "[({" and label[-1] in "])}":
        inner = label[1:-1]
        parts = [part.strip() for part in re.split(r"\s*[|/]\s*", inner) if part.strip()]
        if len(parts) > 1:
            return [_clean_clause(part, strip_leading=False) for part in parts]
    return [label] if label else []



def parse_method_text(text: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    from .prose import parse_explicit_prose

    # Arrow-delimited input is handled by the legacy, deliberately literal
    # parser. All prose, including harmless prefixes such as "系统首先", goes
    # through the conservative semantic parser so there is no semantic bypass.
    natural = parse_explicit_prose(text)
    if natural is not None:
        require_valid_spec(natural)
        return natural
    arrow_delimited = _ARROW_SPLIT.search(text) is not None
    raw_clauses = _ARROW_SPLIT.split(text) if arrow_delimited else _CLAUSE_SPLIT.split(text)
    labels = []
    stages: list[list[str]] = []
    transitions: list[dict[str, Any]] = []
    needs_review: list[dict[str, str]] = []
    evidence_by_label: dict[str, str] = {}
    pending_condition = ""
    for clause_index, raw in enumerate(raw_clauses):
        raw = raw.strip()
        if not raw:
            continue
        original_clause = raw
        inline_return = re.match(r"^((?:若|如果|当).+?)(?:则)?((?:循环回到|回到|返回|迭代到).+)$", raw)
        if inline_return:
            pending_condition = inline_return.group(1).removesuffix("则").strip()
            raw = inline_return.group(2)
        # A condition immediately before an explicit return belongs to the edge,
        # not to an invented evaluator module.
        if re.match(r"^(?:若|如果|当|if\b)", raw, re.IGNORECASE) and clause_index + 1 < len(raw_clauses) and _LOOP_MARKER.match(raw_clauses[clause_index + 1].strip()):
            pending_condition = raw
            continue
        loop_match = _LOOP_MARKER.search(raw.strip())
        if loop_match:
            target = _clean_clause(loop_match.group(1), strip_leading=False)
            target = re.split(r"\s+until\s+", target, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            target = re.split(r"继续|重新", target, maxsplit=1)[0].strip()
            matches = [label for label in labels if label == target]
            if not matches and target:
                matches = [label for label in labels if label.startswith(target)]
            if len(matches) != 1 or not stages:
                needs_review.append({"code": "unresolved_loop_target", "target": target, "message": "Return target must resolve to exactly one earlier stage.", "quote": raw})
                pending_condition = ""
                continue
            stage = matches
            edge_type = "control_flow"
        else:
            stage = _expand_stage(raw, arrow_delimited=arrow_delimited)
            edge_type = "data_flow"
        if stages:
            for source in stages[-1]:
                for target in stage:
                    quote = original_clause if inline_return else pending_condition + ("，" if pending_condition else "") + raw
                    edge = {"source": source, "target": target, "type": edge_type,
                            "evidence": [{"source": "input_text", "quote": quote}]}
                    if pending_condition:
                        edge["label"] = pending_condition
                    transitions.append(edge)
        pending_condition = ""
        stages.append(stage)
        for label in stage:
            if label and label not in labels:
                labels.append(label)
                evidence_by_label[label] = raw.strip()
    nodes = [
        {"id": f"node_{index}", "label": label, "type": _node_type(label), "evidence": [{"source": "input_text", "quote": evidence_by_label[label]}]}
        for index, label in enumerate(labels)
    ]
    node_ids = {node["label"]: node["id"] for node in nodes}
    edges = [{**edge, "source": node_ids[edge["source"]], "target": node_ids[edge["target"]]} for edge in transitions]
    spec = {
        "schema_version": "0.1",
        "figure_type": "workflow",
        "title": "Generated Workflow",
        "layout": {"direction": "left-to-right", "spacing": 24},
        "nodes": nodes,
        "edges": edges,
        "groups": [],
        "needs_review": needs_review,
        "style": {"theme": "academic_clean", "colors": {"process": "#E8EEF7", "data": "#F2F4F7"}},
    }
    require_valid_spec(spec)
    return spec
