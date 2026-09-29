import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOLDOUT = json.loads(
    (ROOT / "inputs/r2-independent-material/r2_holdout_input.json")
    .read_text(encoding="utf-8")
)


def _case(task_id):
    return next(item for item in HOLDOUT["cases"] if item["task_id"] == task_id)


def test_holdout_branch_prose_preserves_both_condition_arms():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_branch_05")["source_text"])
    labels = {node["label"] for node in spec["nodes"]}
    assert {"意图判断模块", "订单查询流程", "知识检索流程"} <= labels
    decision = next(node["id"] for node in spec["nodes"] if node["label"] == "意图判断模块")
    targets = {edge["target"] for edge in spec["edges"] if edge["source"] == decision}
    assert targets == {
        next(node["id"] for node in spec["nodes"] if node["label"] == "订单查询流程"),
        next(node["id"] for node in spec["nodes"] if node["label"] == "知识检索流程"),
    }
    assert not any(item["code"] == "unparsed_structure" for item in spec["needs_review"])


def test_holdout_feedback_prose_preserves_named_retry_stage():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_feedback_09")["source_text"])
    labels = {node["label"] for node in spec["nodes"]}
    assert "信息检索模块" in labels
    quality = next(node["id"] for node in spec["nodes"] if node["label"] == "质量检查模块")
    retrieval = next(node["id"] for node in spec["nodes"] if node["label"] == "信息检索模块")
    assert any(
        edge["source"] == quality
        and edge["target"] == retrieval
        and edge["type"] == "control_flow"
        for edge in spec["edges"]
    )
    assert not any(item["code"] == "unresolved_loop_target" for item in spec["needs_review"])


def test_explicit_return_continuation_links_back_to_existing_stage():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_feedback_09")["source_text"])
    ids = {node["label"]: node["id"] for node in spec["nodes"]}
    assert any(
        edge["source"] == ids["信息检索模块"]
        and edge["target"] == ids["生成式问答系统产生回答"]
        and edge["type"] == "data_flow"
        and edge["evidence"][0]["quote"] == "再次生成回答"
        for edge in spec["edges"]
    )
    assert len(spec["nodes"]) == 3
    assert len(spec["edges"]) == 3


def test_explicit_return_continuation_matches_a_unique_replacement_stage():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(
        "检索模块获取资料后进入生成模块。如果不完整，则返回检索模块并再次执行生成模块。"
    )
    ids = {node["label"]: node["id"] for node in spec["nodes"]}
    assert (ids["检索模块"], ids["生成模块"]) in {
        (edge["source"], edge["target"])
        for edge in spec["edges"]
        if edge["type"] == "data_flow"
    }


def test_return_without_explicit_continuation_does_not_add_a_loop():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text("系统生成结果后进入校验模块。如果失败，则返回工具模块。")
    assert len(spec["edges"]) == 2


def test_ambiguous_return_continuation_requires_review():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(
        "生成模块产生结果后进入校验模块。如果失败，则返回工具模块并再次执行生成模块、记录日志。"
    )
    assert not any(edge["type"] == "data_flow" and edge.get("evidence", [{}])[0].get("quote") == "再次执行生成模块" for edge in spec["edges"])
    assert any(item["code"] == "ambiguous_continuation" for item in spec["needs_review"])


def test_negative_return_continuation_keeps_return_without_positive_edge():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(
        "生成模块产生结果后进入校验模块。如果失败，则返回工具模块并禁止再次执行生成模块。"
    )
    ids = {node["label"]: node["id"] for node in spec["nodes"]}
    assert any(
        edge["source"] == ids["校验模块"]
        and edge["target"] == ids["工具模块"]
        and edge["type"] == "control_flow"
        for edge in spec["edges"]
    )
    assert not any(
        edge["source"] == ids["工具模块"] and edge["target"] == ids["生成模块"]
        for edge in spec["edges"]
    )
    assert any(item["code"] == "negative_continuation" for item in spec["needs_review"])


def test_holdout_branch_prose_accepts_continue_and_else_arms():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_branch_07")["source_text"])
    labels = {node["label"] for node in spec["nodes"]}
    assert {"状态判断", "生产", "故障处理流程"} <= labels
    decision = next(node["id"] for node in spec["nodes"] if node["label"] == "状态判断")
    targets = {edge["target"] for edge in spec["edges"] if edge["source"] == decision}
    assert targets == {
        next(node["id"] for node in spec["nodes"] if node["label"] == "生产"),
        next(node["id"] for node in spec["nodes"] if node["label"] == "故障处理流程"),
    }
    assert not any(item["code"] == "unparsed_structure" for item in spec["needs_review"])


def test_holdout_feedback_preserves_stage_suffix_in_named_return():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_feedback_11")["source_text"])
    labels = {node["label"] for node in spec["nodes"]}
    assert "模型调整阶段" in labels
    confirmation = next(node["id"] for node in spec["nodes"] if node["label"] == "人工确认模块")
    target = next(node["id"] for node in spec["nodes"] if node["label"] == "模型调整阶段")
    assert any(
        edge["source"] == confirmation
        and edge["target"] == target
        and edge["type"] == "control_flow"
        for edge in spec["edges"]
    )
    assert not any(item["code"] == "unresolved_loop_target" for item in spec["needs_review"])


def test_holdout_mixed_prose_preserves_condition_returns_and_parallel_labels():
    from figure_agent.parser import parse_method_text

    mixed = parse_method_text(_case("r2_mixed_19")["source_text"])
    mixed_labels = {node["label"] for node in mixed["nodes"]}
    assert "知识服务阶段" in mixed_labels
    quality = next(node["id"] for node in mixed["nodes"] if node["label"] == "质量检查模块")
    knowledge = next(node["id"] for node in mixed["nodes"] if node["label"] == "知识服务阶段")
    assert any(
        edge["source"] == quality
        and edge["target"] == knowledge
        and edge["type"] == "control_flow"
        for edge in mixed["edges"]
    )

    parallel = parse_method_text(_case("r2_mixed_20")["source_text"])
    parallel_labels = {node["label"] for node in parallel["nodes"]}
    assert {"数据处理", "模型分析流程", "结果汇合", "质量检查"} <= parallel_labels
    assert "分析阶段" in parallel_labels
    assert not any(item["code"] == "unparsed_structure" for item in parallel["needs_review"])


def test_holdout_parallel_merge_prose_preserves_fan_in():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_parallel_merge_13")["source_text"])
    labels = {node["label"] for node in spec["nodes"]}
    assert {"视觉处理系统", "文本处理系统", "融合模块"} <= labels
    fusion = next(node["id"] for node in spec["nodes"] if node["label"] == "融合模块")
    incoming = [edge for edge in spec["edges"] if edge["target"] == fusion]
    assert len(incoming) == 2
    assert not any(item["code"] == "unparsed_structure" for item in spec["needs_review"])


def test_holdout_containment_prose_preserves_group_membership():
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_containment_17")["source_text"])
    assert any(
        group["label"] == "智能医疗系统"
        and {"病例分析模块", "风险预测模块", "治疗建议模块"}
        <= {next(node["label"] for node in spec["nodes"] if node["id"] == child) for child in group["children"]}
        for group in spec["groups"]
    )
    assert not any(item["code"] == "unparsed_structure" for item in spec["needs_review"])


def test_dense_pipeline_uses_vertical_positions_for_final_size():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_sequence_02")["source_text"])
    plan = build_route_plan(spec, family="pipeline", paper_width_mm=85.0)
    assert len({round(point[1], 4) for point in plan["positions"].values()}) > 1


def test_dense_pipeline_keeps_compact_horizontal_positions_for_double_column_holdout():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_sequence_02")["source_text"])
    spec["constraints"] = {"paper_width": "double_column"}
    plan = build_route_plan(spec, family="pipeline", paper_width_mm=180.0)
    assert len({round(point[0], 4) for point in plan["positions"].values()}) > 1
    assert len({round(point[1], 4) for point in plan["positions"].values()}) == 1


def test_group_only_double_column_layout_stays_horizontal():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_containment_17")["source_text"])
    spec["constraints"] = {"paper_width": "double_column"}
    plan = build_route_plan(spec, family="hierarchy", paper_width_mm=180.0)
    assert len({round(point[0], 4) for point in plan["positions"].values()}) > 1
    assert len({round(point[1], 4) for point in plan["positions"].values()}) == 1


def test_narrow_mixed_layout_allocates_height_for_wrapped_labels():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_mixed_20")["source_text"])
    spec["constraints"] = {"paper_width": "single_column"}
    plan = build_route_plan(spec, family="pipeline", paper_width_mm=85.0)
    assert plan["node_size_units"][1] >= 1.45


def test_narrow_group_title_stays_inside_render_bounds():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_mixed_20")["source_text"])
    spec["constraints"] = {"paper_width": "single_column"}
    spec["style"]["variant"] = "hierarchy"
    plan = build_route_plan(spec, family="hierarchy", paper_width_mm=85.0)
    left, bottom, right, top = plan["bounds"]
    for title in plan["group_titles"]:
        title_left, title_bottom, title_right, title_top = title["box"]
        assert title_left >= left
        assert title_right <= right
        assert title_bottom >= bottom
        assert title_top <= top


def test_narrow_mixed_pipeline_does_not_create_pathological_canvas():
    from figure_agent.layouts import build_route_plan
    from figure_agent.backends.drawio_backend import _wrap_label
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_mixed_20")["source_text"])
    spec["constraints"] = {"paper_width": "single_column"}
    spec["style"] = {"variant": "editorial", "font_family": "DejaVu Sans"}
    plan = build_route_plan(spec, family="pipeline", paper_width_mm=85.0)
    left, bottom, right, top = plan["bounds"]
    assert right - left <= 30
    assert top - bottom <= 18
    for node in spec["nodes"]:
        box = plan["node_boxes"][node["id"]]
        available = max(2.0, (box[2] - box[0]) * plan["mm_per_unit"] - 2.0)
        wrapped = _wrap_label(node["label"], available, plan["node_font_size_pt"], plan["font_path"])
        line_height = plan["node_font_size_pt"] * 25.4 / 72 * 1.2
        assert wrapped.count("\n") + 1
        assert (wrapped.count("\n") + 1) * line_height <= (box[3] - box[1]) * plan["mm_per_unit"]


def test_narrow_long_linear_pipeline_uses_compact_fallback():
    from figure_agent.layouts import build_route_plan
    from figure_agent.parser import parse_method_text

    spec = parse_method_text(_case("r2_mixed_19")["source_text"])
    spec["constraints"] = {"paper_width": "single_column"}
    spec["style"] = {"variant": "editorial", "font_family": "DejaVu Sans"}
    plan = build_route_plan(spec, family="pipeline", paper_width_mm=85.0)
    left, bottom, right, top = plan["bounds"]
    assert top - bottom <= 18


def test_preview_wraps_long_cjk_node_labels():
    from figure_agent.backends.drawio_backend import _wrap_label
    from matplotlib.font_manager import findfont, FontProperties

    font = findfont(FontProperties(family=["Noto Sans SC", "Microsoft YaHei", "DejaVu Sans"]))
    wrapped = _wrap_label("智能客服平台包含问题理解模块和知识服务模块", 18.0, 8.0, font)
    assert "\n" in wrapped
    assert max(len(line) for line in wrapped.splitlines()) < len("智能客服平台包含问题理解模块和知识服务模块")


def test_benchmark_review_state_includes_candidate_geometry_findings(tmp_path, monkeypatch):
    import figure_agent.workflow as workflow
    from figure_agent.visual_eval import generate_benchmark

    def fake_generate(text, output_dir, *, count=3, paper_width=None, **kwargs):
        candidates = []
        for index in range(count):
            candidates.append({
                "candidate_id": f"candidate_{index + 1:02d}",
                "revision_id": f"candidate_{index + 1:02d}-rtest",
                "spec": {"nodes": [], "edges": []},
                "artifacts": {},
                "review_findings": [{"code": "routing_unresolved", "severity": "error"}],
            })
        return {"contract": {}, "candidates": candidates}

    monkeypatch.setattr(workflow, "generate_from_text", fake_generate)
    index = generate_benchmark(
        [{"id": "geometry_case", "category": "pipeline", "text": "文本经过处理后输出结果"}],
        tmp_path / "benchmark",
        paper_widths=("single_column",),
    )
    payload = json.loads(index.read_text(encoding="utf-8"))
    record = payload["records"][0]
    assert record["review_state"] == "needs_review"
    assert "routing_unresolved" in record["needs_review_codes"]
