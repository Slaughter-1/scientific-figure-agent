# M2 验证报告

M2 增加了一个不依赖外部模型的文本到 Figure Spec 基线解析器，先覆盖 `architecture/workflow` 共同需要的节点和顺序关系抽取。

`figure_agent.parser.parse_method_text` 当前支持：

- 中文逗号、分号和句号分隔的阶段描述；
- `→`、`->` 和 `=>` 分隔的英文或中文工作流；
- 从显式文本中抽取模块、模型、工具、数据和存储节点；
- 以相邻阶段生成 `data_flow` 边，并在返回前执行 Figure Spec 校验。

固定回归集位于 `eval_cases/m2_cases.json`，包含 5 个 LLM/NLP/Agent 工作流案例。它用于约束后续 LLM Planner 的输出，不代表当前解析器已经具备开放域语义理解能力。

验证命令：

```powershell
python -m pytest -q
```
