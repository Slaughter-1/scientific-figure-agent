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
