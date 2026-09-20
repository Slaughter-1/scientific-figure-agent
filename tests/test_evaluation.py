def test_evaluate_case_reports_node_and_edge_recall():
    from figure_agent.evaluation import evaluate_case

    expected = {"nodes": ["Query", "Retriever", "Generator"], "edges": [["Query", "Retriever"], ["Retriever", "Generator"]]}
    actual = {"nodes": [{"label": "Query"}, {"label": "Retriever"}, {"label": "Generator"}], "edges": [{"source": "Query", "target": "Retriever"}, {"source": "Retriever", "target": "Generator"}]}
    result = evaluate_case(expected, actual)
    assert result["node_recall"] == 1.0
    assert result["edge_recall"] == 1.0


def test_evaluate_cases_aggregates_mean():
    from figure_agent.evaluation import evaluate_cases

    result = evaluate_cases([{"expected": {"nodes": ["A"], "edges": []}, "actual": {"nodes": [{"label": "A"}], "edges": []}}])
    assert result["case_count"] == 1
    assert result["mean_node_recall"] == 1.0


def test_evaluate_case_counts_node_level_evidence():
    from figure_agent.evaluation import evaluate_case

    actual = {
        "nodes": [
            {"label": "A", "evidence": [{"source": "input_text"}]},
            {"label": "B", "evidence": []},
        ],
        "edges": [],
    }
    result = evaluate_case({"nodes": ["A", "B"], "edges": []}, actual)
    assert result["evidence_coverage"] == 0.5


def test_evaluate_case_resolves_edges_through_node_labels():
    from figure_agent.evaluation import evaluate_case

    actual = {
        "nodes": [{"id": "node_0", "label": "A"}, {"id": "node_1", "label": "B"}],
        "edges": [{"source": "node_0", "target": "node_1"}],
    }
    result = evaluate_case({"nodes": ["A", "B"], "edges": [["A", "B"]]}, actual)
    assert result["edge_recall"] == 1.0
