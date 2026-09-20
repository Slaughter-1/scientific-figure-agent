def test_classifier_rejects_empty_input():
    import pytest

    from figure_agent.planner import classify_figure

    with pytest.raises(ValueError, match="non-empty"):
        classify_figure(" ")
