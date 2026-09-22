import json
from pathlib import Path

import pytest

from figure_agent.candidates import _has_cycle
from figure_agent.critic import critique_spec
from figure_agent.layouts import layout_edges, layout_nodes, node_size
from figure_agent.parser import parse_method_text


def _labels_and_edges(spec):
    labels = {node["id"]: node["label"] for node in spec["nodes"]}
    return {labels[edge["source"]]: labels[edge["target"]] for edge in spec["edges"]}


def test_prefix_does_not_bypass_prose_parser():
    spec = parse_method_text("系统首先审核通过后发布，审核失败则返回修改环节")
    assert spec["schema_version"] == "0.3"
    assert {node["label"] for node in spec["nodes"]} == {"审核", "发布", "修改环节"}
    assert {(edge["source"], edge["target"], edge["type"]) for edge in spec["edges"]} == {
        ("node_0", "node_1", "control_flow"),
        ("node_0", "node_2", "control_flow"),
    }


def test_prefix_keeps_sequence_and_original_offsets():
    text = "  系统首先文本经过分词、编码后送入分类器并输出标签"
    spec = parse_method_text(text)
    assert [node["label"] for node in spec["nodes"]] == ["文本", "分词", "编码", "分类器", "输出标签"]
    assert spec["nodes"][0]["evidence"][0]["start"] == 6
    assert spec["nodes"][0]["evidence"][0]["quote"] == "文本"


def test_noun_list_is_not_promoted_to_data_flow():
    spec = parse_method_text("系统支持图像、文本两种输入")
    assert {node["label"] for node in spec["nodes"]} == {"图像", "文本"}
    assert spec["edges"] == []
    assert len(spec["groups"]) == 1


def test_negated_parallel_relation_is_review_only():
    spec = parse_method_text("协调器不并行调用检索代理和分析代理，最终交给回答代理")
    assert not spec["edges"]
    assert any(item["code"] == "negated_relation" for item in spec["needs_review"])


@pytest.mark.parametrize("negation", ["不得", "不应", "不允许"])
def test_common_negated_parallel_phrasings_do_not_create_fanout(negation):
    spec = parse_method_text(f"协调器{negation}并行调用检索代理和分析代理")
    assert not spec["edges"]
    assert any(item["code"] == "negated_relation" for item in spec["needs_review"])


def test_ambiguous_branch_continuation_requires_review():
    spec = parse_method_text("接收请求，分类器根据置信度分为高置信路径和低置信路径，生成报告")
    labels = {node["id"]: node["label"] for node in spec["nodes"]}
    pairs = {(labels[edge["source"]], labels[edge["target"]], edge["type"]) for edge in spec["edges"]}
    assert ("接收请求", "分类器", "data_flow") in pairs or ("请求", "分类器", "data_flow") in pairs
    assert ("分类器", "高置信路径", "control_flow") in pairs
    assert ("分类器", "低置信路径", "control_flow") in pairs
    assert not any(b == "生成报告" for a, b, _ in pairs)
    assert any(issue['code'] == 'unresolved_branch_join' for issue in spec['needs_review'])


def test_explicit_branch_join_connects_all_named_arms():
    spec = parse_method_text("分类器根据置信度分为高置信路径和低置信路径，最终交给报告生成器")
    labels = {node["id"]: node["label"] for node in spec["nodes"]}
    pairs = {(labels[edge["source"]], labels[edge["target"]]) for edge in spec["edges"]}
    assert pairs == {
        ("分类器", "高置信路径"),
        ("分类器", "低置信路径"),
        ("高置信路径", "报告生成器"),
        ("低置信路径", "报告生成器"),
    }
    assert not any(issue["code"] == "unresolved_branch_join" for issue in spec["needs_review"])


def test_critic_uses_complete_source_text_and_distinguishes_result_return():
    parsed = parse_method_text("协调器并行调用检索代理和分析代理，最终交给回答代理；若证据不足则回到检索代理继续搜索")
    incomplete = json.loads(json.dumps(parsed, ensure_ascii=False))
    incomplete["edges"] = incomplete["edges"][:1]
    findings = {item["code"] for item in critique_spec(incomplete)}
    assert "missing_parallel_structure" in findings
    assert "missing_feedback_structure" in findings

    result_return = parse_method_text("调用工具，工具返回证据，输出答案")
    assert "missing_feedback_structure" not in {item["code"] for item in critique_spec(result_return)}


def test_cycle_detection_is_independent_of_node_array_order():
    assert not _has_cycle({"nodes": [{"id": "b"}, {"id": "a"}], "edges": [{"source": "a", "target": "b"}]})
    assert _has_cycle({"nodes": [{"id": "b"}, {"id": "a"}], "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]})


def test_layout_and_render_share_node_dimensions(tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    from matplotlib.axes import Axes
    from matplotlib.patches import FancyBboxPatch
    from figure_agent.backends.drawio_backend import build_drawio_xml, render_drawio_spec

    spec = parse_method_text("输入经过模型后输出答案")
    spec["style"].update({"node": {"width": 180, "height": 72}})
    positions = layout_nodes(spec, family="pipeline")
    width, height = node_size(spec)
    routes = layout_edges(spec, positions, family="pipeline")
    assert width == 1.8 and height == 0.72
    assert routes
    xml = build_drawio_xml(spec)
    assert 'width="180" height="72"' in xml
    for node in spec['nodes']:
        geometry = ET.fromstring(xml).find(f".//mxCell[@id='{node['id']}']/mxGeometry")
        x, y = positions[node['id']]
        assert abs(float(geometry.get('x')) + 90 - x * 100) < 0.01
        assert abs(float(geometry.get('y')) + 36 - (6.2 - y) * 100) < 0.01
    patches = []
    original = Axes.add_patch
    def capture(ax, patch):
        if isinstance(patch, FancyBboxPatch):
            patches.append(patch)
        return original(ax, patch)
    monkeypatch.setattr(Axes, 'add_patch', capture)
    artifacts = render_drawio_spec(spec, tmp_path, "geometry")
    assert all(path.exists() for path in artifacts.values())
    assert len(patches) == len(spec['nodes'])
    for patch in patches:
        bounds = patch.get_path().get_extents()
        assert abs(bounds.width - width) < 1e-8
        assert abs(bounds.height - height) < 1e-8


def test_pdf_font_policy_survives_global_backend_settings(tmp_path):
    import matplotlib
    from figure_agent.backends.drawio_backend import render_drawio_spec

    spec = parse_method_text('输入经过模型后输出答案')
    with matplotlib.rc_context({'pdf.fonttype': 42}):
        files = render_drawio_spec(spec, tmp_path)
        assert matplotlib.rcParams['pdf.fonttype'] == 42
    pdf = files['pdf'].read_bytes()
    assert b'/Subtype /Type3' in pdf
    assert b'/FontFile2' not in pdf


def test_modalities_are_grouped_without_a_data_flow_edge():
    spec = parse_method_text("系统支持图像、文本两种模态")
    assert {node["label"] for node in spec["nodes"]} == {"图像", "文本"}
    assert spec["edges"] == []
    assert any(issue["code"] == "unresolved_relation" for issue in spec["needs_review"]) is False


def test_negated_parallel_is_reviewed_without_affirmative_fanout():
    spec = parse_method_text("协调器不会并行调用检索代理和分析代理，最终交给回答代理")
    assert not spec["edges"]
    assert any(issue["code"] == "negated_relation" for issue in spec["needs_review"])


def test_ambiguous_branch_tail_is_explicitly_reviewed():
    spec = parse_method_text("审核通过后发布，审核失败则返回修改环节，生成报告")
    assert not any(node["label"] == "生成报告" for node in spec["nodes"])
    assert any(issue["code"] == "unresolved_branch_join" for issue in spec["needs_review"])


def test_critic_detects_missing_bare_return_edge():
    spec = parse_method_text("检索器查询知识库，生成器生成答案，返回检索器")
    spec["edges"] = [edge for edge in spec["edges"] if edge["type"] != "control_flow"]
    assert "missing_feedback_structure" in {item["code"] for item in critique_spec(spec)}


def test_pipeline_feedback_uses_a_separate_corridor():
    spec = parse_method_text("协调器并行调用检索代理和分析代理，最终交给回答代理；若证据不足则回到检索代理继续搜索。")
    positions = layout_nodes(spec, family="pipeline")
    routes = layout_edges(spec, positions, family="pipeline")
    forward = routes[3]
    feedback = routes[4]
    horizontal = lambda route: {(round(min(a[0], b[0]), 5), round(max(a[0], b[0]), 5), round(a[1], 5))
                                for a, b in zip(route, route[1:]) if abs(a[1] - b[1]) < 1e-8 and abs(a[0] - b[0]) > 1e-8}
    assert not horizontal(forward) & horizontal(feedback)


def test_swimlane_forward_edges_do_not_reverse_overlap():
    spec = parse_method_text("协调器并行调用检索代理和分析代理，最终交给回答代理；若证据不足则回到检索代理继续搜索。")
    positions = layout_nodes(spec, family="swimlane")
    routes = layout_edges(spec, positions, family="swimlane")

    def horizontal(route):
        return [
            (min(a[0], b[0]), max(a[0], b[0]), a[1], a[0] < b[0])
            for a, b in zip(route, route[1:])
            if abs(a[1] - b[1]) < 1e-8 and abs(a[0] - b[0]) > 1e-8
        ]

    def reverse_overlap(left, right):
        return any(
            a[3] != b[3]
            and a[2] == b[2]
            and min(a[1], b[1]) - max(a[0], b[0]) > 1e-8
            for a in horizontal(left)
            for b in horizontal(right)
        )

    assert not any(reverse_overlap(left, right) for index, left in enumerate(routes) for right in routes[index + 1:])
    from figure_agent.visual_critic import critique_spec_geometry
    assert "edge_reverse_overlap" not in {item["code"] for item in critique_spec_geometry(spec)}
