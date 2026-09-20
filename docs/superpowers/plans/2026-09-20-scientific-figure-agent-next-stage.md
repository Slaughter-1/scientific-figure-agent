# Scientific Figure Agent 下一阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不依赖 Figma 账号的情况下完成可测试的 Figma 场景编译器，并增加跨后端一致性检查和统一产物清单。

**Architecture:** Figure Spec 先经过统一路由，再由 Draw.io、Figma scene compiler 或 Matplotlib 后端生成产物。Figma 写入通过可选 driver 隔离；本地 mock 负责离线回归，真实 MCP 只作为运行时适配器。所有后端结果汇总到 manifest。

**Tech Stack:** Python 3.10+, 现有 Figure Spec validator、Matplotlib、Python 标准库 JSON/XML、可选 Figma MCP。

**Spec:** `docs/superpowers/specs/2026-09-20-scientific-figure-agent-next-stage.md`

## Global Constraints

- Figure Spec 是唯一语义源，后端不得重新解释论文文本。
- Figma 未连接时只能输出本地 scene JSON，并明确标记 `mock` 或 `unavailable`。
- 语义 parity 比较节点 ID、标签、边端点、分组关系和方向，不比较像素坐标。
- 任何后端执行前必须调用 `require_valid_spec`。
- 每次渲染必须产生可序列化的 `manifest.json`。

## Review Focus

- 重复 `source_id`：scene 编译必须失败并给出冲突 ID。
- 分组包含不存在节点：在编译前由 Spec validator 拒绝。
- Figma driver 未提供：仍生成 scene JSON，状态为 `unavailable`。
- 某一后端失败：manifest 保留成功后端产物和失败原因。
- Draw.io/Figma 标签不一致：parity checker 必须报告具体节点 ID。

### Task 1: 建立统一产物和后端路由

**Files:**
- Create: `src/figure_agent/artifacts.py`
- Create: `src/figure_agent/router.py`
- Test: `tests/test_artifacts.py`

**Interfaces:**
- `build_manifest(spec: dict, artifacts: dict) -> dict`
- `render_backends(spec: dict, backends: list[str], output_dir: Path) -> dict`

- [ ] 写测试：断言 manifest 包含 `spec_sha256`、`backends`、`artifacts`、`limitations`。
- [ ] 实现规范化 JSON 哈希和每个后端独立状态。
- [ ] 为 `drawio` 和 `matplotlib` 接入现有渲染器，未知后端返回结构化错误。
- [ ] 运行 `python -m pytest tests/test_artifacts.py -q`。
- [ ] 提交 `feat: add artifact manifest and backend router`。

### Task 2: 实现 Figma scene compiler 与 mock driver

**Files:**
- Create: `src/figure_agent/backends/figma_backend.py`
- Create: `tests/test_figma_backend.py`
- Create: `examples/next_stage/figma_scene.json`

**Interfaces:**
- `compile_figma_scene(spec: dict) -> dict`
- `render_figma_spec(spec: dict, output_dir: Path, driver: FigmaDriver | None = None) -> dict`
- `LocalFigmaDriver.write_scene(scene: dict) -> dict`

- [ ] 写测试：workflow Spec 生成唯一 `source_id`，包含 Frame、Text、Rectangle 和箭头节点。
- [ ] 写测试：未提供 driver 时生成 `scene.json`，状态为 `unavailable`，不出现伪造文件 ID。
- [ ] 实现方向布局、style token 映射和分组节点。
- [ ] 实现 mock driver，写入稳定 JSON 并返回 `mock` 状态。
- [ ] 运行 `python -m pytest tests/test_figma_backend.py -q`。
- [ ] 提交 `feat: add figma scene compiler and offline driver`。

### Task 3: 增加跨后端 parity checker

**Files:**
- Create: `src/figure_agent/parity.py`
- Test: `tests/test_parity.py`

**Interfaces:**
- `extract_drawio_semantics(path: Path) -> dict`
- `extract_figma_semantics(scene: dict) -> dict`
- `compare_semantics(spec: dict, artifact: dict) -> list[dict[str, str]]`

- [ ] 写测试：同一 Spec 的 Draw.io XML 和 Figma scene 返回空问题列表。
- [ ] 写测试：修改一个 Figma 标签后报告 `label_mismatch` 和节点 ID。
- [ ] 实现节点、标签、边和分组的规范化集合比较。
- [ ] 运行 `python -m pytest tests/test_parity.py -q`。
- [ ] 提交 `feat: add cross-backend semantic parity checks`。

### Task 4: 接入 CLI 和验证文档

**Files:**
- Modify: `src/figure_agent/cli.py`
- Create: `scripts/render_next_stage.py`
- Create: `docs/next-stage-report.md`
- Modify: `README.md`
- Test: `tests/test_next_stage_acceptance.py`

**Interfaces:**
- `figure-agent render --spec <path> --backend all --output-dir <path>`

- [ ] 写验收测试：固定 workflow Spec 生成 Draw.io、Matplotlib、Figma scene 和 manifest。
- [ ] 实现 CLI 参数解析和返回码：所有后端成功为 0，存在失败后端为 2，但保留成功产物。
- [ ] 运行脚本并记录未连接 Figma MCP 时的明确状态。
- [ ] 运行完整测试 `python -m pytest -q`。
- [ ] 更新 README、写验证报告并提交 `feat: expose unified render workflow`。

## 执行顺序

按 Task 1 → Task 2 → Task 3 → Task 4 顺序执行。每个任务独立通过测试后再进入下一个任务；Figma MCP 连接只在 Task 2/4 的环境允许时做真实冒烟，不阻塞本地实现。

## 自检

- 设计覆盖 Figma 原生节点、离线后备、跨后端一致性和产物追踪。
- 计划没有把真实 Figma 连接当作本地测试前置条件。
- 每个接口在设计文档和任务中使用相同名称和参数。
- 语义错误只报告，不由 Refiner 擅自删除或改写研究节点。
