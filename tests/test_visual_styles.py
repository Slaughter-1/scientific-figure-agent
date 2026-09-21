def test_visual_styles_have_distinct_layout_and_render_tokens():
    from figure_agent.visual_styles import get_visual_style

    editorial = get_visual_style("editorial")
    swimlane = get_visual_style("swimlane")
    loop = get_visual_style("loop")

    assert {editorial["layout_family"], swimlane["layout_family"], loop["layout_family"]} == {"pipeline", "swimlane", "loop"}
    assert editorial["node"]["width"] != swimlane["node"]["width"]
    assert editorial["edge"]["routing"] != loop["edge"]["routing"]
    assert editorial["colors"] != swimlane["colors"]


def test_chinese_font_resolution_prefers_editable_cjk_font():
    from figure_agent.visual_styles import resolve_font_family

    primary, fallbacks = resolve_font_family("zh")

    assert primary == "Noto Sans SC"
    assert "Microsoft YaHei" in fallbacks
    assert "SimHei" in fallbacks
