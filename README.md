# Scientific Figure Agent

面向 LLM、NLP 和 Agent 论文的科研图编译器。当前仓库从 M0 可行性验证开始，使用 Figure Spec 作为跨后端的结构化表示。

## M0 快速开始

```powershell
python -m pytest -q
python scripts/check_environment.py
python scripts/render_m0_plot.py
python scripts/render_m0_drawio.py
```

示例 Figure Spec 位于 `examples/m0/workflow.json`。生成结果位于 `outputs/m0/`，M0 验证结果见 `docs/m0-report.md` 和 `docs/m0-validation-report.md`。

M1 的四类 Figure Spec 样例位于 `examples/m1/`，包括 `architecture`、`workflow`、`graph` 和 `plot`；验证结果见 `docs/m1-report.md`。

M2 提供 `figure_agent.parser.parse_method_text` 作为文本到 Figure Spec 的基线解析器，固定回归案例位于 `eval_cases/m2_cases.json`，验证结果见 `docs/m2-report.md`。

M3 提供统一的 `figure_agent.backends.drawio_backend.render_drawio_spec` 后端，可从任意合法 Figure Spec 生成可编辑 `.drawio`、`.svg` 和 `.pdf`，验证结果见 `docs/m3-report.md`。
