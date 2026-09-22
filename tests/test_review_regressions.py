import pytest

from figure_agent.parser import parse_method_text
from figure_agent.workflow import build_figure_contract
from figure_agent.workflow import compile_spec_with_contract, generate_from_text
from figure_agent.layouts import layout_edges

REVIEW_INPUT = '用户问题经过规划器分解，检索器查询知识库，工具返回证据，生成器综合证据后输出答案；若证据不足，则回到检索器继续搜索。'


def test_review_input_keeps_tool_result_and_resolves_conditional_feedback():
    spec = parse_method_text(REVIEW_INPUT)
    labels = {n['label']: n['id'] for n in spec['nodes']}
    assert len(labels) == 4
    assert '工具返回证据' in labels
    feedback = [e for e in spec['edges'] if e['type'] == 'control_flow']
    assert len(feedback) == 1
    assert feedback[0]['source'] == labels['生成器综合证据后输出答案']
    assert feedback[0]['target'] == labels['检索器查询知识库']
    assert feedback[0]['label'] == '若证据不足'
    assert feedback[0]['evidence'][0]['quote'] in REVIEW_INPUT


@pytest.mark.parametrize('marker', ['回到', '循环回到', '返回'])
def test_return_to_existing_stage(marker):
    spec = parse_method_text(f'检索器 -> 生成器 -> {marker}检索器')
    assert len(spec['nodes']) == 2
    assert spec['edges'][-1]['target'] == 'node_0'


def test_unknown_feedback_does_not_invent_target():
    text = '检索器 -> 生成器 -> 回到评估器'
    spec = parse_method_text(text)
    assert len(spec['nodes']) == 2
    assert any(n['code'] == 'unresolved_loop_target' for n in spec['needs_review'])
    assert any(n['code'] == 'unresolved_loop_target' for n in build_figure_contract(text)['needs_review'])


def test_ambiguous_feedback_does_not_choose_a_retriever():
    spec = parse_method_text('检索器查询文档，检索器查询网页，生成器，回到检索器。')
    assert len(spec['nodes']) == 3
    assert spec['needs_review']
    assert not any(e['type'] == 'control_flow' for e in spec['edges'])


def test_hierarchy_arrow_approaches_target_downward_without_entering_center():
    spec = {'nodes': [{'id': 'a'}, {'id': 'b'}], 'edges': [{'source': 'a', 'target': 'b'}]}
    route = layout_edges(spec, {'a': (1.8, 4.8), 'b': (1.8, 3.0)}, family='hierarchy')[0]
    assert route[-1][1] > 3.0
    assert route[-1][1] < route[-2][1]
    assert (1.8, 3.0) not in route


def test_hierarchy_feedback_uses_external_corridor():
    spec = {'nodes': [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}, {'id': 'd'}], 'edges': [{'source': 'a', 'target': 'b'}, {'source': 'b', 'target': 'c'}, {'source': 'c', 'target': 'd'}, {'source': 'd', 'target': 'b'}]}
    positions = {'a': (1.8, 4.8), 'b': (1.8, 3.0), 'c': (4.7, 4.8), 'd': (4.7, 3.0)}
    route = layout_edges(spec, positions, family='hierarchy')[-1]
    assert min(point[1] for point in route) < 2.0
    assert route[-1] != positions['b']


def test_loop_feedback_uses_distinct_outer_corridor():
    spec = {'nodes': [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}, {'id': 'd'}], 'edges': [{'source': 'a', 'target': 'b'}, {'source': 'b', 'target': 'c'}, {'source': 'c', 'target': 'd'}, {'source': 'd', 'target': 'b'}]}
    positions = {'a': (4.0, 6.5), 'b': (6.5, 4.0), 'c': (4.0, 1.5), 'd': (1.5, 4.0)}
    route = layout_edges(spec, positions, family='loop')[-1]
    assert max(point[1] for point in route) > 7.0


def test_contract_is_compiled_before_candidate_generation(tmp_path):
    result = generate_from_text('输入 -> 可能使用验证模块 -> 输出', tmp_path, count=1, target_figure_type='architecture')
    candidate = result['candidates'][0]['spec']
    assert candidate['figure_type'] == 'architecture'
    assert all('验证模块' not in node['label'] for node in candidate['nodes'])
    assert candidate['needs_review']


def test_compile_contract_keeps_only_confirmed_edges():
    spec = {'figure_type': 'workflow', 'nodes': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}], 'edges': [{'source': 'a', 'target': 'b'}]}
    compiled = compile_spec_with_contract(spec, {'target_figure_type': 'workflow', 'optional_nodes': ['B'], 'needs_review': [{'code': 'uncertain_entity'}]})
    assert compiled['nodes'] == [{'id': 'a', 'label': 'A'}]
    assert compiled['edges'] == []


def test_contract_detects_required_direction_and_condition_mismatch():
    from figure_agent.workflow import contract_findings

    spec = {
        'nodes': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}],
        'edges': [{'source': 'a', 'target': 'b', 'type': 'data_flow'}],
        'metadata': {'figure_contract': {'required_labels': ['A', 'B'], 'required_edges': [
            {'source': 'b', 'target': 'a', 'type': 'control_flow', 'label': 'retry'}
        ]}},
    }
    findings = contract_findings(spec)
    assert any(item['code'] == 'contract_required_edge_missing' for item in findings)
