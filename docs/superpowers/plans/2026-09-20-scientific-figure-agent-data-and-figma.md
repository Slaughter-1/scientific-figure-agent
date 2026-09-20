# Scientific Figure Agent 数据输入与 Figma 连接层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加 CSV/JSON 到 plot Figure Spec 的可运行入口，并为真实 Figma MCP 建立不猜测 API 的 transport 注入层。

**Architecture:** 输入适配器生成标准化表格，Plot Spec Builder 根据显式列映射生成已有 Figure Spec；Figma scene compiler 通过 `FigmaTransport` 写入外部 Canvas，未连接时保留本地 scene JSON。CLI 负责路由和 manifest。

**Tech Stack:** Python 3.10+、标准库 `csv/json`、现有 Figure Spec validator、Matplotlib、可选宿主 MCP transport。

**Spec:** `docs/superpowers/specs/2026-09-20-scientific-figure-agent-data-and-figma.md`

## Global Constraints

- 输入适配器不猜测实验指标含义或单位。
- 所有 plot spec 在 Matplotlib 执行前调用 `require_valid_spec`。
- 真实 Figma 工具 schema 未验证前不编造 MCP 调用；使用 `FigmaTransport` 注入。
- transport 失败时必须保留本地 scene JSON 和错误状态。
- 现有 35 个测试必须保持通过。

## Review Focus

- CSV 中文列名和 UTF-8 BOM：应正确读取列名，不产生隐藏字符。
- JSON records 为空或第一条记录缺列：应返回具体错误。
- 数值列含空字符串：应指出列名和 1-based 行号。
- heatmap 行长度不一致：应拒绝生成图，而不是截断数据。
- Figma transport 抛错：应保留 scene 文件并返回 `error` 状态。

### Task 1: 标准化 CSV/JSON 表格输入

**Files:**
- Create: `src/figure_agent/data.py`
- Create: `tests/test_data.py`
- Create: `examples/m8/results.csv`

**Interfaces:**
- `load_table(path: str | Path, format: str | None = None) -> dict[str, Any]`

- [ ] 先写测试：CSV 返回 columns、rows、provenance，中文列名保持不变。
- [ ] 先写测试：JSON records 返回同样结构，缺少 records 数组时报具体错误。
- [ ] 运行 `python -m pytest tests/test_data.py -q`，确认在实现前失败。
- [ ] 用标准库实现 CSV/JSON 读取、BOM 清理、空文件和记录结构校验。
- [ ] 重新运行测试并确认通过。
- [ ] 提交 `feat: add csv and json table adapters`。

### Task 2: 从标准化表格构建 Plot Spec

**Files:**
- Create: `src/figure_agent/plot_planner.py`
- Create: `tests/test_plot_planner.py`
- Modify: `src/figure_agent/spec.py`（补充 plot data 字段校验）

**Interfaces:**
- `build_plot_spec(table: dict[str, Any], *, kind: str, x_column: str | None = None, y_column: str | None = None, matrix_columns: list[str] | None = None, title: str | None = None) -> dict[str, Any]`

- [ ] 先写 bar/line/scatter 的列映射测试和 provenance 断言。
- [ ] 先写 heatmap 矩形矩阵测试及不规则矩阵失败测试。
- [ ] 运行 `python -m pytest tests/test_plot_planner.py -q`，观察缺少模块的失败。
- [ ] 实现显式列映射、数值转换、长度校验、`source_columns` 和 `provenance`。
- [ ] 重新运行测试和完整 `python -m pytest -q`。
- [ ] 提交 `feat: build plot specs from normalized tables`。

### Task 3: 增加 Figma Transport 注入边界

**Files:**
- Modify: `src/figure_agent/backends/figma_backend.py`
- Modify: `src/figure_agent/router.py`
- Create: `tests/test_figma_transport.py`

**Interfaces:**
- `FigmaTransport.write_scene(scene: dict[str, Any]) -> dict[str, Any]`
- `render_figma_spec(spec, output_dir, transport=None) -> dict[str, Any]`

- [ ] 先写 mock transport 成功、transport 抛错、未提供 transport 三个测试。
- [ ] 运行目标测试确认 transport 参数尚不存在或行为不完整。
- [ ] 将现有 driver 参数改名为 transport，并保留 `LocalFigmaDriver` 兼容入口。
- [ ] 确保任何 transport 结果都不覆盖本地 scene 路径，异常转换为 `status=error`。
- [ ] 运行目标测试和完整测试。
- [ ] 提交 `feat: add injectable figma transport`。

### Task 4: 接入 plot CLI 和端到端验收

**Files:**
- Modify: `src/figure_agent/cli.py`
- Create: `tests/test_plot_cli.py`
- Create: `scripts/plot_next_stage.py`
- Create: `docs/m8-report.md`
- Modify: `README.md`

**Interfaces:**
- `figure-agent plot --input <path> --kind <kind> --x <column> --y <column> --output-dir <path>`

- [ ] 先写 CLI 成功测试：CSV 生成 plot Spec、PDF/SVG/PNG 和 manifest。
- [ ] 先写 CLI 错误测试：缺少列返回非零状态并包含列名。
- [ ] 运行目标测试确认命令尚不存在。
- [ ] 实现 `plot` 子命令和直接可运行的仓库脚本。
- [ ] 用 `examples/m8/results.csv` 执行一次真实命令，检查产物和 manifest。
- [ ] 运行完整测试并写 M8 报告。
- [ ] 提交 `feat: expose csv to plot cli workflow`。

## 执行顺序

按 Task 1 → Task 2 → Task 3 → Task 4 顺序执行。Task 1/2 完全离线；Task 3 不要求真实 Figma MCP，Task 4 的 plot CLI 验收不受 Figma 连接状态影响。

## 自检

- 设计覆盖当前最明显的两个缺口：用户不能直接从结果表开始，Figma 不能注入真实写入 transport。
- 未把未知的 Figma MCP API 写死进仓库。
- 每个任务都有明确文件、接口、失败测试和验收命令。
- 仍保留本地 SVG/PDF/scene 作为可复现证据。
