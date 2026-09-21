def _spec(edges):
    return {
        "nodes": [
            {"id": "query", "label": "Query", "type": "data"},
            {"id": "planner", "label": "Planner", "type": "process"},
            {"id": "tool", "label": "Tool", "type": "tool"},
            {"id": "answer", "label": "Answer", "type": "data"},
        ],
        "edges": edges,
        "groups": [],
    }


def test_layout_families_produce_different_positions():
    from figure_agent.layouts import layout_nodes

    spec = _spec([
        {"source": "query", "target": "planner"},
        {"source": "planner", "target": "tool"},
        {"source": "tool", "target": "answer"},
    ])

    pipeline = layout_nodes(spec, family="pipeline")
    swimlane = layout_nodes(spec, family="swimlane")
    hierarchy = layout_nodes(spec, family="hierarchy")

    assert pipeline != swimlane
    assert swimlane != hierarchy
    assert pipeline["query"][0] < pipeline["answer"][0]
    assert swimlane["query"][1] != swimlane["answer"][1]


def test_loop_layout_routes_feedback_around_nodes():
    from figure_agent.layouts import layout_edges, layout_nodes

    spec = _spec([
        {"source": "query", "target": "planner"},
        {"source": "planner", "target": "tool"},
        {"source": "tool", "target": "answer"},
        {"source": "tool", "target": "planner"},
    ])
    positions = layout_nodes(spec, family="loop")
    routes = layout_edges(spec, positions, family="loop")

    feedback = routes[3]
    assert len(feedback) >= 3
    assert feedback[0] != positions["tool"]
    assert feedback[-1] != positions["planner"]
