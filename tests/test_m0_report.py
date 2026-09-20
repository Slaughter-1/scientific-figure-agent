def test_m0_report_records_figma_connection_status():
    import json
    from pathlib import Path

    report = json.loads(
        Path("docs/m0-validation-report.md")
        .read_text(encoding="utf-8")
        .split("```json", 1)[1]
        .split("```", 1)[0]
    )
    assert report["figma"]["status"] == "unverified_mcp_unavailable"
    assert report["figma"]["editable"] is False
    assert report["figma"]["required_labels"]
