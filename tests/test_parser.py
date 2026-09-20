from figure_agent.parser import parse_method_text
from figure_agent.spec import validate_spec


def test_parser_rejects_empty_text():
    import pytest

    with pytest.raises(ValueError, match="non-empty"):
        parse_method_text("  ")


def test_parser_extracts_explicit_pipeline_stages():
    text = "系统首先接收药品说明书文本，然后通过预处理模块提取候选片段，再利用大语言模型进行规则识别，最终存入结构化规则库。"
    spec = parse_method_text(text)
    assert validate_spec(spec) == []
    assert [node["label"] for node in spec["nodes"]] == [
        "药品说明书文本",
        "预处理模块",
        "大语言模型",
        "结构化规则库",
    ]
    assert len(spec["edges"]) == 3


def test_parser_does_not_invent_modules():
    spec = parse_method_text("输入文本，然后输出结果。")
    assert [node["label"] for node in spec["nodes"]] == ["输入文本", "输出结果"]


def test_parser_handles_arrow_delimited_workflow():
    spec = parse_method_text("Query → Planner → Tool → Answer")
    assert validate_spec(spec) == []
    assert len(spec["nodes"]) == 4
    assert len(spec["edges"]) == 3


def test_parser_records_source_evidence_for_each_node():
    spec = parse_method_text("接收文本 → 检索工具 → 生成模型")
    assert all(node["evidence"] for node in spec["nodes"])
    assert spec["nodes"][1]["evidence"][0]["source"] == "input_text"
    assert "检索工具" in spec["nodes"][1]["evidence"][0]["quote"]


def test_parser_expands_explicit_branch_group():
    spec = parse_method_text("Query → [Retriever | Memory] → Generator")
    labels = {node["label"] for node in spec["nodes"]}
    assert labels == {"Query", "Retriever", "Memory", "Generator"}
    ids = {node["label"]: node["id"] for node in spec["nodes"]}
    pairs = {(edge["source"], edge["target"]) for edge in spec["edges"]}
    assert (ids["Query"], ids["Retriever"]) in pairs
    assert (ids["Query"], ids["Memory"]) in pairs
    assert (ids["Retriever"], ids["Generator"]) in pairs
    assert (ids["Memory"], ids["Generator"]) in pairs


def test_parser_expands_natural_language_branch_stage():
    spec = parse_method_text("Query → branches to Retriever and Memory → Generator")
    labels = {node["label"] for node in spec["nodes"]}
    assert labels == {"Query", "Retriever", "Memory", "Generator"}


def test_classifier_routes_common_figure_inputs():
    from figure_agent.planner import classify_figure

    assert classify_figure("模块 A 连接模块 B，形成系统架构") == "architecture"
    assert classify_figure("输入 → Planner → Answer") == "workflow"
    assert classify_figure({"data": {"kind": "line"}, "figure_type": "plot"}) == "plot"
