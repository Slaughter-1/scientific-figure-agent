from __future__ import annotations

import json
from pathlib import Path

from figure_agent.evaluation import evaluate_case, evaluate_cases
from figure_agent.workflow import generate_from_text


def main() -> None:
    corpus_path = Path(__file__).with_name("public_paper_corpus.json")
    records = json.loads(corpus_path.read_text(encoding="utf-8"))
    output_root = Path("outputs/research/public_corpus")
    output_root.mkdir(parents=True, exist_ok=True)
    cases = []
    for record in records:
        text = record["method_chain"]
        labels = [item.strip() for item in text.split("→")]
        expected = {"nodes": labels, "edges": [[labels[i], labels[i + 1]] for i in range(len(labels) - 1)]}
        generated = generate_from_text(text, output_root / record["id"], count=3)
        actual = generated["candidates"][0]["spec"]
        # Candidate generation keeps evidence on every parsed node.
        result = evaluate_case(expected, actual)
        result.update({"id": record["id"], "title": record["title"], "category": record["category"]})
        cases.append({"expected": expected, "actual": actual, "metrics": result})
    summary = evaluate_cases(cases)
    summary["corpus_count"] = len(records)
    summary["source"] = "research_data/public_paper_corpus.json"
    summary["evaluation_mode"] = "parser_regression; expected chains are curator-transcribed from cited paper/repository evidence"
    (output_root / "evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
