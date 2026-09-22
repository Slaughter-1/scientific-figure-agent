# Scientific Figure Agent 项目系统审查文档

> 文档用途：将当前工作区的真实代码、配置、测试和研究材料交给另一位 GPT 做技术审查。
>
> 事实基准：工作区 E:\Desktop\科研绘图；Git 提交 bc6dfa5079e92bf60e37bd9e45b8e10ae499569f；审查日期 2026-09-21。
>
> 重要说明：本文件按源代码当前行为编写。它不是产品宣传材料，也不把路线图、接口名称、静态元数据或“测试通过”解释为完整的产品能力。

## 1. 给审查 GPT 的阅读说明

请先判断下列内容属于哪一类：

- **已实现并可在本机复现**：代码路径和验证方式明确，当前测试或手工流程能够证明；
- **已实现的局部能力**：存在函数、数据结构或单个接口，但没有接通完整用户流程；
- **静态占位或演示能力**：返回固定目录、固定评分、示例元数据或本地 JSON，不代表真正的网络检索、视觉评估或远程写入；
- **规划中**：设计文档描述了目标，但当前代码没有实现；
- **未知**：本文件没有足够证据，不能从名称或测试数量推断。

请特别检查：

1. Web API 是否真正使用了请求中的所有字段；
2. Figure Contract 是否真正约束了最终 Figure Spec；
3. 三个候选是否真的有布局或视觉差异；
4. Draw.io、SVG、PDF、PNG、Figma 是否由同一语义源生成；
5. provenance、license 和 review action 是否影响导出，而不只是被记录；
6. “结构 Critic 通过”是否等价于科学内容正确；
7. 评测脚本是否使用独立金标准；
8. 文档声称的功能能否由代码、测试、样例产物和运行日志共同证明。

如果判断所需证据不足，请直接向用户索取**具体文件或运行结果**。建议的索取方式见本文第 19 节。不要因为本文件描述了一个目标架构，就假定目标架构已经全部完成。

## 2. 产品定位和当前结论

### 2.1 当前实际产品

当前项目是一个：

- Python 库和 CLI；
- 带 FastAPI API 的本地 Web 壳；
- React/Vite 前端；
- 以规则解析器为主的 Figure Spec/Plot Spec 生成原型；
- Draw.io、SVG、PDF、PNG 的本地导出原型；
- 有 Figma scene handoff 接口，但没有在本项目中验证真实 Figma 远程写入；
- 有模板、组件、资产、许可证、审阅和评测的数据结构，但其中若干仍是局部实现。

它**还不是**一个已经完成的、可以自行浏览网络、理解任意论文、生成投稿级精美图并自动完成 Figma 精修的全自动 Agent。

它也**不是一个只靠 SKILL.md 工作的 Skill**。核心逻辑在 Python 包中；未来 Skill 只应作为调用本地产品的薄层。

### 2.2 能力成熟度总表

| 能力 | 当前状态 | 事实依据 | 主要限制 |
|---|---|---|---|
| FigureRequest 数据模型 | 已实现局部能力 | src/figure_agent/request.py | 校验浅；Web 没有使用全部字段 |
| Figure Spec 0.1/0.2/0.3 运行时兼容 | 已实现 | src/figure_agent/spec.py、spec_migration.py | 静态 JSON Schema 只覆盖 0.1/0.2；默认解析器仍输出 0.1 |
| 论文段落规则解析 | 已实现 | parser.py、planner.py | 适合短的箭头式流程；不是通用论文语义解析 |
| Figure Contract | 已实现局部能力 | planner.py | 只生成简化字段；没有约束后续导出的 Spec |
| LLM 语义规划 | 接口骨架 | providers/llm.py | 未接入 Web/CLI 主流程；没有 Ollama；无完整 JSON Schema 重试链 |
| 三候选生成 | 已实现原型 | candidates.py | 差异多为静态元数据/布局族；评分未进行真实视觉测量 |
| Draw.io 导出 | 已实现原型 | backends/drawio_backend.py | 位置、分组、字体、边路由和多节点布局有明显限制 |
| SVG/PDF/PNG 图形导出 | 已实现 | drawio_backend.py、plot_backend.py | 图形美观、字体嵌入和复杂布局尚未达到投稿级 |
| CSV/JSON 数据图 | 已实现局部能力 | data.py、plot_planner.py、backends/plot_backend.py | 数据校验、误差线、显著性、单位和图形候选仍不完整 |
| 模板搜索 | 静态目录 | templates.py | 无网络抓取、无实时许可证据、固定四条记录 |
| 组件包/提示词 | 已实现局部能力 | components.py | 通用组件，未接入完整回传、验收和合成流程 |
| 用户素材登记 | 已实现局部能力 | artifacts.py、app/api.py | 只做文件登记；PDF/PNG/SVG 解析和许可字段不完整 |
| 素材合成 | 占位 | assembly.py | 只添加 asset_refs，未把资产渲染进最终图 |
| 结构 Critic | 已实现局部能力 | critic.py | 默认 0.1 Spec 会绕过 evidence 检查；不理解复杂语义 |
| 视觉 Critic | 已实现局部能力 | visual_critic.py、inspect.py | 多为几何/静态检查，无可靠图像视觉模型或截图回归 |
| 版权/许可证检查 | 已实现局部能力 | license.py | 检查字段不完整；存在未拒绝的异常状态 |
| manifest | 已实现局部能力 | artifacts.py | 记录范围有限；Web 导出没有完全复用发布门禁 |
| Figma 接入 | 本地 handoff/transport 接口 | figma_handoff.py、backends/figma_backend.py | 本项目未验证真实 MCP schema、账号、文件或 Frame |
| Web 服务 | 已实现 | web.py、app/api.py、frontend | 可创建和生成任务；完整审阅工作流尚未完成 |
| SQLite 持久化 | 已实现局部能力 | app/store.py | 没有完整的候选/资产/模板关系表；版本冲突控制不足 |
| 评测 | 有脚本和样例 | evaluation.py、research_data、scripts | 复杂金标准存在循环/独立性问题；没有真实视觉质量基准 |
| 真实网络论文检索 | 未实现 | 无网络 provider | research_data 是本地材料，不是运行时自动搜索 |
| 真实 Figma 远程写入 | 未在本项目验证 | 没有已确认的 transport 配置/日志 | 不应将 handoff JSON 视为已写入 |
| 投稿级“精美科研绘图” | 尚未证明 | 无独立人工评审和视觉回归数据 | 当前输出更接近可编辑结构草图/数据图原型 |

## 3. 目标架构与当前实现的差异

计划中的完整链路是：

~~~text
论文段落 / 图注 / CSV / JSON / 用户素材
    -> 输入理解和 Figure Contract
    -> 模板与组件检索
    -> Figure Spec + provenance
    -> 三个候选
    -> Draw.io / SVG / PDF / PNG
    -> 结构 Critic + 视觉 Critic + 版权检查
    -> 用户选择、修改、素材替换
    -> 最终图包和版本记录
~~~

当前主路径更接近：

~~~text
Web 文本
    -> parse_method_text 规则解析
    -> build_figure_contract（独立再次解析）
    -> 静态模板目录
    -> generate_candidates
    -> 本地 Draw.io/SVG/PDF/PNG
    -> 简化 manifest
~~~

关键差异：

- Web 的 paper_text、figure_caption、CSV、JSON、existing_spec、user_assets 没有统一按 input_type 分派；当前主路径按文本解析。
- Contract 没有成为 Spec 生成的硬约束；例如需要审阅的可疑节点仍可能进入候选。
- 生成过程是同步 API 调用，不是可恢复的后台任务队列。
- 当前没有真正的网络模板搜索、下载、缓存和许可证据抓取。
- 组件资产没有被渲染到图中。
- Web 审阅界面无法完成“锁定节点、删除节点、需要证据、局部重新生成”等设计流程。
- 导出 API 没有完整执行 manifest、许可证和发布门禁。
- Figma 只有抽象 transport 和本地 scene，不等于真实 Figma 文件创建或 Canvas 写入。

## 4. 仓库和运行环境

### 4.1 目录结构

~~~text
E:\Desktop\科研绘图
├─ pyproject.toml
├─ requirements.txt
├─ pytest.ini
├─ README.md
├─ src/
│  └─ figure_agent/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ cli.py
│     ├─ web.py
│     ├─ request.py
│     ├─ spec.py
│     ├─ spec_migration.py
│     ├─ parser.py
│     ├─ planner.py
│     ├─ workflow.py
│     ├─ candidates.py
│     ├─ visual_styles.py
│     ├─ layouts.py
│     ├─ critic.py
│     ├─ visual_critic.py
│     ├─ data.py
│     ├─ plot_planner.py
│     ├─ templates.py
│     ├─ components.py
│     ├─ assembly.py
│     ├─ inspect.py
│     ├─ artifacts.py
│     ├─ license.py
│     ├─ parity.py
│     ├─ router.py
│     ├─ figma_handoff.py
│     ├─ evaluation.py
│     ├─ environment.py
│     ├─ providers/
│     │  └─ llm.py
│     ├─ app/
│     │  ├─ api.py
│     │  └─ store.py
│     └─ backends/
│        ├─ drawio_backend.py
│        ├─ plot_backend.py
│        └─ figma_backend.py
├─ schemas/
│  └─ figure_spec_schema.json
├─ frontend/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ vite.config.js
│  ├─ index.html
│  └─ src/
│     ├─ main.jsx
│     ├─ styles.css
│     └─ preview.js
├─ tests/
├─ research_data/
├─ eval_cases/
├─ scripts/
└─ docs/
~~~

当前源代码包含 37 个 Python 模块和 37 个 test_*.py 测试文件。数量本身不能证明功能完整度。

### 4.2 Python 依赖和入口

pyproject.toml 当前声明：

- Python >= 3.10；
- matplotlib >= 3.10；
- Web extra：fastapi == 0.104.1、python-multipart >= 0.0.9、uvicorn[standard] == 0.24.0；
- test extra：pytest >= 9.0、httpx < 0.28；
- console scripts：
  - figure-agent -> figure_agent.cli:main
  - figure-agent-web -> figure_agent.web:main

requirements.txt 目前只列 matplotlib、pytest。若用户只按 requirements.txt 安装，不一定得到 Web 运行所需的 FastAPI、Uvicorn、multipart 依赖。项目环境中还曾出现 agentmesh-sdk 对 FastAPI 0.104.1 和 Uvicorn 0.24.0 的严格版本冲突；这属于环境依赖管理问题，不是图形算法本身。

### 4.3 前端依赖

frontend/package.json 使用 React、React DOM、Vite 和 @vitejs/plugin-react 的 latest 版本范围，package-lock.json 锁定了安装结果。脚本只有：

- npm run dev
- npm run build
- npm run preview

没有前端测试运行器，也没有端到端浏览器测试。Vite 开发服务器将 /api 代理到 127.0.0.1:8765。

### 4.4 服务启动

推荐在项目根目录：

~~~powershell
cd E:\Desktop\科研绘图
python -m pip install -e ".[web,test]"
cd frontend
npm ci
npm run build
cd ..
figure-agent-web --data-dir E:\Desktop\科研绘图\figure-agent-data
~~~

默认服务地址是 http://127.0.0.1:8765。web.py 启动参数包括 --data-dir、--host、--port。

服务启动后，根路径是否显示前端取决于 frontend/dist 是否位于代码查找的位置。若 dist 不存在，当前应用会返回 JSON 提示，而不是可交互网页。历史白屏问题的直接原因是根路径未提供页面或静态文件；当前代码已经包含 dist 挂载逻辑，但仍需检查前端是否成功构建以及服务工作目录。若只看到 HTTP 404，不能认为后端 API 也失败；应分别检查 /api/health、/docs 和 frontend/dist。

### 4.5 启动验证

~~~powershell
Invoke-WebRequest http://127.0.0.1:8765/api/health
Invoke-WebRequest http://127.0.0.1:8765/docs
Get-ChildItem E:\Desktop\科研绘图\frontend\dist
~~~

如果使用浏览器访问根路径，至少应看到 index.html 返回的前端页面，而不是纯 JSON 或空白页面。

## 5. 核心请求模型 FigureRequest

文件：src/figure_agent/request.py。

支持的 input_type 字面值：

- paper_text
- figure_caption
- csv
- json
- existing_spec
- user_assets

主要字段：

~~~json
{
  "input_type": "paper_text",
  "content": "...",
  "figure_goal": "method_overview",
  "target_figure_type": "architecture",
  "audience": "paper",
  "paper_width": "double_column",
  "style": "academic_clean",
  "required_outputs": ["svg", "pdf", "png", "drawio"],
  "template_policy": "open_license_first",
  "candidate_count": 3,
  "user_assets": [],
  "constraints": {}
}
~~~

允许的目标类型包括 architecture、workflow、graph、plot；版面包括 single_column、double_column、custom；模板策略包括 open_license_first、broad_search、local_only。

当前校验：

- 检查 input_type、target_figure_type、paper_width、template_policy 是否在枚举内；
- 检查 content 非空；
- 检查 candidate_count 在 1 到 3；
- 检查 required_outputs 和 user_assets 是列表。

当前限制：

- bool 在 Python 中属于 int，candidate_count 的类型校验需要更严谨；
- content 的复杂结构只做空值级别检查；
- required_outputs 的值没有充分校验；
- audience、style、constraints 没有完整 schema；
- Web 创建后没有把每个字段都传递给规划器和后端；
- 请求模型没有被数据库完整序列化为可查询的规范化关系。

## 6. Figure Spec 版本和迁移

### 6.1 运行时支持

文件：src/figure_agent/spec.py。

运行时接受 0.1、0.2、0.3。基础对象包括：

- title
- figure_type
- layout
- nodes
- edges
- groups
- data
- metadata
- provenance
- evidence
- constraints
- template_refs
- asset_refs
- panel
- candidate_id
- review_notes
- needs_review
- semantic_confidence

节点类型：

- model
- tool
- data
- process
- storage
- decision

边类型：

- data_flow
- control_flow
- dependency

布局方向包括 LTR 和 TTB；数据图支持 bar、line、heatmap、scatter。

验证包括：

- schema_version；
- 节点 ID 唯一；
- 边的源和目标存在；
- group 成员存在；
- metadata 基本字段；
- plot 的 x、y、error、series、significance 基本长度检查。

当前不是完整科学图 schema，尚未充分检查：

- 颜色、字体、尺寸、坐标是否有限；
- 负误差线、NaN/Inf；
- 坐标越界；
- evidence 的结构和 quote 与输入的对应关系；
- provenance 是否覆盖所有节点、边、数据列；
- 字体是否可用；
- SVG/PDF 导出是否完整。

### 6.2 静态 JSON Schema

schemas/figure_spec_schema.json 目前主要覆盖 0.1 和 0.2。运行时说支持 0.3，但静态 Schema 存在版本漂移，审查时不能只看此文件就认定 0.3 已完整约束。

### 6.3 迁移逻辑

文件：src/figure_agent/spec_migration.py。

迁移会：

- 深拷贝输入；
- 将 schema_version 改为 0.3；
- 补充 provenance、evidence、constraints、template_refs、asset_refs、panel、review_notes、needs_review；
- 补 task_id、request_id、candidate_id（如提供）；
- 给节点补 evidence、locked、confidence；
- 根据是否有节点 evidence 粗略设置 semantic_confidence。

迁移不会：

- 自动恢复缺失证据；
- 从论文重新建立 provenance；
- 验证引用 quote 真的来自输入；
- 把 0.1 数据结构变成语义完整的 0.3；
- 自动改变主工作流的默认解析输出。

## 7. 论文文本解析和 Figure Contract

### 7.1 规则解析器

文件：src/figure_agent/parser.py。

当前能力：

- 识别 ->、→、=>；
- 没有箭头时按部分中文和英文标点分句；
- 识别 [A|B] 形式的分支；
- 识别 to、分支为、分为等部分分支表达；
- 识别 loop back to、repeat until、循环回到、返回、迭代到等部分循环表达；
- 对每个阶段生成节点和 data_flow/control_flow 边；
- 节点证据通常是原始子句，但边通常没有 evidence；
- 默认输出标题 Generated Workflow Spec 和 schema 0.1。

已知语义限制：

- 没有通用英文论文句法分析；
- 没有事实句、方法句、结果句、约束句分类；
- 对长段落、跨句指代、表格、公式和图注支持弱；
- 部分前缀和标点会导致标签截断；
- “回到”在常见中文表达中不一定命中已有 loop 规则；
- 未知循环目标可能形成无证据节点，而不是 needs_review；
- 规则解析生成的边缺乏直接证据引用；
- 中文字体和编码问题属于导出/浏览器链路，不会由解析器自动解决。

### 7.2 Figure Contract

文件：src/figure_agent/planner.py。

当前实际字段大致包括：

- figure_goal
- target_figure_type
- required_labels
- optional_nodes
- required_edges
- evidence_gaps
- evidence_coverage
- needs_review

不完全等于计划中的：

- required_nodes
- forbidden_inventions
- panels
- recommended_layout
- recommended_template_types

Planner 能够：

- 根据关键词粗略分类 architecture、graph、plot、workflow；
- 从段落中提取部分证据；
- 识别“可能、可选、未来工作、有望、potential、might”等不确定标记。

关键问题：generate_from_text 会对原文再次调用 parse_method_text，并把原始 Spec 传给候选生成；Contract 没有真正过滤未证实节点、禁止发明模块或强制所有 required_edges。因此 Contract 当前更像报告，而不是编译约束。

## 8. 候选生成、布局和视觉样式

文件：src/figure_agent/candidates.py、visual_styles.py、layouts.py。

### 8.1 三个候选的名义定位

- candidate_01：结构完整/结构优先；
- candidate_02：论文版式优先；
- candidate_03：视觉层级优先。

候选会记录 spec、artifact 路径、scores、review_findings、preview_fingerprint 和 design_reason。

### 8.2 实际差异

候选根据节点边形态选择 editorial、swimlane、hierarchy、loop 等布局族。部分候选改变布局族、颜色变体、字体/间距元数据；但：

- plot 候选通常复用同一 Plot Spec 和同一绘图调用，视觉内容可能完全相同；
- 三候选没有逐一调用完整结构/视觉 Critic 再反馈修正；
- scores 是启发式公式，未使用真实图像测量、论文尺寸截图或人工标注；
- layout_distinctiveness 和 semantic_preservation 并非测量结果；
- score 不是用户选择的科学质量保证。

### 8.3 样式

academic_clean 使用浅色背景、蓝/紫/灰等 token，提供节点宽高、圆角、阴影、字号和边样式。字体解析是硬编码优先级列表，并不检测本机是否安装字体或 SVG/PDF 是否嵌入字体。

中文乱码风险来源：

- 导出的 SVG/PDF 依赖本机字体；
- 浏览器未必能找到 Noto Sans CJK、Microsoft YaHei 等字体；
- SVG 使用 font-family 不等于嵌入字体；
- 字体 fallback 在不同 Windows/浏览器环境可能不同。

### 8.4 布局缺陷风险

- pipeline 将所有节点排成单行，节点较多时会变得很长；
- swimlane 的行数固定为 3，节点多时 y 可能落在画布外；
- loop 布局按数组索引取固定位置，超过四个节点可能重叠；
- hierarchy 按数组索引分行，不是按图拓扑层级；
- 边路由采用固定偏移，可能穿过节点文字；
- 自动分组可能将 data/storage 和其余节点按类型归类，未必符合论文语义；
- 这些问题会导致“节点+连线的丑陋图案”，属于实际质量限制，不是用户主观误解。

## 9. Draw.io、SVG、PDF、PNG 后端

文件：src/figure_agent/backends/drawio_backend.py。

### 9.1 Draw.io

实现：

- 将节点、边、group 写入 mxGraphModel XML；
- 根据布局计算位置；
- 生成 .drawio；
- 可生成对应 SVG/PDF。

限制：

- flat node_width/node_height 与嵌套 visual style token 没有始终统一；
- 坐标由中心位置换算 top-left 时存在视觉偏移风险；
- group 多数是关系/元数据表达，不一定是 Draw.io 的真实父子容器；
- XML 转义和自定义样式覆盖范围有限；
- 边标签和复杂箭头样式支持弱；
- 输出 SVG/PDF 是本地渲染结果，不代表 Draw.io 原生客户端打开后的完全一致结果；
- render_drawio_spec 不负责生成 PNG。

### 9.2 SVG/PDF

SVG/PDF 由 Matplotlib/本地后端绘制。当前适合简单流程和数据图，尚未证明：

- 多栏尺寸下标签始终可读；
- 中英文混排始终无乱码；
- 字体在目标期刊环境中可复现；
- 多组、长标签、循环、反馈边和复杂箭头不裁剪；
- 导出的 SVG/PDF 与 Draw.io 中的节点一一对应。

### 9.3 PNG

数据图后端支持 PNG。结构图候选的 PNG 不是所有路径都默认生成，API 的 required_outputs 也没有完全强制后端一致生成。审查时应查看具体 candidate.json 和 exports 目录，不要只根据字段名称推断。

## 10. 数据图流水线

文件：src/figure_agent/data.py、plot_planner.py、backends/plot_backend.py。

### 10.1 输入和图类型

支持：

- CSV；
- JSON records；
- bar；
- line；
- scatter；
- heatmap；
- 多个 y 列；
- 共享误差列或按系列误差列；
- significance 字段；
- 基本 x/y/label/unit 字段。

### 10.2 数据处理

当前会：

- 读取 utf-8-sig CSV；
- 对 JSON records/list 做基本规范化；
- 推断数值列或类别列；
- 构建 Plot Spec；
- 保存部分 source、format、column_provenance。

当前不足：

- source 只记录字符串，不稳定地记录输入文件 SHA-256；
- 列级 provenance 对 error/significance 等角色可能被简单归为 y；
- NaN/Inf 和负误差检查不足；
- 表头空格和重复列的边界行为不完整；
- 没有行级 identity；
- 没有统计检验；
- 显著性标记是输入字符串的绘制，不会自动计算 p 值；
- unit 主要是标签文字，不做单位换算；
- Web 界面没有完整的数据列选择、误差列配置、图类型配置。

### 10.3 绘图质量

- bar、line、scatter 使用固定尺寸和有限颜色 token；
- heatmap 的语义刻度、缺失值和注释能力有限；
- 显著性位置是固定偏移，可能遮挡误差线或其他系列；
- 多系列图例和类别标签长时容易拥挤；
- 没有独立的三种图形候选生成；
- 没有数据图的视觉回归样本。

## 11. 模板检索和许可证

文件：src/figure_agent/templates.py、license.py。

### 11.1 当前模板目录

当前静态记录主要指向：

- draw.io 官方模板/文档；
- Mermaid 官方语法/文档；
- 项目自己的 GitHub 来源；
- Figma Templates 入口。

TemplateRecord 含有 id、source_url、source_type、license、editable、supported_types、style_tags、components、preview_url、download_url、restrictions、retrieved_at、approval_status 等字段。

### 11.2 实际行为

- 没有运行时 HTTP 搜索、网页解析或下载；
- 返回顺序主要来自固定列表和关键词过滤，不保证总是三条；
- preview_url/download_url 当前可为空；
- “verified”是静态元数据，不等于本次运行检查了许可证页面；
- retrieved_at 是查询/记录时间，不是远程文件下载时间；
- Mermaid 文档说明与可再利用模板许可证不是同一个概念；
- 官方模板入口不自动授予任意二次分发权；
- 未验证资源可以展示，但当前其他导出路径未始终阻断它。

### 11.3 许可证检查

license.py 会检查 template_refs 和 asset_refs 的 approval_status/license，并对 review_required、unknown、None 等状态产生 finding。

需要重点复核：

- rejected 或任意非空许可证文本是否总能被阻断；
- Web export 是否调用 license checker；
- manifest 是否包含每个来源、证据 URL、下载时间和用户确认；
- 用户上传素材的许可证是否被强制填写。

## 12. 组件包、资产和合成

### 12.1 组件请求

文件：src/figure_agent/components.py。

能够生成：

- component_id；
- role；
- required_elements；
- 尺寸和 padding；
- 背景/描边/字体；
- 文本；
- 生成提示词；
- component-manifest.json 和 component-prompts.md 的基础内容。

组件词典目前主要包含 retriever/tool、database、search_arrow、document_stack 等通用词，存在把视觉表示当成语义事实的风险。

### 12.2 资产登记

文件：src/figure_agent/artifacts.py、app/api.py。

登记大致包括：

- 文件名；
- SHA-256；
- 扩展名；
- 是否可编辑；
- 简单尺寸；
- 来源/许可字段的部分支持。

当前实际限制：

- SVG 尺寸解析只覆盖部分 width/height 写法；
- PNG/PDF/Draw.io/Figma JSON 没有完整内容验证；
- 没有稳定的 MIME、透明度、像素尺寸和时间字段统一登记；
- JSON 扩展名就被视为可编辑，不代表是有效 Figma JSON；
- Web 上传会读完整文件，没有明显大小上限；
- 同名文件可能覆盖；
- upload API 与内部 AssetManifest 的字段不完全一致。

### 12.3 合成

assembly.py 目前主要把资产引用挂到 Spec 或候选上。它没有完成：

- 将 SVG/PNG 放进 Draw.io；
- 将组件位置映射到目标节点；
- 进行透明背景和尺寸校验；
- 在 Figma scene 中创建对应原生节点；
- 合成后进行 Draw.io/Figma/SVG parity 检查。

## 13. Critic、自动修正和发布门禁

### 13.1 结构 Critic

文件：src/figure_agent/critic.py。

检查项目包括：

- Spec 基础验证；
- 重复标签；
- 悬空边；
- 孤立节点；
- 部分 evidence 缺失；
- title/layout 基本问题。

重要限制：默认 parser 输出 0.1，而 evidence 检查主要针对 0.2/0.3，因此很多“节点没有证据”的问题不会按计划被阻断。它也不会验证边方向是否真正符合原文、模块是否是研究方法中真实出现的概念、循环是否正确表达。

### 13.2 视觉 Critic

文件：src/figure_agent/visual_critic.py、inspect.py。

目标检查包括：

- 重叠；
- 越界；
- 边穿文字；
- 字体过小；
- 颜色数量；
- 字体一致性；
- SVG/PDF 裁剪；
- 单栏/双栏缩放。

当前主要是基于 Spec、坐标和文件静态信息的检查，没有可靠的浏览器截图、像素级 diff、OCR 字号验证或视觉语言模型审查。输出通过不等于“审美良好”。

### 13.3 自动修正

当前可安全做的修正主要是：

- 样式 token；
- 标题；
- 部分间距或画布设置。

它没有形成完整的“修改前版本、修改后版本、差异、回滚”工作流。语义增删也没有由用户批准后再重新编译的完整闭环。

### 13.4 Manifest 和发布状态

文件：src/figure_agent/artifacts.py。

Manifest 可包含：

- spec hash；
- 候选产物；
- artifact 路径；
- critic findings；
- license findings；
- publish_ready。

但需要注意：

- Web export 没有始终调用 build_manifest、Critic 和许可证门禁；
- publish_ready 不能被当成“投稿级证明”；
- manifest 不一定包含所有模板/资产记录和原始输入 hash；
- zip 包当前偏向候选文件清单，未必包含完整的 review、version、input、asset 原件；
- 导出失败时中间产物和状态恢复仍不完整。

## 14. Figma 接入现状

文件：src/figure_agent/figma_handoff.py、src/figure_agent/backends/figma_backend.py。

当前设计用协议抽象 transport，主要状态：

- unavailable；
- mock/local；
- connected；
- error。

当前可做：

- 从 Spec 生成本地 scene JSON；
- 通过本地 mock 返回节点数量；
- 若调用者提供 callback，可在抽象层返回 connected 和 file_or_frame；
- 将 handoff 内容保存为本地 JSON/manifest。

当前不能由本项目独立证明：

- 已登录 Figma；
- 已创建真实 Figma 文件；
- 已选择正确页面；
- Frame、Text、Rectangle、Line、Group 都是原生节点；
- 已真实导出 SVG/PDF；
- Draw.io、Figma、Spec 的几何 parity 已通过。

真实接入前必须拿到实际工具 schema、权限和一次 smoke-test 日志；不能凭猜测写 MCP 调用代码。当前还存在旧接口名 FigmaDriver 与计划接口 FigmaTransport 的命名差异，需统一。

## 15. LLM Provider

文件：src/figure_agent/providers/llm.py。

当前提供：

- LLMProvider Protocol；
- unavailable provider；
- mock provider；
- OpenAI-compatible HTTP provider；
- 基本 response JSON 解析。

当前不完整：

- Web/CLI 主流程没有把 Provider 注入 parser/planner；
- 没有 Ollama provider；
- schema 校验主要是浅层必需键检查，不是完整 JSON Schema；
- 没有按计划最多两次重试并将失败状态写入任务；
- 没有将模型、时间、请求摘要写入 llm_runs；
- 没有设置页面让用户选择 provider、endpoint、model；
- 任何云端调用的隐私提示和密钥生命周期管理需要补齐。

因此目前系统即使安装了 OpenAI-compatible 配置，也不会自动变成 LLM 驱动的论文理解 Agent。

## 16. FastAPI API

文件：src/figure_agent/app/api.py。

### 16.1 当前接口

| 方法 | 路径 | 当前用途 |
|---|---|---|
| GET | /api/health | 健康检查 |
| POST | /api/tasks | 创建任务、保存输入 |
| GET | /api/tasks | 列出任务 |
| GET | /api/tasks/{task_id} | 任务摘要和状态 |
| POST | /api/tasks/{task_id}/status | 手动改变状态 |
| POST | /api/tasks/{task_id}/analyze | 规则分析 |
| POST | /api/tasks/{task_id}/search-templates | 静态模板搜索 |
| POST | /api/tasks/{task_id}/generate-candidates | 生成候选 |
| GET | /api/tasks/{task_id}/candidates | 读取候选 |
| POST | /api/tasks/{task_id}/select-candidate | 选择候选 |
| GET | /api/tasks/{task_id}/manifest | 读取任务清单 |
| POST | /api/tasks/{task_id}/export | 打包候选文件 |
| GET | /api/tasks/{task_id}/files/{file_path} | 读取任务文件 |
| POST | /api/tasks/{task_id}/review-actions | 保存审阅操作 |
| POST | /api/tasks/{task_id}/assets | 上传资产并登记 |

FastAPI 还会自动提供 /docs、/redoc、/openapi.json。

### 16.2 计划接口但当前缺失或不完整

完整计划中的 assemble、inspect、Figma 写入、版本 diff、局部重新生成等接口尚未全部存在。当前 review-actions 主要保存记录，并不会自动修改候选 Spec 或重新导出。

### 16.3 任务流程

典型顺序：

~~~text
POST /api/tasks
POST /api/tasks/{id}/analyze
POST /api/tasks/{id}/search-templates
POST /api/tasks/{id}/generate-candidates
GET  /api/tasks/{id}/candidates
POST /api/tasks/{id}/select-candidate
POST /api/tasks/{id}/export
~~~

当前请求处理是同步执行。状态枚举存在，但部分状态是占位或手动更新，缺少严格的状态转换校验、后台队列、重试和崩溃恢复。

### 16.4 API 风险点

- 文件路径读取和导出路径必须持续复核路径穿越防护；
- upload 没有统一大小限制和文件类型深度校验；
- review action 的 target、approved_by 和时间戳没有权限模型；
- candidate_id、task_id 的关联校验需要加强；
- export 默认候选不一定要求用户明确选择；
- regeneration 可能覆盖固定路径；
- manifest 和数据库更新没有完整原子事务。

## 17. SQLite 持久化

文件：src/figure_agent/app/store.py。

当前表：

- tasks；
- task_inputs；
- task_versions；
- artifacts；
- review_actions；
- llm_runs。

计划中应有但当前没有完整建模的实体：

- candidates；
- assets；
- template_refs；
- 更完整的 artifact/task-version 关系；
- review action 对 Spec 变更的实际引用。

已实现的基础能力：

- 创建任务；
- 保存输入；
- 保存状态；
- 记录版本快照；
- 记录 artifact；
- 查询任务列表和状态。

当前限制：

- task_versions 的并发/唯一性和 base_version 冲突检查不足；
- review action 可写入但不会形成语义 patch；
- 输入文件 hash、MIME、大小和 provenance 的统一记录不完整；
- 没有用户认证/权限，这是本地单用户原型的默认假设；
- 服务重启可读到任务，但完整中间状态恢复未完全证明。

## 18. 前端当前功能

文件：frontend/src/main.jsx、styles.css、preview.js。

当前页面主要支持：

- 创建文本任务；
- 触发分析；
- 搜索模板；
- 生成候选；
- 查看候选卡片；
- 预览 SVG/PNG；
- 查看有限的证据片段；
- 选择候选；
- 导出候选；
- 查看部分评分和设计理由。

当前没有或不完整：

- Markdown/TXT/PDF/CSV/JSON 多类型上传交互；
- 图类型、版面宽度、风格、provider 的完整表单；
- 三个候选的真正并排同步比较；
- 节点点击定位和完整 evidence panel；
- 模板许可和来源的完整界面；
- 删除/保留/需要证据按钮；
- 组件包下载和素材替换映射；
- 任务历史和刷新后的编辑上下文；
- 版本 diff、回滚和重新生成指定区域；
- 明确的错误边界和跨任务状态清理。

前端百分比和预览状态不能自动证明评分经过图像分析；应以 API 返回和具体产物为准。

## 19. CLI

文件：src/figure_agent/cli.py、router.py。

已存在或接近存在的命令族包括：

- analyze；
- search-templates；
- generate；
- plot；
- assemble；
- inspect；
- package；
- figma handoff；
- evaluate/环境检查相关脚本。

命令行为需要以当前 --help 和源代码为准。特别注意：

- 文本 generate 主要走规则解析；
- plot 是当前最完整的数据入口之一；
- assemble 偏向资产引用；
- inspect 偏向静态检查；
- package 主要打包候选文件；
- Figma 命令生成本地 scene/handoff，并不自动验证远程 Figma；
- 计划中的所有 CLI 参数并非都已经实现，不能只根据路线图复制命令。

建议审查时运行：

~~~powershell
figure-agent --help
figure-agent generate --help
figure-agent plot --help
figure-agent-web --help
~~~

## 20. 研究数据、评测和测试

### 20.1 本地研究材料

- research_data/public_paper_corpus.json：20 个案例；
- research_data/complex_gold.json：6 个复杂案例；
- research_data/sources.json：来源索引；
- cases/：KATE 等案例 Markdown/CSV；
- eval_cases/m2_cases.json；
- eval_cases/visual_quality/README.md：目前主要是说明文件，不能当作视觉基准数据集。

这些文件是仓库中的离线材料。运行时不会自动搜索论文网页、GitHub 数据集或远程模板。

### 20.2 评测实现限制

文件：src/figure_agent/evaluation.py、scripts/evaluate_public_corpus.py、scripts/evaluate_complex_gold.py、scripts/build_evaluation_report.py。

当前评测能够：

- 对标签集合计算部分节点召回；
- 对边标签/方向做有限比较；
- 统计 evidence 是否非空；
- 统计分支和部分循环指标；
- 生成报告摘要。

需要重点审查：

- complex_gold 的部分 expected nodes/edges 是否由待测 parser 结果派生，若是则存在循环论证；
- 3 节点以上循环的检测和 2 节点回边不等价；
- 仅计算 recall 会漏掉 hallucinated/多余节点；
- 没有独立人工视觉评分；
- 没有 20–30 个案例的真实精美图人工对照；
- 没有导出成功率、字体跨环境成功率、恢复率的长期数据；
- 没有 CI 中固定执行的浏览器端到端验证。

### 20.3 当前测试验证

在本文件基准提交和当前环境中运行过：

~~~text
pytest
113 passed, 6 warnings, 13.01s
~~~

警告主要来自 Starlette multipart 和 httpx 兼容提示。测试通过说明现有测试断言通过，不说明：

- 输出视觉美观；
- 任意中文论文都能正确理解；
- 模板许可真实有效；
- Figma 已真实连接；
- Web 页面在所有浏览器正常；
- 复杂图没有重叠；
- 投稿级质量达到。

测试文件覆盖 Parser、Spec、迁移、候选、后端、Web API、数据图、模板、资产、Figma handoff、评测等，但不少测试只验证结构存在、文件存在、字符串存在或 mock 行为。

## 21. 当前已知问题分级

### P0：会误导用户或阻断核心承诺

1. Web 的 Contract 没有约束最终 Spec，未经证据确认的节点可能导出。
2. “三候选”没有可靠的真实视觉差异和质量测量。
3. 真实 Figma 写入未在本项目验证，不得宣称已完成。
4. 模板“verified”是静态记录，不是动态许可审计。
5. Web export 没有一致执行完整 Critic、license 和 manifest 发布门禁。
6. 复杂评测的金标准独立性不足，不能作为论文理解准确率证明。
7. 当前自动图形主要是结构草图，尚无投稿级审美证据。

### P1：显著影响实用性

1. 中文字体依赖本机 fallback，SVG/PDF 不一定嵌入中文字体。
2. loop、swimlane、hierarchy 和边路由在节点较多时会重叠、越界或穿文字。
3. 资产上传后没有真正合成到 Draw.io/Figma/SVG。
4. review-actions 只记录操作，未形成可执行的 Spec patch。
5. Web input_type、paper_width、style、required_outputs 的覆盖不完整。
6. 没有真正网络搜索论文、模板或 GitHub 数据。
7. 前端缺少上传、审阅、版本、许可和局部重生成流程。
8. SQLite 关系模型不足以支持完整候选和资产生命周期。

### P2：工程质量和维护性

1. requirements.txt 与 pyproject 的 Web 依赖不一致。
2. FastAPI/Uvicorn 与工作区其他包可能发生版本冲突。
3. 前端使用 latest 依赖范围，需稳定化版本。
4. 运行时 Spec 0.3 与静态 Schema 漂移。
5. FigmaDriver/FigmaTransport 命名和接口语义需统一。
6. 生成路径覆盖、并发、错误恢复和缓存策略不足。
7. 没有前端单元/端到端测试。
8. provenance、hash、MIME、license 字段尚未统一。

## 22. 与完整产品目标的差距

目标是“本地 Web 科研绘图 Agent”。要达到该目标，至少需要按以下顺序补齐：

### 阶段 A：事实一致性和数据契约

- 统一 Figure Spec 0.3 运行时和静态 JSON Schema；
- 让所有节点、边、数据列强制拥有 provenance/evidence；
- Contract 编译时过滤无证据模块；
- 统一请求、候选、资产、模板、版本数据库表；
- 让 manifest 包含输入 hash、每个模板和资产的完整许可记录。

### 阶段 B：真实工作流

- 按 input_type 分派 paper、caption、CSV、JSON、existing_spec、assets；
- 让 analyze 产出 Contract，generate 只接受已确认/已审阅 Contract；
- review action 生成可应用的 Spec patch；
- 选择候选后固定 candidate，导出只允许已选候选；
- 每次重新生成创建新版本，不覆盖历史。

### 阶段 C：语义能力

- 注入可配置 LLMProvider；
- 支持 mock、OpenAI-compatible、Ollama；
- 完整 JSON Schema 验证、两次重试和 needs_review；
- 提取事实/方法/结果/约束句；
- 复杂循环、分支、多 agent 和 RAG 结构提供独立金标准。

### 阶段 D：视觉质量

- 使用约束布局或图布局算法，而不是固定坐标；
- 实现文字测量、自动换行、箭头避障、组容器和画布自适应；
- 嵌入或可验证地选择中文字体；
- 为三候选保存真实 preview，并做 SVG/PDF/PNG 同源 parity；
- 建立截图和像素级回归；
- 让视觉 Critic 的严重问题阻断导出。

### 阶段 E：模板、资产和 Figma

- 对白名单来源做实际检索/缓存和许可证据保存；
- 资产做类型、尺寸、透明度、许可证验证；
- 将资产实际放置到 Draw.io/SVG/Figma；
- 用真实工具 schema 完成 Figma smoke test；
- manifest 记录连接状态、文件/Frame 标识和导出日志。

### 阶段 F：评测和发布

- 建立独立人工标注的 20–30 个论文案例；
- 同时评估节点 precision/recall、边方向、循环/分支、hallucination；
- 进行中文字体、单栏/双栏、SVG/PDF/PNG 和浏览器测试；
- 把严重结构错误、未知许可证和导出裁剪列为发布阻断项；
- 再考虑将核心能力封装为薄 Skill。

## 23. 建议审查 GPT 索取的文件

审查 GPT 如果需要证据，请按下面的最小集合向用户索取，不要笼统地说“请提供全部项目”。

### 23.1 判断核心语义解析

~~~text
请提供：
1. src/figure_agent/parser.py
2. src/figure_agent/planner.py
3. src/figure_agent/workflow.py
4. 一个真实输入段落
5. 该输入的 figure-contract.json 和 figure-spec.json
~~~

### 23.2 判断候选和视觉差异

~~~text
请提供：
1. src/figure_agent/candidates.py
2. src/figure_agent/layouts.py
3. src/figure_agent/visual_styles.py
4. 某一个任务的 candidates.json
5. candidate_01、candidate_02、candidate_03 的 SVG/PNG
6. 若有，审查截图或 PDF
~~~

### 23.3 判断 Draw.io/SVG/PDF/PNG 一致性

~~~text
请提供：
1. src/figure_agent/backends/drawio_backend.py
2. 一个 candidate 的 figure.drawio
3. 对应 SVG、PDF、PNG
4. candidate.json
5. 输出目录 manifest.json
~~~

### 23.4 判断中文乱码和字体

~~~text
请提供：
1. src/figure_agent/backends/drawio_backend.py
2. src/figure_agent/backends/plot_backend.py
3. 出现乱码的原始输入
4. 生成的 SVG/PDF/PNG
5. 当前系统字体列表和浏览器截图
~~~

### 23.5 判断 Web 白屏、API 和任务恢复

~~~text
请提供：
1. src/figure_agent/web.py
2. src/figure_agent/app/api.py
3. src/figure_agent/app/store.py
4. frontend/src/main.jsx
5. frontend/src/preview.js
6. frontend/dist/index.html（若已构建）
7. /api/health、/api/docs 或 /openapi.json 的响应
8. 浏览器控制台错误和服务日志
~~~

### 23.6 判断真实 Figma 接入

~~~text
请提供：
1. src/figure_agent/figma_handoff.py
2. src/figure_agent/backends/figma_backend.py
3. 实际 Figma MCP 工具名称和 schema
4. 一次固定 M0 workflow 的 smoke-test 日志
5. Figma 文件或 Frame 标识
6. 导出的 SVG/PDF 和 parity 报告
~~~

没有第 3 至 6 项时，只能审查本地 handoff 设计，不能判断真实 Figma 写入是否成功。

### 23.7 判断论文/数据评测

~~~text
请提供：
1. research_data/public_paper_corpus.json
2. research_data/complex_gold.json
3. src/figure_agent/evaluation.py
4. scripts/evaluate_public_corpus.py
5. scripts/evaluate_complex_gold.py
6. 运行命令和完整报告
7. 独立人工标注说明
~~~

### 23.8 判断模板和版权

~~~text
请提供：
1. src/figure_agent/templates.py
2. src/figure_agent/license.py
3. src/figure_agent/artifacts.py
4. 任务 manifest.json
5. 每个模板的 license_evidence_url、下载时间和来源页面
6. 用户上传素材的授权信息
~~~

### 23.9 文件索取原则

- 不索取 API key、密码、Cookie、私人论文或未脱敏个人信息；
- 可要求用户把敏感字段替换成 REDACTED；
- 如果只需判断结构，优先索取 JSON、日志和最小复现，而不是整个项目；
- 如果要判断视觉质量，必须索取实际导出的 SVG/PDF/PNG 或截图；
- 如果要判断 Figma，必须索取真实工具 schema 和成功返回，不接受“代码看起来应该能写入”作为证据。

## 24. 可直接交给审查 GPT 的提示词

~~~text
你是一个严格的科研软件和科研绘图系统审查员。请阅读随附的 PROJECT_SYSTEM_REVIEW.md，并把仓库当前状态拆成：
1. 已被代码和测试证明的功能；
2. 只有局部函数或静态占位的功能；
3. 计划中但尚未实现的功能；
4. 会导致科学内容错误、视觉质量不达标、版权风险或数据丢失的缺陷；
5. 需要补充的最小文件和运行证据。

请不要把：
- 测试通过解释为视觉质量通过；
- 静态模板记录解释为网络搜索或许可证验证；
- Figma scene/handoff 解释为真实 Figma 远程写入；
- provenance 字段存在解释为证据链有效；
- 三个候选文件解释为三个真正不同的设计；
- 规则解析器解释为通用论文理解 Agent；
- 计划文档解释为已实现产品。

请优先输出：
A. 现状结论；
B. 关键证据及其文件路径；
C. P0/P1/P2 缺陷；
D. 最小复现步骤；
E. 向用户索取的具体文件；
F. 按投入产出排序的修复计划；
G. 对“是否达到投稿级科研绘图”的明确判断及证据缺口。

如果证据不足，请以文件名、路径、命令或输出格式提出索取请求，不要自行补全事实。
~~~

## 25. 最终审查结论的建议表达

在没有新的独立证据前，合理的结论应接近：

> 这是一个已经具备 Figure Spec、规则文本解析、候选生成、数据图、Draw.io/SVG/PDF/PNG 本地导出、FastAPI/React Web 壳、静态模板目录和若干审查接口的科研绘图原型。它可以作为后续 Agent 产品的工程基础，但尚未证明自己是一个完整的论文理解 Agent、真实模板搜索器、真实 Figma 集成或投稿级精美绘图系统。最大的审查重点是 Contract 与最终 Spec 脱节、视觉布局质量、中文字体、许可证证据、Web review 闭环、评测独立性和 Figma 真实性。

这份结论应随着新的代码、实际产物、独立人工评审和真实 Figma smoke test 更新。

## 26. 2026-09-21 后续修复记录

根据最小证据包的技术审查，本轮已完成一组 P0 修复，代码和回归测试均已更新：

- 解析器识别中文“回到”以及“循环回到”并尝试解析到已有阶段；不明确或不存在的目标进入 `needs_review`，不会创建一个看似合理的新节点；
- 将“工具返回证据”作为完整阶段保留，不再把“返回”误判为循环标记；
- 将“若/如果……则回到……”保存为带条件标签和证据的 `control_flow` 回边；
- 候选生成前编译 Figure Contract：不确定节点不会静默进入候选 Spec，目标图类型沿用已保存 Contract；
- Web 生成优先读取同一任务根目录的 Contract，而不是无提示地重新分类；
- 候选选择和正式导出绑定：没有选择候选时，空导出请求返回 409；选择 candidate_03 后空导出请求会打包 candidate_03；
- 结构图后端现在同时生成 PNG 预览；
- 层级、泳道和循环反馈边使用外侧通道，避免箭头末段进入目标节点或与主流程共享同一条线；分组标题按组错开；
- 新增真实审查输入、未解析回边、Contract 编译、导出候选绑定和布局回归测试。

本轮实际验证：

~~~text
python -m pytest -q
126 passed, 8 warnings
~~~

警告仍来自 Starlette multipart 和 httpx 的弃用提示。此次修改证明了该审查样例的关键闭环有所改善，不等于所有论文输入、所有复杂布局或投稿级审美已经通过验证。真实任务目录中的旧候选不会被自动覆盖；新的 smoke test 产物保存在 `outputs/review-smoke-new/`，用于前后视觉对照。

本轮随后继续接通了审阅与交付闭环：对已选择的候选执行 `remove_node`、`lock_node` 或 `mark_needs_evidence` 时，会更新候选 Spec、重新生成图形文件，并保存修改前后的 Spec 版本；存在未处理 `needs_review` 时，正式导出返回 409；显式指定的候选不能覆盖任务已经选择的其他候选。无候选上下文的旧式审阅请求仍只记录操作，以保持历史 API 兼容。

追加验证结果：

~~~text
python -m pytest -q
129 passed, 11 warnings
~~~

## 27. 版本化正式导出与产物一致性阶段

根据审查回复的下一阶段要求，本轮又完成了以下交付约束：

- 每个候选生成时记录 `revision_id`、`revision_number` 和 `spec_sha256`；
- 选择候选时保存候选修订号和 Spec hash，而不是只保存 candidate_id；
- 候选修改后旧确认自动失效，必须重新选择当前修订；
- 没有选择候选时，即使显式传入 candidate_id，也不能正式导出；
- `lock_node` 定义为锁定节点语义内容，删除前必须显式 `unlock_node`；
- `resolve_needs_evidence` 可用证据关闭指定待审项；`dismiss_review` 可在保留原因的情况下将问题标记为不适用；
- 删除 Contract 必需节点或关系会生成 Contract 冲突待审项，不会自动补连新关系；
- 审阅重新渲染先写入独立 revision 目录，失败时保留旧当前修订，并写入失败记录；
- 正式 ZIP 只包含当前候选修订、请求、Contract、当前 Spec、候选元数据和实际产物；`manifest.json` 记录版本身份、hash、审阅操作、文件大小和文件 hash；
- Draw.io、SVG 预览现在输出条件边标签，条件不再只存在于 Spec 元数据中。

本轮全量验证：

~~~text
python -m pytest -q
135 passed, 16 warnings
~~~

历史记录：当时尚未完成真实 Figma 工具 smoke test、完整网络模板许可证审计和大规模独立人工视觉评测；后续 R1 已完成，R2 仍待人工评分，R3 已有真实一正两负审计。

## 28. RC 收口实现记录（2026-09-21）

根据最新审查中的 G1–G8 门槛，本轮继续完成：

- 增加 `contract_findings`，初始编译和正式导出都会检查必需节点、边方向、边类型及条件标签；
- 候选使用独立 `revisions/<revision_id>/` 目录，并保留候选根目录的 current pointer；
- 选择和修改校验 revision、版本号和 Spec SHA-256；任务级互斥锁和陈旧 `base_revision/base_version` 检查避免旧页面覆盖新版本；
- 审阅 issue 获得稳定 `issue_id` 与 `issue_revision`，解决记录保存 resolution、reason、evidence_refs、时间和 result_revision；Contract 冲突不能通过 dismiss 绕过；
- 正式导出校验当前修订实际文件哈希、证据、Contract、视觉几何和许可证；ZIP 先写临时文件，再重新读取并校验文件集合、大小、哈希和修订身份；
- 反馈边增加外部侧向走廊和画布范围计算，视觉 Critic 检查边穿节点、退化线段和 SVG viewBox；
- 增加固定 M0 Figma 本地 smoke test，验证原生 `FRAME/RECTANGLE/TEXT/LINE`、语义 parity、mock 状态和显式 connected identity。

验证结果：

~~~text
python -m pytest -q
152 passed, 16 warnings
~~~

警告仍来自 Starlette multipart 和 httpx 的弃用提示。真实 Figma M0 已完成：File `8nWpDqYrB3S2aUbUiPnwKS`、Frame `1:2`，读回了中文 TEXT、RECTANGLE、VECTOR 边和 GROUP，并完成 SVG/PDF 导出。独立人工单栏/双栏盲评仍未完成。本地 mock 或 heuristic 分数不会被标记为真实 Figma 或投稿级证明。

## 29. Release Gate R1–R3 实施记录

最新审查将剩余工作收缩为三个 Gate：

### R1 真实 Figma M0

增加了 [figma_m0.py](../src/figure_agent/figma_m0.py) 和 `figure-agent figma-m0`。固定 M0 图包含中文节点、一个分组、正常数据边和“若证据不足”反馈边。无远程 Transport 时生成完整的本地证据包，并明确写入 `status=unavailable`；注入式 Transport 必须同时提供写入、读回和 SVG/PDF 导出方法，才允许记录 `connected`。本次真实证据位于 `outputs/figma-m0-rc1/`，包含 File/Frame 标识、读回、Parity、SVG/PDF 和 smoke.log。

### R2 独立视觉评测

新增人工维护的 [benchmark_20.json](../eval_cases/visual_quality/benchmark_20.json)，包含 5 个 pipeline、5 个 RAG/Agent、4 个分支、3 个循环和 3 个多智能体案例。`figure-agent generate-benchmark` 已生成 20 × 3 个候选，机器预检结果为 60 个候选、0 个结构/几何错误；这只是预检，不是人工审美结论。

`figure-agent build-review-sheet` 生成 120 行人工评分表（20 案例 × 3 候选 × 单栏/双栏）。评分包括语义正确、无重叠/裁剪、文字可读、箭头清晰、信息层级和论文美观度，并记录硬失败类型。人工评分尚未填写，因此 R2 未通过。

### R3 动态许可证审计

模板检索结果现在记录获取时间、来源、许可证证据、内容身份哈希和哈希作用域。未嵌入的模板仅作为结构参考；真正嵌入的模板或用户资产必须有来源、许可证证据、获取时间和内容 SHA-256，否则正式导出阻断。`review_required`、`unknown` 和 `rejected` 资源继续阻断导出。



R1 当前状态：PASS（固定 M0）。R2：PENDING（120 条评分尚未填写）。R3：代码、内容变更校验和真实 Lucide ISC 一正两负测试 PASS；真实用户素材审计待进行。
