import json
from pathlib import Path

from figure_agent.parser import parse_method_text
from figure_agent.spec import validate_spec


CASES = json.loads(
    (Path(__file__).parents[1] / "eval_cases" / "m2_cases.json").read_text(encoding="utf-8")
)


def test_m2_semantic_cases():
    for case in CASES:
        spec = parse_method_text(case["text"])
        assert validate_spec(spec) == [], case["id"]
        assert [node["label"] for node in spec["nodes"]] == case["required_labels"], case["id"]
        assert len(spec["edges"]) == case["edge_count"], case["id"]
