import pytest


def test_unavailable_llm_is_explicit():
    from figure_agent.providers.llm import UnavailableLLM

    with pytest.raises(RuntimeError, match="no LLM provider"):
        UnavailableLLM().complete_json(system_prompt="", user_prompt="", schema={})


def test_mock_llm_returns_structured_response():
    from figure_agent.providers.llm import MockLLM

    response = {"required_nodes": ["Query"]}
    assert MockLLM(response).complete_json(system_prompt="", user_prompt="", schema={}) == response
