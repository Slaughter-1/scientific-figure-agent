"""Conservative parsing of explicit relations in Chinese method prose."""
from __future__ import annotations

import re
from typing import Any

_LIST = r'、|以及|和|与|及|或'
_RETURN = r'循环回到|回到|返回|退回|迭代到'
_SEQUENTIAL = r'系统首先|系统然后|首先|然后|随后|之后|接着|最终|最后|再'


class _Graph:
    def __init__(self, text: str):
        self.text = text
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.groups: list[dict[str, Any]] = []
        self.issues: list[dict[str, str]] = []

    def evidence(self, quote: str) -> list[dict[str, Any]]:
        start = self.text.find(quote)
        if start < 0:
            raise ValueError('Evidence must be an exact source span')
        return [{'source': 'input_text', 'quote': quote, 'start': start, 'end': start + len(quote)}]

    def node(self, label: str, quote: str) -> str:
        from .parser import _node_type

        label = label.strip()
        if label not in self.nodes:
            self.nodes[label] = {'id': f'node_{len(self.nodes)}', 'label': label,
                                 'type': _node_type(label), 'evidence': self.evidence(label if label in self.text else quote)}
        return label

    def edge(self, a: str, b: str, quote: str, *, kind: str = 'data_flow', label: str = '') -> None:
        row = {'source': self.nodes[a]['id'], 'target': self.nodes[b]['id'], 'type': kind, 'evidence': self.evidence(quote)}
        if label:
            row['label'] = label
        if row not in self.edges:
            self.edges.append(row)

    def chain(self, labels: list[str], quote: str) -> None:
        for label in labels:
            self.node(label, quote)
        for a, b in zip(labels, labels[1:]):
            self.edge(a, b, quote)

    def review(self, code: str, quote: str, target: str = '') -> None:
        self.issues.append({'code': code, 'target': target, 'quote': quote,
                            'message': 'Explicit relation cannot be resolved safely; confirm it before export.'})

    def spec(self) -> dict[str, Any]:
        return {'schema_version': '0.3', 'figure_type': 'workflow', 'title': 'Generated Workflow',
                'layout': {'direction': 'left-to-right', 'spacing': 24}, 'nodes': list(self.nodes.values()),
                'edges': self.edges, 'groups': self.groups, 'needs_review': self.issues,
                'provenance': {'source': 'input_text', 'parser': 'explicit_prose'},
                'metadata': {'source_text': self.text},
                'style': {'theme': 'academic_clean', 'colors': {'process': '#E8EEF7', 'data': '#F2F4F7'}}}


def _items(text: str) -> list[str]:
    return [part.strip() for part in re.split(_LIST, text) if part.strip()]


def _entity(text: str) -> str:
    """Normalize an entity without turning a noun-list suffix into an action."""
    from .parser import _clean_clause

    raw = re.sub(r'^(?:进入|走|调用|转到|由)', '', text.strip())
    if re.search(r'(?:模块|阶段|流程|环节)$', raw):
        value = raw
    else:
        value = _clean_clause(raw).strip()
    if value != "输入":
        value = re.sub(r"(?:两种|多种|若干)?(?:类型)?输入$", "", value).strip()
    return value


def _steps(clause: str) -> list[str]:
    """Split temporal/action cues, never split generic conjunctions into order."""
    from .parser import _clean_clause

    clause = re.sub(rf'^(?:{_SEQUENTIAL})', '', clause.strip())
    match = re.fullmatch(r'(.+?)经过(.+)', clause)
    if match:
        return [_clean_clause(match[1].strip()), *_steps(match[2])]
    match = re.fullmatch(r'(.+?)先(.+)', clause)
    if match:
        return [_clean_clause(match[1].strip()), *_steps(match[2])]
    match = re.fullmatch(r'(.+?)后(?:进行|执行|完成)?(.+)', clause)
    if match:
        return [*_steps(match[1]), *_steps(match[2])]
    # The leading 并 of 并行 is explicitly excluded. A noun list with 和/与
    # is not sufficient evidence for an ordered pipeline.
    match = re.fullmatch(r'(.+?)并(?!行)(.+)', clause)
    if match:
        return [*_steps(match[1]), *_steps(match[2])]
    if '、' in clause:
        return [step for part in clause.split('、') for step in _steps(part)]
    clause = re.sub(r'^(?:送入|交给|进入|经过|进行)', '', clause)
    clause = re.sub(r'^由', '', clause)
    return [_clean_clause(clause)] if clause else []


def _continuation_target(graph: _Graph, suffix: str, quote: str) -> tuple[str | None, str | None]:
    """Resolve one explicit ``再次/重新/继续`` action to an existing node."""
    markers = list(re.finditer(r'(?:再次|重新|继续)(?:进行|执行|完成|优化)?', suffix))
    if not markers:
        return None, None
    marker = markers[-1]
    tail = suffix[marker.end():].strip()
    if not tail:
        return None, None
    # A continuation marker inside an explicit prohibition is evidence about
    # what must not happen. Keep that evidence for review, but never turn it
    # into a positive graph edge.
    prefix = suffix[:marker.start()]
    if re.search(r'(?:禁止|不得|不要|不能|不可|严禁)\s*$', prefix):
        graph.review('negative_continuation', quote, suffix.strip())
        return None, None
    if any(separator in tail for separator in ('、', '，', ',', '并', '和', '与')):
        graph.review('ambiguous_continuation', quote, tail)
        return None, None
    action = tail.rstrip('。；;')
    labels = list(graph.nodes)
    exact = [label for label in labels if action in label or label in action]
    if not exact:
        action_chars = {char for char in action if not char.isspace()}
        exact = [label for label in labels
                 if len(action_chars) >= 2 and action_chars <= set(label)]
    if len(exact) != 1:
        graph.review('continuation_target_unresolved', quote, action)
        return None, None
    return exact[0], suffix[marker.start():marker.end() + len(action)]


def _return(graph: _Graph, sources: list[str], clause: str, quote: str, condition: str = '') -> bool:
    named = re.fullmatch(
        rf'(?:则|便|就)?(?:返回|退回|回到|循环回到|迭代到)'
        rf'(?P<target>.+?(?:模块|阶段|流程|环节))'
        rf'(?P<suffix>(?:(?:重新|再次|继续|进行|执行|完成|优化|并).*)?)', clause
    )
    if named and sources:
        target = re.sub(r'^(?:进入|走|调用|转到)', '', named['target'].strip())
        graph.node(target, quote)
        for source in sources:
            graph.edge(source, target, quote, kind='control_flow', label=condition)
        continuation, continuation_quote = _continuation_target(graph, named['suffix'], quote)
        if continuation and continuation_quote:
            graph.edge(target, continuation, continuation_quote)
        return True
    match = re.fullmatch(rf'(?:则|便|就)?(?:{_RETURN})(.+?)(?:(直到.+)|(?:继续|重新).*)?', clause)
    if not match:
        return False
    target = match[1].strip()
    matches = [label for label in graph.nodes if label == target]
    if not matches:
        matches = [label for label in graph.nodes if label.startswith(target)]
    if len(matches) != 1 or not sources:
        graph.review('unresolved_loop_target', quote, target)
    else:
        for source in sources:
            graph.edge(source, matches[0], quote, kind='control_flow', label=condition or match[2] or '')
    return True


def parse_explicit_prose(text: str) -> dict[str, Any] | None:
    if re.search(r'→|->|=>', text):
        return None
    from .parser import _clean_clause

    clauses = [m.group().strip() for m in re.finditer(r'[^，,；;。\n]+', text) if m.group().strip()]
    if not clauses:
        return None
    graph = _Graph(text)
    previous: list[str] = []
    changed = False
    branch_source: str | None = None
    branch_anchor: str | None = None
    parallel_pending = False
    branch_pending = False
    branch_arms: list[str] = []
    pending_condition = ''
    pending_branch_condition = ''
    for index, clause in enumerate(clauses):
        if pending_branch_condition:
            branch_arm = re.fullmatch(r'(?:则|便|就)(?:进入|走|调用|转到|继续|执行|进行|处理)(.+)', clause)
            if branch_arm and previous:
                source = previous[-1]
                target = graph.node(_entity(branch_arm[1]), clause)
                graph.edge(source, target, clause, kind='control_flow', label=pending_branch_condition)
                previous, changed, branch_pending, branch_arms, branch_anchor = [], True, True, [target], source
                pending_branch_condition = ''
                continue
            pending_branch_condition = ''
        if branch_pending:
            else_arm = re.fullmatch(r'(?:否则|不满足时|否则则)(?:进入|走|调用|转到|继续|执行|进行|处理)?(.+)', clause)
            if else_arm and branch_anchor:
                target = graph.node(_entity(else_arm[1]), clause)
                graph.edge(branch_anchor, target, clause, kind='control_flow', label='否则')
                branch_arms.append(target)
                previous, branch_pending, branch_anchor = [target], False, None
                changed = True
                continue
            # A branch continuation is only joined when the source explicitly
            # names the merge. A bare next sentence remains review-only and
            # must not receive guessed edges from every branch arm.
            join = re.fullmatch(
                rf'(?:{_SEQUENTIAL})?(?:(?:两路|两支|二者|各路|这些路径|这些分支)(?:随后|最终)?(?:共同)?|(?:随后|最终)?(?:共同)?)'
                rf'(?:汇合|合并|汇总|进入|交给)(?:为|到|至)?(.+)',
                clause,
            )
            status_arm = re.fullmatch(r'(.+?)(未通过|通过|失败)(?:后|才|则)(?:返回|退回|走)?(.+)', clause)
            if join and branch_arms:
                target = _entity(join[1])
                graph.node(target, clause)
                for arm in branch_arms:
                    graph.edge(arm, target, clause)
                previous, branch_pending, branch_arms, branch_anchor = [target], False, [], None
                changed = True
                continue
            # Consecutive success/failure clauses form one explicit branch;
            # defer the ambiguity check until the first non-arm clause.
            if status_arm:
                pass
            else:
                graph.review('unresolved_branch_join', clause)
                previous, branch_pending, branch_arms = [], False, []
                # Do not turn the ambiguous tail into a new process node.
                # The source does not say which branch reaches it.
                changed = True
                continue
        # Capability/list statements describe membership, not a data-flow
        # sequence. Preserve the items as a group so "图像、文本两种输入"
        # cannot become 图像 -> 文本两种输入.
        supported = re.fullmatch(r"(.+?)(?:支持|提供|接受)(.+?)(?:两种|多种|若干)?(?:类型)?(?:输入|模态)", clause)
        if supported:
            children = [_entity(item) for item in _items(supported[2])]
            children = [item for item in children if item]
            if len(children) >= 2:
                for child in children:
                    graph.node(child, clause)
                graph.groups.append({'id': f'group_{len(graph.groups)}', 'label': '输入类型',
                                     'children': [graph.nodes[c]['id'] for c in children],
                                     'evidence': graph.evidence(clause)})
                previous, changed = [], True
                continue

        # Phase membership and explicitly stated invocation are different
        # relations; never chain siblings or adjacent phases.
        member = re.fullmatch(r'(.+?(?:阶段|系统|平台))(?:包含|包括)(.+)', clause)
        invoke = re.fullmatch(r'(.+?阶段)由(.+?)调用(.+)', clause)
        if member or invoke:
            match = member or invoke
            children = _items(match[2]) if member else [match[2].strip(), match[3].strip()]
            for child in children:
                graph.node(child, clause)
            graph.groups.append({'id': f'group_{len(graph.groups)}', 'label': match[1],
                                 'children': [graph.nodes[c]['id'] for c in children], 'evidence': graph.evidence(clause)})
            if invoke:
                graph.edge(children[0], children[1], clause, kind='dependency')
            previous, changed = [], True
            continue

        negated = re.fullmatch(r'(.+?)(?:不会|不|未|没有|不得|不可|不能|不应|不允许|禁止)(?:并行|同时)?调用(.+)', clause)
        if negated:
            source = graph.node(_entity(negated[1]), clause)
            children = [_entity(item) for item in _items(negated[2])]
            for child in children:
                if child:
                    graph.node(child, clause)
            graph.review('negated_relation', clause, source)
            previous, changed = [], True
            continue

        parallel = re.fullmatch(r'(.+?)(?:(?:并行|同时)调用|把.+?(?:分发|派)给)(.+)', clause)
        if parallel and len(_items(parallel[2])) >= 2:
            source = graph.node(_entity(parallel[1]), clause)
            for prior in previous:
                graph.edge(prior, source, text)
            children = [_entity(item) for item in _items(parallel[2])]
            for child in children:
                graph.node(child, clause)
                graph.edge(source, child, clause)
            previous, changed, parallel_pending = children, True, True
            continue

        parallel_subjects = re.fullmatch(r'(.+?)(?:和|与)(.+?)分别处理(.+?)(?:与|和)(.+)', clause)
        parallel_actions = re.fullmatch(r'(.+?)(?:分别执行|分别进行)(.+?)(?:和|与)(.+)', clause)
        parallel_enter = re.fullmatch(r'(.+?)后分别进入(.+?)(?:和|与)(.+)', clause)
        if parallel_subjects:
            subjects = [_entity(parallel_subjects[1]), _entity(parallel_subjects[2])]
            for subject in subjects:
                graph.node(subject, clause)
                for prior in previous:
                    graph.edge(prior, subject, text)
            previous, changed, parallel_pending = subjects, True, True
            continue
        if parallel_actions:
            source = graph.node(_entity(parallel_actions[1]), clause)
            actions = [_entity(parallel_actions[2]), _entity(parallel_actions[3])]
            for action in actions:
                graph.node(action, clause)
                graph.edge(source, action, clause)
            previous, changed, parallel_pending = actions, True, True
            continue
        if parallel_enter:
            source = graph.node(_entity(parallel_enter[1]), clause)
            for prior in previous:
                if prior != source:
                    graph.edge(prior, source, clause)
            actions = [_entity(parallel_enter[2]), _entity(parallel_enter[3])]
            for action in actions:
                graph.node(action, clause)
                graph.edge(source, action, clause)
            previous, changed, parallel_pending = actions, True, True
            continue

        fan_in = re.fullmatch(r'(.+?)(?:共同|一起)进入(.+)', clause)
        if fan_in and len(_items(fan_in[1])) >= 2:
            target = graph.node(fan_in[2], clause)
            for source in _items(fan_in[1]):
                graph.node(source, clause)
                graph.edge(source, target, clause)
            previous, changed = [target], True
            continue

        if parallel_pending:
            merge_then = re.fullmatch(r'(?:结果)?汇合后(?:进行|执行|完成)?(.+)', clause)
            if merge_then:
                merged = graph.node('结果汇合', clause)
                for source in previous:
                    graph.edge(source, merged, clause)
                target = graph.node(_entity(merge_then[1]), clause)
                graph.edge(merged, target, clause)
                previous, parallel_pending = [target], False
                changed = True
                continue
            fusion = re.fullmatch(r'(?:随后|之后)(.+?)(?:合并|汇总|融合)(.+)', clause)
            if fusion:
                target = graph.node(_entity(fusion[1]), clause)
                for source in previous:
                    graph.edge(source, target, clause)
                result_match = re.search(r'(?:并)?(?:生成|输出)(.+)', fusion[2])
                if result_match:
                    result = graph.node(_entity(result_match[1]), clause)
                    graph.edge(target, result, clause)
                    previous = [result]
                else:
                    previous = [target]
                parallel_pending = False
                changed = True
                continue
            join = re.fullmatch(rf'(?:{_SEQUENTIAL})?(?:交给|汇入)(.+)', clause)
            aggregate = re.fullmatch(r'(.+?)(?:合并|收集|汇总)(?:两者|各代理|所有)?.*结果', clause)
            if join or aggregate:
                target = graph.node((join or aggregate)[1], clause)
                for source in previous:
                    graph.edge(source, target, text)
                previous, parallel_pending = [target], False
                continue
            graph.review('unresolved_parallel_join', clause)
            previous, parallel_pending = [], False

        split = re.fullmatch(r'(.+?)(?:根据|依据).+?(?:分为|选择)(.+)', clause)
        if split and len(_items(split[2])) >= 2:
            source = graph.node(_entity(split[1]), clause)
            for prior in previous:
                graph.edge(prior, source, text)
            targets = [_entity(item) for item in _items(split[2])]
            for target in targets:
                graph.node(target, clause)
                graph.edge(source, target, clause, kind='control_flow', label=target)
            # A following action does not say which arm reaches it, or
            # whether all arms merge. Keep it review-only instead of guessing.
            previous, changed, branch_pending, branch_arms, branch_anchor = [], True, True, targets, source
            continue

        explicit_branch = re.fullmatch(
            r'(?:若|如果|当)(.+?)(?:则|便|就)(?:进入|走|调用|转到|继续|执行|进行|处理)(.+)', clause
        )
        if explicit_branch and previous:
            source = previous[-1]
            target = graph.node(_entity(explicit_branch[2]), clause)
            graph.edge(source, target, clause, kind='control_flow', label=explicit_branch[1].strip())
            previous, changed, branch_pending, branch_arms, branch_anchor = [], True, True, [target], source
            continue
        explicit_condition_route = re.fullmatch(r'(?:根据|依据)(.+?)(?:进入|选择)(.+)', clause)
        if explicit_condition_route and previous:
            target = graph.node(_entity(explicit_condition_route[2]), clause)
            graph.edge(previous[-1], target, clause, kind='control_flow', label=explicit_condition_route[1].strip())
            previous, changed = [target], True
            continue
        explicit_transition = re.fullmatch(r'(.+?)进入(.+)', clause)
        if (explicit_transition and '后' not in explicit_transition[1]
                and not any(token in clause for token in ('、', '并'))):
            stages = [_entity(explicit_transition[1]), _entity(explicit_transition[2])]
            graph.chain(stages, clause)
            for source in previous:
                if source != stages[0]:
                    graph.edge(source, stages[0], clause)
            previous, changed = [stages[-1]], True
            continue
        branch_condition = re.fullmatch(r'(?:若|如果|当)(.+)', clause)
        if (branch_condition and index + 1 < len(clauses)
                and re.fullmatch(r'(?:则|便|就)(?:进入|走|调用|转到|继续|执行|进行|处理).+', clauses[index + 1])):
            pending_branch_condition = branch_condition[1].strip()
            changed = True
            continue

        status = re.fullmatch(r'(.+?)(未通过|通过|失败)(?:后|才|则)(?:返回|退回|走)?(.+)', clause)
        modality = re.fullmatch(r'(.+?)(?:为|是)(.+?)时(?:走|经过)(.+)', clause)
        if status or modality:
            match = status or modality
            source, condition, target = _entity(match[1]), match[2].strip(), _entity(match[3])
            graph.node(source, clause)
            graph.node(target, clause)
            graph.edge(source, target, clause, kind='control_flow', label=condition)
            # A subsequent bare clause after two status arms does not identify
            # a merge. Keep the arm targets only for an explicit join phrase;
            # otherwise the next iteration records review without inventing a node.
            if status:
                branch_arms.append(target)
                branch_pending = True
                branch_anchor = source
            previous, changed = [], True
            continue

        decision = re.fullmatch(r'.*?(判断.+)', clause)
        arm = re.fullmatch(r'(.+?)(?:调用|走)(.+)', clause)
        if decision and index + 1 < len(clauses) and re.fullmatch(r'(.+?)(?:调用|走)(.+)', clauses[index + 1]):
            branch_source = graph.node(decision[1], clause)
            for source in previous:
                graph.edge(source, branch_source, text)
            previous, changed = [], True
            continue
        if arm and branch_source:
            target = graph.node(arm[2], clause)
            graph.edge(branch_source, target, text, kind='control_flow', label=arm[1])
            continue
        branch_source = None

        # A final output cue is temporal sequence, not a loop return.  Handle it
        # before the generic ``<stage>后返回...`` observation rule.
        final_return = re.fullmatch(r'(?:最后|最终)(?:返回|输出|生成|发布)(.+)', clause)
        if final_return:
            stages = [_entity(final_return[1])]
            graph.chain(stages, clause)
            for source in previous:
                graph.edge(source, stages[0], clause)
            previous, changed = stages, True
            continue

        # Conditions and observation actions are parsed before sequence cues.
        conditional = re.fullmatch(rf'((?:若|如果|当).+?|.+?(?:失败|错误))(?:则|便|就)?((?:{_RETURN}).+)', clause)
        observation = re.fullmatch(rf'(.+?)后((?:{_RETURN}).+)', clause)
        if conditional:
            _return(graph, previous, conditional[2], clause, conditional[1].rstrip('则便就'))
            previous, changed = [], True
            continue
        condition_return = re.fullmatch(rf'(.+?)时((?:{_RETURN}).+)', clause)
        if condition_return:
            _return(graph, previous, condition_return[2], clause, condition_return[1])
            previous, changed = [], True
            continue
        if observation:
            stages = _steps(observation[1])
            graph.chain(stages, clause)
            for source in previous:
                graph.edge(source, stages[0], text)
            _return(graph, stages[-1:], observation[2], clause)
            previous, changed = [], True
            continue
        if re.match(r'^(?:若|如果|当)', clause) and index + 1 < len(clauses) and re.match(rf'^(?:则)?(?:{_RETURN})', clauses[index + 1]):
            pending_condition = clause
            continue
        if _return(graph, previous, clause, text if pending_condition else clause, pending_condition):
            previous, changed, pending_condition = [], True, ''
            continue

        if re.search(r'若|如果|否则|并行|同时|包含|包括|回到|直到|根据|依据', clause):
            graph.review('unparsed_structure', clause)
            previous = []
            changed = True
            stages = [clause]
        elif re.match(r'^(?:用户问题|生成器|检索器|工具|规划器|回答器|回答代理|协调器)', clause) and not re.search(r'送入|进入|并输出|并保存|后进行|之后', clause):
            # Preserve a named actor's compound operation as one explicit
            # stage (e.g. "生成器综合证据后输出答案"). Splitting it would
            # invent intermediate data nodes that the source does not name.
            stages = [_clean_clause(clause)]
        else:
            stages = _steps(clause)
        changed = changed or len(stages) > 1
        graph.chain(stages, clause)
        for source in previous:
            graph.edge(source, stages[0], text)
        previous = stages[-1:]

    if '多轮' in text and not any(e['type'] == 'control_flow' for e in graph.edges):
        graph.review('implicit_iteration_unresolved', text)
        changed = True
    return graph.spec() if changed else None
