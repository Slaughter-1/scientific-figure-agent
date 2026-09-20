import json


def test_assemble_assets_matches_files_to_node_ids(tmp_path):
    from figure_agent.assembly import assemble_spec_with_assets

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "retriever.svg").write_text('<svg width="320" height="180"></svg>', encoding="utf-8")
    spec_path = tmp_path / "figure.json"
    spec_path.write_text(json.dumps({"nodes": [{"id": "retriever", "label": "Retriever", "type": "tool"}], "asset_refs": []}), encoding="utf-8")
    result = assemble_spec_with_assets(spec_path, assets, tmp_path / "assembled.json")
    assert result["nodes"][0]["asset_refs"]
    assert (tmp_path / "assembled.json").exists()
