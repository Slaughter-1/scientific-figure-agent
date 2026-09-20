def test_environment_report_has_required_keys():
    from figure_agent.environment import build_environment_report

    report = build_environment_report()
    assert {"python", "matplotlib", "drawio", "figma_mcp"} <= report.keys()
