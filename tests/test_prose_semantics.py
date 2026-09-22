"""Development regressions; not independent holdout or human gold labels."""
import pytest
from figure_agent.parser import parse_method_text
from figure_agent.workflow import build_figure_contract, compile_spec_with_contract


def graph(text):
    spec = parse_method_text(text)
    labels = {n['id']: n['label'] for n in spec['nodes']}
    edges = {(labels[e['source']], labels[e['target']], e['type'], e.get('label', '')) for e in spec['edges']}
    return spec, set(labels.values()), edges


@pytest.mark.parametrize(('text', 'labels'), [
    ('文本经过分词、编码后送入分类器并输出标签', ['文本', '分词', '编码', '分类器', '输出标签']),
    ('文档读取后进行切分、向量化，最后写入索引', ['文档读取', '切分', '向量化', '写入索引']),
    ('日志先清洗，再聚合事件并保存报告', ['日志', '清洗', '聚合事件', '保存报告']),
    ('样本归一化后训练分类模型，之后评估模型并保存指标', ['样本归一化', '训练分类模型', '评估模型', '保存指标']),
])
def test_sequence_retains_actions_and_exact_order(text, labels):
    spec, actual, edges = graph(text)
    assert actual == set(labels)
    assert {(a, b) for a, b, _, _ in edges} == set(zip(labels, labels[1:]))
    assert not spec['needs_review']
    for item in spec['nodes'] + spec['edges']:
        assert all(e['quote'] in text for e in item['evidence'])


@pytest.mark.parametrize(('text', 'source', 'destinations', 'conditions'), [
    ('审核通过后发布，审核失败则返回修改环节', '审核', ['发布', '修改环节'], ['通过', '失败']),
    ('验证通过才存档，验证未通过则退回修订步骤', '验证', ['存档', '修订步骤'], ['通过', '未通过']),
    ('输入为图片时走视觉编码器，输入为文本时走文本编码器', '输入', ['视觉编码器', '文本编码器'], ['图片', '文本']),
    ('路由器根据任务类别分为查询路径和计算路径', '路由器', ['查询路径', '计算路径'], ['查询路径', '计算路径']),
])
def test_conditional_arms_share_source_without_serial_arm_edge(text, source, destinations, conditions):
    spec, labels, edges = graph(text)
    assert labels == {source, *destinations}
    assert edges == {(source, dest, 'control_flow', cond) for dest, cond in zip(destinations, conditions)}
    assert not spec['needs_review']


@pytest.mark.parametrize(('text', 'source', 'children', 'join'), [
    ('协调器并行调用工具代理和评审代理，最终交给回答代理', '协调器', ['工具代理','评审代理'], '回答代理'),
    ('调度器同时调用检索器与计算器，最后交给汇总器', '调度器', ['检索器','计算器'], '汇总器'),
    ('规划代理把子任务分发给检索代理和分析代理，汇总代理合并结果', '规划代理', ['检索代理','分析代理'], '汇总代理'),
])
def test_parallel_relations_are_fan_out_and_explicit_fan_in(text, source, children, join):
    spec, labels, edges = graph(text)
    assert labels == {source, join, *children}
    assert {(a, b) for a, b, _, _ in edges} == {(source,c) for c in children} | {(c,join) for c in children}
    assert not spec['needs_review']


def test_parallel_without_join_does_not_create_one():
    spec, labels, edges = graph('控制器并行调用语音模型和视觉模型')
    assert labels == {'控制器','语音模型','视觉模型'}
    assert {(a,b) for a,b,_,_ in edges} == {('控制器','语音模型'),('控制器','视觉模型')}
    assert not spec['needs_review']


def test_fan_in_does_not_serialize_inputs():
    _, labels, edges = graph('片段和历史消息共同进入构造器，再交给语言模型')
    assert labels == {'片段','历史消息','构造器','语言模型'}
    assert {(a,b) for a,b,_,_ in edges} == {('片段','构造器'),('历史消息','构造器'),('构造器','语言模型')}


def test_containment_does_not_imply_data_flow():
    text = '训练阶段包含数据模块、编码器和解码器；推理阶段由服务模块调用编码器'
    spec, labels, edges = graph(text)
    assert labels == {'数据模块','编码器','解码器','服务模块'}
    assert {(a,b) for a,b,_,_ in edges} == {('服务模块','编码器')}
    ids = {n['id']: n['label'] for n in spec['nodes']}
    groups = {g['label']: {ids[c] for c in g['children']} for g in spec['groups']}
    assert groups == {'训练阶段': {'数据模块','编码器','解码器'}, '推理阶段': {'服务模块','编码器'}}
    assert all(g['evidence'][0]['quote'] in text for g in spec['groups'])


def test_containment_alone_has_no_edges():
    spec, labels, edges = graph('预处理阶段包含过滤模块、抽取模块和校验模块')
    assert labels == {'过滤模块','抽取模块','校验模块'}
    assert edges == set()
    assert len(spec['groups']) == 1


def test_inline_observation_return_targets_existing_stage():
    text = '规划器制定计划，工具执行计划，观察结果后回到规划器直到完成'
    spec, labels, edges = graph(text)
    assert ('观察结果','规划器制定计划','control_flow','直到完成') in edges
    assert '完成' not in labels
    assert not spec['needs_review']


@pytest.mark.parametrize('target', ['规划器', '评估器'])
def test_unknown_or_ambiguous_return_is_reviewed(target):
    text = f'规划器制定计划，规划器调整计划，观察结果后回到{target}'
    spec, labels, edges = graph(text)
    assert not any(kind == 'control_flow' for _,_,kind,_ in edges)
    assert any(i['code'] == 'unresolved_loop_target' for i in spec['needs_review'])


def test_return_mention_does_not_invent_retriever_before_query():
    spec, labels, edges = graph('问题查询知识库，若证据不足则回到检索器继续搜索')
    assert '检索器' not in labels
    assert not any(kind == 'control_flow' for _,_,kind,_ in edges)
    assert any(i['code'] == 'unresolved_loop_target' for i in spec['needs_review'])


def test_temporal_order_is_not_reversed_to_satisfy_old_gold():
    spec, labels, edges = graph('生成答案后进行事实检查，发现错误就返回生成器')
    assert ('生成答案','事实检查') in {(a,b) for a,b,_,_ in edges}
    assert ('事实检查','答案') not in {(a,b) for a,b,_,_ in edges}
    assert '生成器' not in labels
    assert spec['needs_review']


def test_multi_round_context_does_not_invent_feedback_edge():
    spec, labels, edges = graph('多轮对话中代理读取记忆、调用工具并将结果写回记忆')
    assert len(labels) >= 3
    assert not any(kind == 'control_flow' for _,_,kind,_ in edges)
    assert spec['needs_review']


def test_condition_keyword_in_data_is_not_a_loop():
    spec, labels, edges = graph('检索器，工具返回证据，生成器')
    assert '工具返回证据' in labels
    assert not any(kind == 'control_flow' for _,_,kind,_ in edges)


def test_optional_parallel_component_remains_optional():
    text = '协调器并行调用检索代理和可能使用验证代理，最终交给回答代理'
    spec = compile_spec_with_contract(parse_method_text(text), build_figure_contract(text))
    assert '检索代理' in {n['label'] for n in spec['nodes']}
    assert not any('验证代理' in n['label'] for n in spec['nodes'])
    assert spec['needs_review']


def test_unparsed_trailing_clause_is_not_silently_discarded():
    spec, labels, _ = graph('协调器并行调用检索器和计算器，随后还有一个尚未说明的处理步骤')
    assert spec['needs_review']
    assert any('处理步骤' in label for label in labels)
