# Scientific Figure Agent Visual Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将当前可运行的 Figure Spec 原型升级为一个能正确显示中文、生成有明确审美差异的候选方案、支持证据审阅并导出可编辑科研图的本地 Web 产品。

**Architecture:** Figure Spec 继续作为唯一语义源。新增独立的视觉样式层和布局层，把同一份语义 Spec 投影为 editorial pipeline、swimlane、loop/hierarchy 三类候选；Draw.io 保存可编辑源，Matplotlib/SVG 提供稳定预览，Web UI 展示候选、证据、许可证和审阅操作。后续 LLM、模板检索和 Figma 都通过已有 provider/transport 接口接入，不把外部 API 写进核心渲染器。

**Tech Stack:** Python 3.10+, FastAPI, SQLite, Matplotlib, Draw.io XML, React + Vite, pytest, 本地字体回退（Noto Sans SC / Microsoft YaHei / SimHei）。

**Spec:** docs/superpowers/specs/2026-09-20-scientific-figure-agent-design.md

## Global Constraints

- Figure Spec 是唯一语义源；视觉样式只能增加布局和装饰属性，不能增加论文中没有证据的研究模块。
- 默认输出 SVG、PDF、PNG、Draw.io；SVG/PDF 必须保留可复制或可编辑的文本。
- 中文和英文都必须可渲染；字体缺失时必须返回明确的 fallback 状态。
- 未验证许可证的模板或用户素材不能被标记为 publish_ready。
- 三个候选必须在布局家族、视觉层级或信息组织上存在可解释差异，不能只改变颜色或方向。
- 旧有 92 个测试必须保持通过；任何自动精修不得删除、合并或改写语义节点。
- Figma 未连接时继续生成本地 scene、Draw.io 和 SVG/PDF/PNG，不伪造远程文件标识。

## Review Focus

- 中文节点、中文标题和中文坐标标签在 SVG、PDF、浏览器预览中都应正常显示；由 Task 1 和 Task 3 的 CJK 回归测试覆盖。
- 含循环或分支的 Agent 方法图不能被排成一条线；由 Task 2 的 loop/branch fixture 覆盖。
- 三候选不能只是同一张图换颜色；由 Task 2 的结构指纹和布局家族测试覆盖。
- 无证据节点不能自动进入最终稿；由 Task 4 的 contract、review action 和导出阻断测试覆盖。
- 许可证不完整的模板和素材不能进入默认导出；由 Task 6 的 manifest 和导出门禁测试覆盖。

---

## 产品分阶段目标

### P0：视觉质量修复（当前下一步，优先级最高）

完成字体、版式、候选差异和 Web 预览闭环。用户输入一段中文或英文方法描述后，能看到三张明显不同、可读、可下载的 SVG/PDF/Draw.io 候选。

### P1：证据审阅闭环

让用户在候选页查看每个节点和边来自哪一段文字，确认、删除或标记需要证据；语义修改写入版本和 review action。

### P2：数据图与模板协作

补齐多系列实验图、误差线、单位、显著性标记，并将模板搜索、许可证登记和用户组件上传接入任务目录。

### P3：连接层和评测

接入真实 Figma transport（如果存在连接），建立 20–30 个公开论文案例的结构、视觉和导出评测，达到可发布的本地产品质量门槛。

---

### Task 1: 建立统一视觉样式和布局接口

**Files:**
- Create: src/figure_agent/visual_styles.py
- Create: src/figure_agent/layouts.py
- Modify: src/figure_agent/spec.py
- Modify: src/figure_agent/backends/drawio_backend.py
- Modify: src/figure_agent/backends/plot_backend.py
- Test: tests/test_visual_styles.py
- Test: tests/test_layouts.py

**Interfaces:**
- get_visual_style(variant: str, *, language: str = "auto", paper_width: str = "double_column") -> dict[str, Any]
- layout_nodes(spec: dict[str, Any], *, family: str) -> dict[str, tuple[float, float]]
- available_layout_families(figure_type: str, has_cycle: bool, has_branch: bool) -> list[str]
- resolve_font_family(language: str) -> tuple[str, list[str]]

- [ ] **Step 1: 写失败测试。** 在 tests/test_visual_styles.py 中断言 editorial、swimlane、loop 返回不同的 layout_family、节点尺寸、边样式和颜色 token；在缺少字体名称时断言 resolve_font_family("zh") 返回 Noto Sans SC 作为首选并包含 Windows fallback。
- [ ] **Step 2: 写失败测试。** 在 tests/test_layouts.py 中建立四节点线性图、带分支图和带回边图，分别断言 pipeline、swimlane、loop 布局的位置不相同，loop 的回边端点不会覆盖节点中心。
- [ ] **Step 3: 实现样式 token。** 在 visual_styles.py 中定义 academic_clean 的字体、字号、背景、边框、箭头、节点色和分组色；至少实现 editorial、swimlane、loop、hierarchy 四个视觉族。样式函数只能返回 JSON 可序列化字典。
- [ ] **Step 4: 实现布局族。** 在 layouts.py 中实现横向 pipeline、阶段 swimlane、反馈 loop 和分支 hierarchy。布局只消费已有节点、边、groups，不创建语义节点；为每个节点返回中心坐标，并给边返回可选的 route points。
- [ ] **Step 5: 接入两个渲染后端。** drawio_backend.py 使用样式 token 生成可编辑 XML；Matplotlib 使用 FancyArrowPatch、分组背景和方向对应的连接点，避免所有边都从左右中心直穿。所有文字设置 svg.fonttype="none" 和 pdf.fonttype=42。
- [ ] **Step 6: 运行测试。** 运行 python -m pytest tests/test_visual_styles.py tests/test_layouts.py tests/test_drawio_output.py tests/test_plot_backend.py -q，预期全部通过；再运行 python -m compileall -q src tests。
- [ ] **Step 7: 提交。** git add src/figure_agent/visual_styles.py src/figure_agent/layouts.py src/figure_agent/spec.py src/figure_agent/backends tests/test_visual_styles.py tests/test_layouts.py；git commit -m "feat: add visual style and layout families"。

### Task 2: 生成真正不同的三候选方案

**Files:**
- Modify: src/figure_agent/candidates.py
- Modify: src/figure_agent/critic.py
- Modify: src/figure_agent/visual_critic.py
- Modify: src/figure_agent/app/api.py
- Test: tests/test_candidates.py
- Test: tests/test_visual_critic.py

**Interfaces:**
- generate_candidates(spec, output_dir, *, count=3, templates=None) -> list[dict[str, Any]]
- 每个候选新增 design：family、rationale、best_for、tradeoffs。
- 每个候选新增 preview_fingerprint：node_positions、edge_routes、style_variant。
- critique_spec 和 critique_artifact 返回 design_family、finding_code、severity、message。

- [ ] **Step 1: 写失败测试。** 对同一份包含分支和循环的 Spec 生成三个候选，断言候选分别使用 editorial、swimlane、loop 或 hierarchy，且至少两个候选的节点坐标和边路线不同；断言每个候选包含 rationale 和 tradeoffs。
- [ ] **Step 2: 写失败测试。** 对纯线性流程断言仍生成三个候选，但候选 3 自动降级为 hierarchy 或 swimlane，并在 design.tradeoffs 记录“线性流程不需要反馈回路”。
- [ ] **Step 3: 实现候选规划。** 根据 figure_type、是否存在分支、是否存在回边、节点数量和 paper_width 选择视觉族；候选 1 追求语义完整，候选 2 追求论文版式，候选 3 追求视觉层级。候选规划不得修改 nodes、edges 的语义字段。
- [ ] **Step 4: 实现结构指纹和评分。** 把布局坐标、边路线、样式族写入候选 JSON；评分增加 layout_distinctiveness、visual_readability 和 semantic_preservation，并在评审页面显示评分来源。
- [ ] **Step 5: 增加无语义风险的视觉 Critic。** 检查节点重叠、文本溢出、画布越界、边穿过文字、循环路线覆盖节点和三候选相似度；自动修复只移动节点、扩大画布或调整字号。
- [ ] **Step 6: 运行测试并生成样例。** 运行 python -m pytest tests/test_candidates.py tests/test_visual_critic.py -q；用中文 Agent Loop fixture 生成 outputs/visual-candidates/candidate_01..03，检查每个目录包含 Draw.io、SVG、PDF 和 candidate.json。
- [ ] **Step 7: 提交。** git add src/figure_agent/candidates.py src/figure_agent/critic.py src/figure_agent/visual_critic.py src/figure_agent/app/api.py tests/test_candidates.py tests/test_visual_critic.py；git commit -m "feat: generate distinct visual candidates"。

### Task 3: 修复 Web 预览和中文交互体验

**Files:**
- Modify: frontend/src/main.jsx
- Modify: frontend/src/styles.css
- Modify: src/figure_agent/app/api.py
- Modify: tests/test_web_api.py
- Create: frontend/src/preview.js
- Test: tests/test_web_static_assets.py

**Interfaces:**
- GET /api/tasks/{task_id}/candidates 返回可访问的 svg、pdf、drawio URL 以及 design、scores、review_findings。
- 前端组件：CandidateCard、EvidencePanel、ScoreBar、ArtifactLinks。
- resolvePreview(artifacts) -> { url: string, type: "svg" | "png" | "none" }。

- [ ] **Step 1: 写失败测试。** 在 tests/test_web_static_assets.py 中用 FastAPI TestClient 检查 / 返回 HTML、模块脚本为 application/javascript、CSS 为 text/css；检查带中文候选的 SVG 文件 URL 可以返回 UTF-8 内容。
- [ ] **Step 2: 写失败测试。** 在 tests/test_web_api.py 中检查候选 JSON 含 design.family、design.rationale、SVG/PDF/Draw.io 下载地址和结构评分。
- [ ] **Step 3: 实现预览解析。** 新增 frontend/src/preview.js，优先显示 PNG，缺失时显示 SVG，并在加载失败时显示明确的“预览不可用，但可下载源文件”状态，不把失败图片渲染成空白卡片。
- [ ] **Step 4: 重写候选卡片。** main.jsx 增加视觉族标签、适用场景、取舍说明、证据覆盖率、结构/视觉评分、SVG/PDF/Draw.io 下载链接和选择按钮；标题、按钮、错误信息统一使用中英文可显示的系统字体。
- [ ] **Step 5: 改善布局。** styles.css 增加宽屏三列、移动端单列、浅色画布、候选标签、评分条和错误状态；中文文本使用 Noto Sans SC、Microsoft YaHei、sans-serif。
- [ ] **Step 6: 构建验证。** 运行 npm run build，再运行 python -m pytest tests/test_web_static_assets.py tests/test_web_api.py -q；用浏览器打开 http://127.0.0.1:8765/ 验证中文标题和三张候选预览均可见。
- [ ] **Step 7: 提交。** git add frontend src/figure_agent/app/api.py tests/test_web_api.py tests/test_web_static_assets.py；git commit -m "feat: add candidate review web interface"。

### Task 4: 建立 Figure Contract 与证据审阅闭环

**Files:**
- Modify: src/figure_agent/parser.py
- Modify: src/figure_agent/workflow.py
- Modify: src/figure_agent/critic.py
- Modify: src/figure_agent/app/store.py
- Modify: src/figure_agent/app/api.py
- Modify: frontend/src/main.jsx
- Test: tests/test_parser.py
- Test: tests/test_critic.py
- Test: tests/test_web_api.py

**Interfaces:**
- build_figure_contract(text: str, *, target_figure_type: str | None = None) -> dict[str, Any]
- extract_evidence(text: str, entity: str) -> list[dict[str, Any]]
- POST /api/tasks/{task_id}/review-actions 支持 confirm_node、remove_node、mark_needs_evidence、lock_node、select_candidate。
- review action 统一字段：action、target、reason、approved_by、created_at、base_version。

- [ ] **Step 1: 写失败测试。** 对包含“可能”“可选”“未来工作”等不确定措辞的段落，断言相关实体进入 needs_review，且不进入 required_nodes；对明确出现的模块断言保留 quote、段落索引和置信度。
- [ ] **Step 2: 写失败测试。** 对 remove_node、mark_needs_evidence 和 lock_node 记录 review action，导出前检查未处理的严重证据问题并阻止 publish_ready。
- [ ] **Step 3: 实现句子分类和证据抽取。** 在现有规则解析器前增加事实句、方法句、结果句、约束句分类；LLM Provider 可选，规则路径必须可独立运行；每个节点、边和组保留来源位置。
- [ ] **Step 4: 实现版本化审阅。** TaskStore 为每次语义 review action 生成新版本，不覆盖旧 Spec；候选选择、节点锁定和证据确认写入 SQLite 与任务 manifest。
- [ ] **Step 5: 实现前端证据面板。** 点击节点或 finding 时显示原文引用、位置、置信度和允许的动作；语义删除必须有 reason，布局自动修正不要求用户确认。
- [ ] **Step 6: 运行测试。** python -m pytest tests/test_parser.py tests/test_critic.py tests/test_web_api.py -q，并确认旧测试全部通过。
- [ ] **Step 7: 提交。** git add src/figure_agent/parser.py src/figure_agent/workflow.py src/figure_agent/critic.py src/figure_agent/app frontend/src/main.jsx tests；git commit -m "feat: add evidence review workflow"。

### Task 5: 完善 CSV/JSON 数据图的投稿级输出

**Files:**
- Modify: src/figure_agent/data.py
- Modify: src/figure_agent/plot_planner.py
- Modify: src/figure_agent/backends/plot_backend.py
- Modify: src/figure_agent/spec.py
- Modify: frontend/src/main.jsx
- Test: tests/test_data.py
- Test: tests/test_plot_planner.py
- Test: tests/test_plot_backend.py

**Interfaces:**
- normalize_table(content: str | bytes, *, format: str) -> dict[str, Any]
- build_plot_spec(table: dict[str, Any], *, kind: str, x: str, y: list[str], error: list[str] | None = None, unit: str | None = None, significance: str | None = None) -> dict[str, Any]
- render_plot_spec(spec, output_dir, stem) -> dict[str, Path]

- [ ] **Step 1: 写失败测试。** 覆盖多系列、误差线、单位、显著性标记、热图和分组轴；错误列长度、非数值列和空组必须返回可读的 422/ValueError。
- [ ] **Step 2: 扩展 Plot Spec 0.3。** 保存原始文件 SHA-256、列名、列类型、每个系列的列 provenance、单位、误差类型和显著性来源。
- [ ] **Step 3: 实现渲染。** Matplotlib 使用中文字体回退、论文字号、色盲友好调色板、图例和单位；误差线和显著性标记不能遮挡主数据；SVG/PDF 保留文本。
- [ ] **Step 4: 接入三候选。** 数据图候选分别使用 grouped bars、dot/interval、heatmap 或 small multiples，候选 JSON 记录图形取舍；不能把同一系列仅换颜色作为独立候选。
- [ ] **Step 5: 运行测试和样例。** python -m pytest tests/test_data.py tests/test_plot_planner.py tests/test_plot_backend.py -q；生成一份中文多系列 CSV 样例并检查 SVG/PDF 标签和单位。
- [ ] **Step 6: 提交。** git add src/figure_agent/data.py src/figure_agent/plot_planner.py src/figure_agent/backends/plot_backend.py src/figure_agent/spec.py frontend/src/main.jsx tests；git commit -m "feat: improve multi-series scientific plots"。

### Task 6: 模板、组件和许可证协作

**Files:**
- Modify: src/figure_agent/templates.py
- Modify: src/figure_agent/components.py
- Modify: src/figure_agent/artifacts.py
- Modify: src/figure_agent/app/api.py
- Modify: src/figure_agent/app/store.py
- Create: src/figure_agent/license.py
- Test: tests/test_template_catalog.py
- Test: tests/test_components.py
- Test: tests/test_artifacts.py

**Interfaces:**
- TemplateRecord：id、source_url、license、license_evidence_url、editable、supported_types、style_tags、components、restrictions、retrieved_at、approval_status。
- search_templates(query: str, *, policy: str, limit: int = 3) -> list[TemplateRecord]
- build_component_request(spec: dict, missing_roles: list[str]) -> dict[str, Any]
- register_asset(path: Path, *, source: str, license: str | None, editable: bool) -> dict[str, Any]
- check_export_license(manifest: dict) -> list[dict[str, str]]

- [ ] **Step 1: 写失败测试。** 未验证许可证的模板状态必须为 review_required；默认导出只能接受 verified、project_owned 或用户明确确认的素材；每个素材必须包含 SHA-256、MIME、大小和可编辑性。
- [ ] **Step 2: 实现白名单目录。** 先接入 draw.io 官方、Mermaid 官方、明确开源许可证的 GitHub 仓库和本地模板目录；网络结果先落地为 TemplateRecord，不直接下载网页图片进入图中。
- [ ] **Step 3: 实现组件协作包。** 对缺少的视觉角色生成 component-manifest.json、component-prompts.md、尺寸/颜色/透明背景要求和节点映射；上传 SVG、PNG、PDF、Draw.io、Figma JSON 后注册 AssetManifest。
- [ ] **Step 4: 接入导出门禁。** manifest 写入模板来源、许可证证据 URL、获取时间、用户确认和限制；存在 review_required 时导出仍可提供审阅包，但不能标记 publish_ready。
- [ ] **Step 5: 运行测试。** python -m pytest tests/test_template_catalog.py tests/test_components.py tests/test_artifacts.py -q。
- [ ] **Step 6: 提交。** git add src/figure_agent/templates.py src/figure_agent/components.py src/figure_agent/artifacts.py src/figure_agent/app src/figure_agent/license.py tests；git commit -m "feat: add auditable templates and assets"。

### Task 7: Figma 连接、端到端评测和发布门槛

**Files:**
- Modify: src/figure_agent/backends/figma_backend.py
- Modify: src/figure_agent/figma_handoff.py
- Modify: src/figure_agent/router.py
- Create: scripts/build_evaluation_report.py
- Create: eval_cases/visual_quality/
- Modify: README.md
- Create: docs/visual-product-report.md
- Test: tests/test_figma_handoff.py
- Test: tests/test_evaluation.py
- Test: tests/test_overall_cli.py

**Interfaces:**
- push_candidate_to_figma(task_id: str, candidate_id: str, transport: FigmaTransport) -> dict[str, Any]
- evaluate_case(case_dir: Path) -> dict[str, float | int | str]
- build_evaluation_report(results: list[dict[str, Any]], output: Path) -> Path

- [ ] **Step 1: 写失败测试。** Figma unavailable 时返回 unavailable 和本地 scene；mock transport 返回 file/frame 标识；真实 transport 失败时保留 scene、错误和 manifest。
- [ ] **Step 2: 接入候选选择。** 新增 CLI figure-agent push-figma --task ... --candidate ... 和 API 路由，返回文件/Frame 标识、节点数、parity 结果和限制。
- [ ] **Step 3: 建立评测集。** 固定 Self-RAG loop、CRAG branch、ReAct loop、AutoGen multi-agent、TPS-Bench parallel、中文方法段落和多系列 CSV；每个案例包含输入、金标准节点/边、期望图类型和许可信息。
- [ ] **Step 4: 生成报告。** 统计节点召回率、边方向准确率、分支/循环召回率、证据覆盖率、候选差异度、视觉 Critic 通过率、许可证完整率、SVG/PDF 导出成功率和任务恢复率。
- [ ] **Step 5: 设定发布门槛。** 旧测试全部通过；许可证字段完整率 100%；SVG/PDF 导出成功率至少 98%；结构 Critic 严重错误为 0；无证据节点不得自动进入最终稿；中文 fixture 无乱码。
- [ ] **Step 6: 更新文档。** README 增加本地启动、字体诊断、候选评审、Draw.io/Figma 状态和常见故障；docs/visual-product-report.md 记录样例截图、指标和已知限制。
- [ ] **Step 7: 提交。** git add src scripts eval_cases README.md docs tests；git commit -m "feat: add visual product evaluation and figma handoff"。

## 推荐执行顺序

先完成 Task 1 → Task 2 → Task 3，解决当前“中文乱码和候选缺乏审美差异”的直接问题；这三个任务完成后再做 Task 4，避免用户在证据审阅页面中看到不可读的候选。Task 5 可以与 Task 4 并行推进，但进入最终导出前必须先完成 Task 6 的许可证门禁。Task 7 最后执行，用于确认真实 Figma 连接和发布质量，而不是把外部账号作为本地开发前置条件。

## 每个阶段的验收演示

### P0 演示

输入：

~~~
用户问题经过规划器分解，检索器查询知识库，工具返回证据，生成器综合证据后输出答案；若证据不足，则回到检索器继续搜索。
~~~

应看到三张不同候选：横向 editorial、分区 swimlane、带反馈回路的 loop/hierarchy；中文标签、标题和分组均正常显示，并可下载 SVG、PDF、Draw.io。

### P1 演示

点击“检索器”节点能看到原文引用；点击“需要证据”后，导出包保留 review action，且不会标记为 publish_ready。

### P2 演示

上传带 method、accuracy、std、p_value 列的中文 CSV，三候选分别展示 grouped bar、interval plot 和 heatmap/small multiples，图例、单位和显著性标记可追溯到列。

### P3 演示

模板许可证、用户 SVG 来源和 Figma 连接状态全部进入 manifest；Figma 不可用时仍能完成本地导出。

## 自检结果

- 计划覆盖当前用户反馈：字体、预览、候选审美和候选差异在 Task 1–3 中有直接实现和测试。
- 计划没有把“更好看”定义为随机换颜色，而是定义为布局家族、信息组织、连接路线和可读性指标。
- 每个后续任务都保留 Figure Spec 语义源、provenance、license 和历史版本。
- 真实 Figma、网络模板和云端模型均是可插拔增强，不阻塞本地产品可用性。
