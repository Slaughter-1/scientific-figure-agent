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

## M9–M15 端到端工作流

当前版本提供统一请求协议、论文段落 Figure Contract、开放许可优先的模板目录、组件提示词包、三候选生成、素材组装、视觉检查和评测接口。常用 CLI：

```powershell
figure-agent analyze --input method.md
figure-agent search-templates --query "LLM agent architecture"
figure-agent generate --input method.md --output-dir outputs/generated --candidates 3
figure-agent plot --input results.csv --kind bar --x method --y accuracy --output-dir outputs/plot
figure-agent package --spec outputs/generated/candidate_01/figure-spec.json --output-dir outputs/components
figure-agent assemble --spec figure.json --assets assets --output outputs/assembled.json
figure-agent inspect --artifact outputs/generated/candidate_01/figure.svg
```

`generate` 会保存 `figure-contract.json`、三个候选目录、候选评分和模板引用；`package` 会生成 `component-manifest.json` 与 `component-prompts.md`；`inspect` 会附带结构化视觉检查结果。模板目录当前使用可审计的官方/项目内记录，未确认许可证的资源不会进入 `open_license_first` 结果。Figma 未连接时仍输出本地 `figure.figma-scene.json`，连接状态由 manifest 标记。

阶段验收与限制见 [`docs/m9-m15-report.md`](docs/m9-m15-report.md)。

公开 LLM/Agent 论文评测集见 [`docs/public-corpus-report.md`](docs/public-corpus-report.md)，当前包含 12 个官方论文/仓库案例，覆盖工具调用、RAG、Agent planning、多智能体和可解释性。
