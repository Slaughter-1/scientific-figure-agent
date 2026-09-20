import json


def test_build_component_package_writes_manifest_and_prompts(tmp_path):
    from figure_agent.components import build_component_package

    spec = {
        "nodes": [{"id": "retriever", "label": "Retriever", "type": "tool"}],
        "style": {"colors": {"tool": "#E8EEF7"}},
    }
    result = build_component_package(spec, tmp_path)
    assert (tmp_path / "component-manifest.json").exists()
    assert (tmp_path / "component-prompts.md").exists()
    manifest = json.loads((tmp_path / "component-manifest.json").read_text(encoding="utf-8"))
    assert manifest["components"][0]["component_id"] == "retriever"
    assert "Retriever" in (tmp_path / "component-prompts.md").read_text(encoding="utf-8")
    assert result["manifest"]


def test_register_asset_records_editability_and_format(tmp_path):
    from figure_agent.components import register_asset

    svg = tmp_path / "retriever.svg"
    svg.write_text('<svg width="320" height="180"></svg>', encoding="utf-8")
    asset = register_asset(svg, source="user_upload", license_status="user_confirmed")
    assert asset["format"] == "svg"
    assert asset["editable"] is True
    assert asset["width"] == 320
    assert asset["license"] == "user_confirmed"


def test_attach_assets_maps_user_assets_to_spec_nodes(tmp_path):
    from figure_agent.components import attach_assets_to_spec, register_asset

    svg = tmp_path / "retriever.svg"
    svg.write_text('<svg width="320" height="180"></svg>', encoding="utf-8")
    asset = register_asset(svg, source="user_upload", license_status="user_confirmed")
    spec = {"nodes": [{"id": "retriever", "label": "Retriever", "type": "tool"}]}
    attached = attach_assets_to_spec(spec, {"retriever": asset})
    assert attached["nodes"][0]["asset_refs"] == [asset["asset_id"]]
    assert attached["asset_refs"][0]["asset_id"] == asset["asset_id"]
