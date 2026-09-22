# RC2 语义修复状态

## 目的

本轮开发针对 RC1 独立视觉评审暴露的语义问题进行收口。评审的主要结论是：几何重叠和裁剪已经基本可控，但自然语言中的分支、循环、并行协作和阶段包含关系没有可靠地进入最终 Figure Spec，导致图形看起来整齐，却不能准确表达论文方法。

## 已实现的修复

### 1. 显式自然语言解析

新增 `src/figure_agent/prose.py`，由 `parser.parse_method_text` 在适用时调用。当前解析器覆盖：

- 具有明确时间或处理词的序列：`经过`、`先`、`后`、`随后`、`并`；
- 条件分支：`根据…分为`、`通过/失败后`、`输入为…时`；
- 并行扇出与汇合：`并行调用`、`分发给`、`共同进入`、`汇总结果`；
- 明确反馈：`回到`、`循环回到`、`返回`、`退回`；
- 阶段包含关系：以 `groups` 表达，不自动推导成员之间的数据流。

每个节点、边和分组都带有原文证据片段及字符偏移。无法唯一确定回返目标、并行汇合目标或隐式多轮关系时，解析器生成 `needs_review`，不擅自添加模块或边。

### 2. 语义安全检查

`src/figure_agent/critic.py` 增加了确定性检查：

- 明确分支但没有扇出时报告 `missing_branch_structure`；
- 明确循环/反馈但没有控制流边时报告 `missing_feedback_structure`；
- 明确并行/汇合但没有扇出或扇入时报告 `missing_parallel_structure`。

这些检查只报告缺陷，不会自动发明论文中没有证据的节点。

### 3. 回归测试

`tests/test_prose_semantics.py` 覆盖序列、分支、循环、并行扇出/扇入、阶段包含、未解析回返、歧义目标、隐式多轮和证据偏移。相关 Critic 测试位于 `tests/test_critic.py`。

## 验证结果

在当前工作区执行：

```text
python -m pytest -q
179 passed, 16 warnings
```

前端在 `frontend` 目录执行：

```text
npm run build
vite build succeeded
```

警告来自 Starlette multipart 和 httpx 的弃用提示，不是本轮新增失败。

## 证据边界

`eval_cases/visual_quality/benchmark_rc2_holdout.json` 和 `evidence/rc2-development-reviewer.zip` 是开发诊断材料。它们在本轮过程中参与了规则调试，因此**不能作为独立 RC2 盲评或发布验收证据**。对应状态记录在 `evidence/rc2-development-trial/trial-status.json`。

要完成独立验收，必须在语义规则冻结后重新生成一批措辞、案例和文件名均不同的 holdout，并且：

1. 生成阶段不再读取或调试该 holdout 的答案；
2. 匿名评测包不包含 Spec、标签映射、参考答案和评分脚本中的金标准；
3. 由独立评审按固定指标检查语义正确性、分支/循环/并行表达、箭头方向、可读性和论文版式；
4. 保存原始评分表、匿名映射、评审说明和生成版本 hash。

目前仍缺少用户所述“最新三轮的精确提示词文件”和“已评分盲评 JSON”原件。仅凭会话摘要无法逐条证明对这些文件的完全落实；如需逐项审计，应补充这两类材料。

## 当前结论

本轮已经把审查指出的四类语义结构接入主解析路径，并用回归测试锁定了保守策略。当前项目可以进入“语义冻结后的独立 holdout 评测”阶段，但尚未宣称 RC2 通过、投稿级通过或独立盲评通过。
