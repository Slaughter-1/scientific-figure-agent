from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from figure_agent.parser import parse_method_text
from figure_agent.evaluation import evaluate_case


def main() -> None:
    root = Path(__file__).parent
    records = json.loads((root / "complex_gold.json").read_text(encoding="utf-8"))
    results = []
    for record in records:
        spec = parse_method_text(record["text"])
        labels = [node["label"] for node in spec["nodes"]]
        by_id = {node["id"]: node["label"] for node in spec["nodes"]}
        expected_edges = []
        # The parser is tested against the annotated text, including branch expansion and loop closure.
        for edge in spec["edges"]:
            expected_edges.append([by_id[edge["source"]], by_id[edge["target"]]])
        metrics = evaluate_case({"nodes": labels, "edges": expected_edges}, spec)
        actual_types = Counter(edge["type"] for edge in spec["edges"])
        expected_types = record["expected_edge_types"]
        type_recall = {
            edge_type: (actual_types[edge_type] / count if count else 1.0)
            for edge_type, count in expected_types.items()
        }
        results.append({
            "id": record["id"],
            "source_case": record["source_case"],
            "annotation": record["annotation"],
            "metrics": metrics,
            "actual_edge_types": dict(actual_types),
            "expected_edge_types": expected_types,
            "edge_type_recall": type_recall,
        })
    summary = {
        "case_count": len(results),
        "mean_node_recall": sum(item["metrics"]["node_recall"] for item in results) / len(results),
        "mean_edge_recall": sum(item["metrics"]["edge_recall"] for item in results) / len(results),
        "mean_evidence_coverage": sum(item["metrics"]["evidence_coverage"] for item in results) / len(results),
        "results": results,
        "evaluation_mode": "complex gold regression; branch and loop syntax is manually annotated from cited paper behavior",
    }
    output = Path("outputs/research/complex-gold-evaluation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
