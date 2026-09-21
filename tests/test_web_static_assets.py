from pathlib import Path


def test_frontend_preview_module_has_svg_fallback():
    preview = Path("frontend/src/preview.js")

    assert preview.exists()
    source = preview.read_text(encoding="utf-8")
    assert "resolvePreview" in source
    assert 'type: "svg"' in source


def test_frontend_styles_include_cjk_font_fallback():
    source = Path("frontend/src/styles.css").read_text(encoding="utf-8")

    assert "Noto Sans SC" in source
    assert "Microsoft YaHei" in source
