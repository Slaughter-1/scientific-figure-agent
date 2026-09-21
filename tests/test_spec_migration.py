import pytest


def test_migrate_legacy_spec_to_03_preserves_content():
    from figure_agent.spec_migration import migrate_spec

    spec = {
        "schema_version": "0.1", "figure_type": "workflow",
        "layout": {"direction": "left-to-right"},
        "nodes": [{"id": "query", "label": "Query", "type": "data", "evidence": [{"source": "input_text", "quote": "Query"}]}],
        "edges": [], "groups": [], "style": {},
    }
    migrated = migrate_spec(spec, task_id="task-1")
    assert migrated["schema_version"] == "0.3"
    assert migrated["task_id"] == "task-1"
    assert migrated["nodes"][0]["locked"] is False
    assert migrated["nodes"][0]["confidence"] == 1.0


def test_03_rejects_invalid_semantic_confidence():
    from figure_agent.spec import validate_spec

    spec = {"schema_version": "0.3", "figure_type": "workflow", "layout": {"direction": "left-to-right"}, "nodes": [], "edges": [], "groups": [], "style": {}, "semantic_confidence": 2}
    assert "semantic_confidence must be between 0 and 1" in validate_spec(spec)
