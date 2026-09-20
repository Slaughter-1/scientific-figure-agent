import pytest


def test_figure_request_applies_three_candidate_defaults():
    from figure_agent.request import FigureRequest

    request = FigureRequest.from_dict({"input_type": "paper_text", "content": "Planner calls retriever."})
    assert request.candidate_count == 3
    assert request.style == "academic_clean"
    assert request.template_policy == "open_license_first"
    assert request.to_dict()["input_type"] == "paper_text"


def test_figure_request_rejects_unknown_input_and_empty_content():
    from figure_agent.request import FigureRequest

    with pytest.raises(ValueError, match="input_type"):
        FigureRequest.from_dict({"input_type": "url", "content": "x"})
    with pytest.raises(ValueError, match="content"):
        FigureRequest.from_dict({"input_type": "paper_text", "content": " "})


def test_figure_request_rejects_candidate_count_out_of_range():
    from figure_agent.request import FigureRequest

    with pytest.raises(ValueError, match="candidate_count"):
        FigureRequest.from_dict({"input_type": "paper_text", "content": "x", "candidate_count": 6})
