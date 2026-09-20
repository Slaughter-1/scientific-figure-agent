def test_build_figure_contract_extracts_labels_and_review_state():
    from figure_agent.workflow import build_figure_contract

    contract = build_figure_contract("用户问题 → 检索工具 → 生成模型 → 答案")
    assert contract["target_figure_type"] == "workflow"
    assert contract["required_labels"] == ["用户问题", "检索工具", "生成模型", "答案"]
    assert contract["needs_review"] == []


def test_generate_from_text_writes_contract_and_candidates(tmp_path):
    from figure_agent.workflow import generate_from_text

    result = generate_from_text("Query → Planner → Answer", tmp_path, count=3)
    assert (tmp_path / "figure-contract.json").exists()
    assert len(result["candidates"]) == 3
    assert result["contract"]["target_figure_type"] == "workflow"
