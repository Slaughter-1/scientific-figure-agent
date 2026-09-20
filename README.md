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

M5 的 `figure_agent.backends.plot_backend.render_plot_spec` 支持 `bar`、`line`、`scatter` 和 `heatmap`，验证结果见 `docs/m5-report.md`。

M6 的 `figure_agent.critic` 提供结构化 Critic/Refiner，用于发现 Figure Spec 问题并执行安全的元数据修复，验证结果见 `docs/m6-report.md`。

下一阶段增加统一渲染入口：

```powershell
python scripts/render_next_stage.py render --spec examples/m0/workflow.json --backend all --output-dir outputs/next-stage
```

它会生成 Draw.io、Figma scene、可用的数据图产物和 `manifest.json`；验证结果见 `docs/next-stage-report.md`。

M7 为文本到 Figure Spec 增加节点证据溯源和轻量级图类型分类，验证结果见 `docs/m7-report.md`。

M8 支持 CSV/JSON 直接生成 Plot Spec 和图表，并提供可注入的 Figma Transport，验证结果见 `docs/m8-report.md`。

```powershell
python scripts/plot_next_stage.py plot --input examples/m8/results.csv --kind bar --x method --y accuracy --output-dir outputs/m8
```
