# Scientific Figure Agent

**把方法描述转成可编辑图稿，并把输入证据、候选修订和正式导出绑定起来。**

Scientific Figure Agent 是一个本地科研绘图研发项目，面向 LLM、NLP、Agent 方法图及常见实验数据图。它提供自然语言到结构化 Figure Spec 的规则式解析、多候选布局、Draw.io 可编辑文件、SVG/PDF/PNG 预览，以及带版本和许可证检查的本地 Web/API 工作流。

> **当前定位：带质量限制的工程版本。** 安装、API、任务审阅、版本绑定和正式导出已经有工程验收记录；复杂自然语言解析、密集布局和自动科研终稿质量仍有限制。原 R2 和 S5 的 FAIL 保留，合格 S5 质量验收未成立。GitHub 托管和 Release 下载不等于质量评测通过。

## 目录

- [1. 功能与适用范围](#1-功能与适用范围)
- [2. 环境要求](#2-环境要求)
- [3. 安装与首次启动](#3-安装与首次启动)
- [4. Web 界面使用](#4-web-界面使用)
- [5. 命令行完整用法](#5-命令行完整用法)
- [6. HTTP API 与审阅操作](#6-http-api-与审阅操作)
- [7. 输出、版本与导出门禁](#7-输出版本与导出门禁)
- [8. 数据保存与部署边界](#8-数据保存与部署边界)
- [9. 项目结构与架构](#9-项目结构与架构)
- [10. 研发过程](#10-研发过程)
- [11. 开发、测试和发布](#11-开发测试和发布)
- [12. 常见问题](#12-常见问题)
- [13. 当前限制与验收状态](#13-当前限制与验收状态)
- [14. 许可证与第三方材料](#14-许可证与第三方材料)

## 1. 功能与适用范围

| 功能 | 入口 | 当前能力和边界 |
|---|---|---|
| 方法文本分析 | Web、`analyze`、API | 提取 Figure Contract、节点/边证据和待审问题；不是任意中文均可靠的通用理解器 |
| 三候选生成 | Web、`generate`、API | 根据结构使用 editorial/pipeline、swimlane、hierarchy、loop 等布局；复杂图可能留下待审项 |
| 真实论文栏宽 | `generate --paper-width`、API | 结构图支持单栏 85 mm、双栏 180 mm；对应 220 dpi PNG 约 736/1559 px |
| 结构化 Spec 渲染 | `render` | workflow、architecture、graph 可用 Draw.io 后端；plot 用 Matplotlib |
| 实验数据图 | `plot` | CSV/JSON 生成 bar、line、scatter、heatmap，支持多系列、误差列、用户给定的显著性文字 |
| 候选审阅与版本管理 | HTTP API | 删除/锁定节点、标注与解决证据、登记与批准素材；修改后新建修订并使旧选择失效 |
| 正式图包导出 | Web、HTTP API | 绑定已选择的当前修订，检查 Contract、待审项、许可证、几何及产物身份 |
| 素材引用 | `package`、`assemble`、HTTP API | 组件需求输出、资产登记和引用；**引用或随 ZIP 交付不等于已把图标视觉合成进图** |
| 模板目录 | `search-templates` | 检索内置静态目录及其来源记录，**不是实时互联网模板搜索** |
| Figma 本地交接 | `push-figma`、`figma-m0` | 保留本地 Scene 和 transport 扩展接口；本版本不承诺可直接远程写入 Figma |
| 研发评测工具 | `generate-benchmark`、`build-review-sheet`、开发脚本 | 生成评测条件、保留失败分母及组织审计；工具运行不等于独立评审通过 |

推荐用于明确的方法链、图稿初稿、可编辑结构图和实验数据展示。不要将未经复核的图直接作为科学事实或论文最终结论。

### 三个容易混淆的概念

- **候选文件**：生成器的原始输出，可有 `needs_review`；用于预览与检查。
- **正式导出 ZIP**：通过任务 API 的版本绑定和导出门禁后打包的当前修订。
- **投稿质量认证**：本项目没有完成这种认证；前两项成功不代表第三项成立。

## 2. 环境要求

| 组件 | 说明 |
|---|---|
| Python | `pyproject.toml` 声明 `>=3.10`；本轮 Windows 工程验收使用 3.13.7，首次使用优先选择 Python 3.13 |
| Python 依赖 | 核心为 Matplotlib；Web 使用 FastAPI、Uvicorn、python-multipart；以 `pyproject.toml` 为安装入口 |
| Node.js / npm | 从源码构建 Web 前端时需要。当前 lockfile 中 Vite/plugin-react 要求 Node `^20.19.0 || >=22.12.0`；可使用满足条件的 Node 22 |
| 中文字体 | 结构图优先 Noto Sans SC，回退 Microsoft YaHei、SimHei、Arial、DejaVu Sans。需实际安装含中文字形的字体 |
| Draw.io Desktop | 生成 `.drawio` 原文件和本地预览不是以它为前置；在原生客户端编辑或做原生往返时需要 |
| Figma | 非本地使用前置；远程写入还需要实际 transport、授权、权限和配额 |

初次安装需要下载依赖。默认本地文本生成链不调用云端 LLM，不要求 API Key。仓库中的 provider 类是扩展代码，并未接入默认生成流程。

GitHub 研发仓库与精简使用目录的相对结构一致：`pyproject.toml`、`src/`、`frontend/` 均位于项目根。请先进入该根目录再执行命令，而不是进入外层下载 ZIP 的父目录。

## 3. 安装与首次启动

### 3.1 获取项目

从 GitHub 获取研发仓库：

```bash
git clone https://github.com/Slaughter-1/scientific-figure-agent.git
cd scientific-figure-agent
```

或在仓库的 **Releases** 中下载 `Scientific_Figure_Agent` 精简使用包，解压并进入包含 `pyproject.toml` 的目录。源码 clone 适合维护和测试；使用包不附带历史测试、评测材料或数据库。

### 3.2 Windows PowerShell

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web]"
```

这里直接调用虚拟环境 Python，不要求修改 PowerShell 执行策略或全局 Python 安装。不要把项目安装进另一个旧副本的全局 editable 环境。

**从源码 clone 时，先构建前端：**

```powershell
Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
Pop-Location
```

精简使用包已经含 `frontend/dist/` 时可以直接运行；只有修改前端或需要重新构建时才执行上述命令。保留现有 `package-lock.json`，不要用随意升级依赖代替构建。

```powershell
.\.venv\Scripts\python.exe -m figure_agent.cli check-env
.\.venv\Scripts\python.exe -m figure_agent.web --host 127.0.0.1 --port 8765 --data-dir figure-agent-data
```

打开：

- 本地页面：`http://127.0.0.1:8765/`
- API 文档：`http://127.0.0.1:8765/docs`
- 健康检查：`http://127.0.0.1:8765/api/health`

终端中的服务需要保持运行；按 `Ctrl+C` 停止。

### 3.3 Linux / macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[web]'
(cd frontend && npm ci && npm run build)
python -m figure_agent.web --host 127.0.0.1 --port 8765 --data-dir figure-agent-data
```

这是对应的跨平台启动方式，不代表所有系统版本都完成了同等验收。中文字体仍需自行存在于本机；不要把 Windows 私有字体文件复制到仓库。

### 3.4 前端开发模式

后端在一个终端运行 `figure_agent.web`，另一个终端：

```bash
cd frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173/`。现有 Vite 配置把 `/api` 代理到 `http://127.0.0.1:8765`。修改了后端端口时，需要相应调整本地开发配置。

## 4. Web 界面使用

1. 在“论文段落或方法链”输入框中填写流程描述。
2. 点击“分析并生成 3 个候选”。页面依次创建任务、生成 Contract、调用候选生成。
3. 检查候选图、节点原文证据、设计取舍与下载文件。界面上的分数是启发式指标，不是通过质量评审的证明。
4. 点击“选择并导出当前修订”。系统先保存本次候选与 revision 的选择记录，再调用正式导出。
5. 导出被拒绝时，检查待审事项和服务返回的原因，不要手改候选 JSON 或清空待审列表绕过检查。

建议首次用简单明确的描述，例如：

```text
文本经过分词、编码后送入分类器并输出标签。
```

当前 Web 页面主要覆盖“输入 → 三候选 → 证据预览 → 选择导出”。**完整审阅动作通过 API 提供，页面尚未实现全部审阅按钮、数据表绘图面板或账号系统。**页面默认请求双栏；单栏通过 CLI 或 API 显式指定。

当前输入是方法文本，不会自动读取整篇 PDF、DOI 或论文链接。请先提取所需段落；`input_type` 枚举存在并不代表所有文件类型都有完整 Web 生成入口。

## 5. 命令行完整用法

下文使用已激活虚拟环境的 `python`；Windows 未激活时替换为 `.\.venv\Scripts\python.exe`。安装后也可用 `figure-agent` 命令。

### 5.1 分析和生成结构图

```bash
python -m figure_agent.cli analyze --input examples/quickstart/method.txt
python -m figure_agent.cli generate --input examples/quickstart/method.txt --output-dir outputs/my-single --candidates 3 --paper-width single_column
python -m figure_agent.cli generate --input examples/quickstart/method.txt --output-dir outputs/my-double --candidates 3 --paper-width double_column
```

`generate` 的参数：

| 参数 | 说明 |
|---|---|
| `--input` | UTF-8 文本文件，不是整个 PDF |
| `--output-dir` | 新输出目录；建议每次运行使用不同目录 |
| `--candidates` | 一般使用 1–3，默认 3 |
| `--paper-width` | `single_column` 或 `double_column`；默认双栏。当前不提供任意毫米宽度的公开参数 |
| `--policy` | `open_license_first`、`local_only`、`broad_search`，默认 `open_license_first` |

输出大致如下：

```text
outputs/my-single/
├── figure-contract.json
├── candidates.json
├── candidate_01/
│   ├── candidate.json
│   ├── figure-spec.json
│   ├── figure.drawio
│   ├── figure.svg
│   ├── figure.pdf
│   ├── figure.png
│   └── revisions/...
├── candidate_02/...
└── candidate_03/...
```

具体路径以本次 `candidate.json` 的 `spec_path` 和 `artifacts` 为准。随机修订 ID、输出路径和时间可能不同，不要求跨运行 ZIP 字节完全相同。

### 5.2 渲染已有 Figure Spec

```bash
python -m figure_agent.cli render --spec examples/m1/workflow.json --backend drawio --output-dir outputs/spec-workflow
python -m figure_agent.cli render --spec examples/m1/architecture.json --backend drawio --output-dir outputs/spec-architecture
python -m figure_agent.cli render --spec examples/m1/graph.json --backend drawio --output-dir outputs/spec-graph
python -m figure_agent.cli render --spec examples/m1/plot.json --backend matplotlib --output-dir outputs/spec-plot
```

Spec 描述节点、边、分组、样式和来源；执行校验以 `src/figure_agent/spec.py` 为准，不能假定静态 JSON schema 文件与全部 Python 校验完全等价。

`--backend all` 可以调用全部后端，但结构图的 Matplotlib-only 分支会被跳过；Figma 状态仍需单独读取，不能把整体命令退出 0 当作远程写入完成。

### 5.3 CSV/JSON 实验数据图

示例数据位于 `examples/quickstart/metrics.csv`，是演示数字，不是本项目实验结果。

```csv
method,accuracy,f1,std,significance
Baseline,0.71,0.68,0.02,
Variant,0.78,0.75,0.015,
Proposed,0.83,0.81,0.01,*
```

```bash
python -m figure_agent.cli plot --input examples/quickstart/metrics.csv --kind bar --x method --y accuracy,f1 --y-error std --x-label Method --y-label Metric --title "Demo metrics" --output-dir outputs/plot-bar
python -m figure_agent.cli plot --input examples/quickstart/series.json --kind line --x step --y loss --title "Demo loss" --output-dir outputs/plot-line
python -m figure_agent.cli plot --input examples/quickstart/series.json --kind scatter --x step --y loss --output-dir outputs/plot-scatter
python -m figure_agent.cli plot --input examples/quickstart/metrics.csv --kind heatmap --matrix-columns accuracy,f1 --output-dir outputs/plot-heatmap
```

JSON 格式支持记录数组，或者 `{"records": [...]}`：

```json
[{"step": 1, "loss": 0.8}, {"step": 2, "loss": 0.6}, {"step": 3, "loss": 0.4}]
```

关键规则：

- bar/line/scatter 必须指定 `--x` 和 `--y`；多个 y 列用逗号分隔。
- heatmap 使用 `--matrix-columns`，选中的列必须是数值。
- `--y-error` 为一个共享误差列或每系列各一个列；不会由系统替你计算实验误差。
- `--significance significance` 仅绘制输入列中的标记，不执行统计显著性检验。
- 生成 `plot-spec.json`、SVG、PDF、PNG 和 `manifest.json`；该数据图路径没有 Draw.io 源图输出。
- 数据图当前使用自己的 Matplotlib 尺寸和 300 dpi 输出；**结构图的 85/180 mm、220 dpi 规则不自动适用于 `plot` 命令。**

### 5.4 模板目录与组件需求

```bash
python -m figure_agent.cli search-templates --query workflow --policy local_only --limit 3
python -m figure_agent.cli package --spec examples/m1/workflow.json --output-dir outputs/components
```

`package` 输出 `component-manifest.json` 和 `component-prompts.md`，用于后续组件制作交接。**它不是正式任务 ZIP 导出命令，也不会自动调用图像生成模型。**

`assemble` 根据素材文件名与 node ID 的对应关系写入引用：

```bash
python -m figure_agent.cli assemble --spec examples/m1/workflow.json --assets my-assets --output outputs/assembled-spec.json
```

例如 Spec 的节点 ID 为 `tool`，对应素材名应为 `tool.svg`。`my-assets` 由使用者准备；新资产默认待审，不能把装配成功当成许可证批准或图标已经绘制到图中。

### 5.5 检查文件

```bash
python -m figure_agent.cli inspect --artifact outputs/my-single/candidate_01/figure.svg
python -m figure_agent.cli inspect --artifact outputs/my-single/candidate_01/figure.drawio
```

不同格式的 inspector 深度不同。PNG/PDF 的基础文件检查不等价于实际视觉检查。正式导出 ZIP 的强校验使用第 6 节所述 `verify_package`。

### 5.6 Figma 本地交接与远程边界

```bash
python -m figure_agent.cli push-figma --spec examples/m1/workflow.json --output-dir outputs/figma-handoff
```

此命令可生成本地 `figure.figma-scene.json` 和 `figma-manifest.json`。没有实际 transport 时，远端状态是 `unavailable`。

`--connection` 仅接收外部 bridge 返回的连接结果记录，不会仅凭一个手写 JSON 自动完成 OAuth、写入、读回或导出。`figma-m0` 在未注入 transport 的情况下退出 2 是未连接状态，不应伪造为成功。本次发布保留接口，**远程 Figma 功能不在已验证交付范围内**。

### 5.7 研发评测入口

这些命令可用，但日常使用不需要运行整套评测：

```bash
python -m figure_agent.cli generate-benchmark --cases examples/quickstart/benchmark-demo.json --output-dir outputs/benchmark-demo --paper-widths single_column,double_column
python -m figure_agent.cli build-review-sheet --cases examples/quickstart/benchmark-demo.json --output outputs/demo-review-sheet.json
```

示例只有一条公开演示 case，不是独立 holdout。`generate-benchmark` 兼容旧 `id/text/category` 列表及带 `cases[].task_id/source_text/category` 的 envelope；`build-review-sheet` 当前仍使用 flat list，并含内部身份字段，**不可直接当盲评包分发**。

正式盲化、审计、评分汇总在 GitHub 研发仓库的 `scripts/` 中；精简使用包不携带历史评測脚本、原评测材料、分数和私有映射。需要研究评测时使用完整研发 checkout，不从示例结果推断质量通过。

## 6. HTTP API 与审阅操作

API 默认仅绑定本机，不带生产级账号认证。实时请求定义和返回值以本机 `/docs`、`/openapi.json` 为准；部分请求体是自由字典，因此还需参照源码中的动作校验。

### 6.1 创建 → 分析 → 生成 → 选择 → 导出

在已经启动服务的机器上运行 PowerShell：

```powershell
$base = "http://127.0.0.1:8765"
$body = @{
  input_type = "paper_text"
  content = "文本经过分词、编码后送入分类器并输出标签。"
  candidate_count = 3
  paper_width = "single_column"
  template_policy = "local_only"
} | ConvertTo-Json -Depth 10

$task = Invoke-RestMethod -Method Post -Uri "$base/api/tasks" -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
$id = $task.task_id
Invoke-RestMethod -Method Post -Uri "$base/api/tasks/$id/analyze"
$result = Invoke-RestMethod -Method Post -Uri "$base/api/tasks/$id/generate-candidates"
$candidate = $result.candidates[0]
# 先检查 candidate.spec.needs_review、证据和实际图形，再进行选择。
$selection = @{candidate_id = $candidate.candidate_id; revision_id = $candidate.revision_id} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/tasks/$id/select-candidate" -ContentType "application/json" -Body $selection
$export = Invoke-RestMethod -Method Post -Uri "$base/api/tasks/$id/export" -ContentType "application/json" -Body '{}'
Invoke-WebRequest -Uri ($base + $export.download_url) -OutFile "selected-figure.zip"
```

示例演示请求关系，不保证任意输入、任意候选都能导出。若返回 409，应检查原因，不使用另一条绕过门禁的调用。

### 6.2 常用端点

| 方法／路径 | 用途 |
|---|---|
| `GET /api/health` | 服务健康状态 |
| `POST /api/tasks` | 创建任务 |
| `GET /api/tasks`、`GET /api/tasks/{id}` | 查询任务列表和单个任务 |
| `POST /api/tasks/{id}/analyze` | 构建并保存 Contract |
| `POST /api/tasks/{id}/generate-candidates` | 生成候选 |
| `GET /api/tasks/{id}/candidates` | 读取当前候选与 revision |
| `POST /api/tasks/{id}/search-templates` | 该任务下的静态模板目录查询 |
| `POST /api/tasks/{id}/select-candidate` | 绑定当前候选修订 |
| `POST /api/tasks/{id}/review-actions` | 执行支持的审阅动作 |
| `POST /api/tasks/{id}/assets` | multipart 上传，文件字段名为 `file` |
| `POST /api/tasks/{id}/export` | 正式版本化 ZIP 导出 |
| `GET /api/tasks/{id}/files/{path}` | 读取任务内已生成文件 |

### 6.3 支持的审阅动作

动作统一发送到 `/review-actions`。建议带上 `candidate_id`、当前 `base_revision`、实际节点 ID `target` 和明确 `reason`。

| action | 行为 |
|---|---|
| `lock_node` / `unlock_node` | 锁定／解锁节点 |
| `remove_node` | 删除未锁定节点及关联边和分组引用；删除 Contract 必需内容会形成冲突，不能直接导出 |
| `mark_needs_evidence` | 增加证据待审项 |
| `resolve_needs_evidence` | 提供真实证据并解决准确的 issue；输入原文引用必须确实包含在任务内容中 |
| `dismiss_review` | 带理由处理确认为不适用的普通问题；不能用它消除 Contract 必需项冲突 |
| `attach_asset` | 将任务内已上传资产登记到候选，默认不批准许可证 |
| `approve_asset` | 根据具名许可证、来源及许可证证据显式批准对应资产 |

例如，在前一节已有 `$candidate` 的前提下锁定一个节点：

```powershell
$action = @{
  action = "lock_node"
  candidate_id = $candidate.candidate_id
  base_revision = $candidate.revision_id
  target = $candidate.spec.nodes[0].id
  reason = "保留已确认的输入节点"
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri "$base/api/tasks/$id/review-actions" -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($action))
```

动作执行后应重新读取当前候选；不要继续复用旧 `$candidate.revision_id`。处理证据问题时使用返回的准确 `issue_id`，不能猜测 UUID。

本版本不是完整图形编辑器：不要从动作名推断已经支持任意加边、改标签或在线重画。必须重写科学结构时，可编辑独立 Spec 或 Draw.io 图稿；外部编辑不自动回写已有任务的确认修订。直接编辑任务内部 JSON 会触发身份不一致检查。

### 6.4 资产与许可证证据

上传素材和许可证文件后，使用返回的任务内路径进行 `attach_asset`。常用字段包括：`path`、`source`、`license`、`source_url`、`license_evidence_url`、`license_evidence_path`。

`approve_asset` 必须指定该候选中的 `asset_id` 和非空理由，并有可读、非空的许可证证据。批准导致新修订，之后需要再次选择当前候选版本才能导出。文件在批准后被改变，内容哈希检查会阻止正式导出。

这些检查验证记录和文件身份，不替代法律判断。不能把用户授权、公开素材 URL 或一个哈希自动解释为任意商业/论文用途都合法。

### 6.5 验证正式图包

安装项目后可以直接调用现有校验函数：

```bash
python -c "from figure_agent.artifacts import verify_package; import json; print(json.dumps(verify_package('selected-figure.zip'), ensure_ascii=False, indent=2))"
```

它面向任务 API 产生的正式图包，不是对 GitHub Release 应用 ZIP 的校验入口。Release 文件完整性使用下载附件提供的 SHA-256。

## 7. 输出、版本与导出门禁

每个候选有 `candidate_id`、`revision_id`、`revision_number` 和 `spec_sha256`。审阅动作会生成新修订，并重新渲染该修订的图形文件。旧修订保留用于追溯。

正式导出要求：已选择当前修订；没有未处理的 `needs_review` 和 Contract 冲突；证据、许可证和几何检查通过；实际文件与记录相符；输入、Contract、Spec、候选、选择记录和 evidence manifest 的身份对应一致。ZIP 写完还会重新读取校验。

常见状态码：

- **404**：任务、候选或文件不存在。
- **409**：旧修订、未选择、错绑、待审未解决、文件变化或正式包校验冲突。
- **422**：输入或动作字段不合格、证据/来源不完整等。

`export_ready=true` 表示当前正式图包通过相应检查；`publish_ready=false` 仍可能存在且是正常边界。通过哈希校验也不证明图中的科学关系都正确。

## 8. 数据保存与部署边界

默认工作数据目录：

```text
figure-agent-data/
├── figure-agent.sqlite3
└── tasks/<task_id>/
    ├── request.json
    ├── input/
    ├── versions/
    ├── candidates/
    ├── assets/
    ├── reviews/
    └── exports/
```

使用 `--data-dir` 指向独立目录。任务内容、上传素材、审阅记录和导出件均应当视为使用者数据，不提交 Git。备份 SQLite 时先正常停服务，或者使用 SQLite 支持的一致性备份方式；不要只在服务写入中随意复制单个数据库文件。

本版本以本地单用户工具为交付范围。**不要直接把无认证 API 监听到公网**。团队服务的认证、授权、配额、进程隔离与运维并不包含在本轮交付内。

`check-env` 通过 PATH 查找 Draw.io。未找到只表示当前探测未命中，不足以证明桌面客户端没有安装。生成预览与原生客户端验收应分别记录。

## 9. 项目结构与架构

```text
scientific-figure-agent/
├── README.md
├── pyproject.toml
├── src/figure_agent/
│   ├── cli.py, web.py
│   ├── request.py, workflow.py, parser.py, prose.py, planner.py
│   ├── spec.py, candidates.py, layouts.py, visual_styles.py
│   ├── critic.py, visual_critic.py, reviews.py, artifacts.py
│   ├── data.py, plot_planner.py, components.py, assembly.py, license.py
│   ├── app/              # FastAPI 与 SQLite 任务存储
│   ├── backends/         # Draw.io、Matplotlib、Figma 本地 Scene/transport
│   └── providers/        # 尚未接入默认流程的 LLM provider 扩展
├── frontend/             # React/Vite 源码、lockfile，使用包还包含 dist
├── schemas/
├── examples/
├── docs/                 # 使用边界、架构与研发过程
├── tests/                # 仅研发 checkout：必要自动回归测试与 fixture
└── scripts/              # 仅研发 checkout：维护、评测与验收脚本
```

处理主线：

```text
文本/结构化数据
  → 请求校验与规则解析
  → Figure Contract + 原文证据
  → Figure Spec
  → 候选样式与统一 RoutePlan
  → Draw.io / SVG / PDF / PNG
  → 审阅动作与 revision
  → 重新选择当前修订
  → 导出门禁与 ZIP 重新校验
```

关系有明确原文依据时建立；不明确的内容进入待审。RoutePlan 用于使预览、可编辑文件及检查使用同一套节点尺寸、端口和路径；这种一致性并不自动保证语义解析或版面选择都正确。

## 10. 研发过程

项目采用 AI 辅助工程迭代，Codex 与 Claude 先后参与实施，外部复核用于核对产物与执行记录。**AI 辅助开发、AI 评分、人工验收是三类不同事实。**本项目没有把 AI 评分声明为真人评审。

| 阶段 | 主要工作 | 留下的结果 |
|---|---|---|
| 基础工程 | Figure Spec、Draw.io/Matplotlib 后端、命令行与本地 Web | 建立从输入到图稿的运行链 |
| 语义修复 | 中文序列、分支、反馈、并行汇合、包含关系与否定续作；保留原文证据 | 指定反例回归修复，不宣称通用语言理解完成 |
| 布线一致性 | 统一节点几何、反馈通道、端口和 RoutePlan；处理 Draw.io 坐标与标签 | 减少预览与可编辑文件不一致 |
| 审阅与导出 | 审阅真实修改 Spec、新修订、旧选择失效、Contract 和产物身份检查 | 正式图包绑定到已确认的当前版本 |
| 栏宽与可读性 | API/CLI 栏宽透传、真实 85/180 mm 输出、标题边界与窄栏容纳 | 工程尺寸回归通过；复杂图仍可能待审 |
| 素材链 | 登记、显式批准、来源/许可证据和文件字节校验 | 已测试样例的正例及负例闭环 |
| R2 / S5 | 冻结、匿名评测与协议审计 | 原 R2/S5 FAIL 保留；S5 协议不符合，合格质量验收未成立 |
| 最终工程交付 | 精简应用与私有证据分离、新目录安装运行、原生代表性检查 | 带质量限制的工程交付完成 |

工程收口参考提交为 `54f4d10c34a3f6a9e78a313e7cc502556520ebcf`，该提交仅更新状态页；实际生成与评测工具变更在其祖先实现提交中。GitHub 发布整理可能产生新的文档/打包提交，应以 Release 指向的受测提交为准，不能把旧测试数字冒充新 CI 结果。

更多研发脉络见 [docs/DEVELOPMENT_HISTORY.md](docs/DEVELOPMENT_HISTORY.md)，验收范围见 [docs/ENGINEERING_STATUS.md](docs/ENGINEERING_STATUS.md)。这些是公开摘要，不包含私有评分、会话日志、机器路径或个人账号授权资料。

## 11. 开发、测试和发布

### 完整研发 checkout

```bash
python -m pip install -e '.[test,web]'
(cd frontend && npm ci && npm run build)
python -m pytest -q
python -m compileall -q src
```

历史工程基线记录为 `348 passed, 80 warnings`（Windows）。具体执行数和警告随版本/环境而定；查看实际退出码和失败原因，不以“凑齐历史数量”为验收方法。必要的回归 fixture 应随研发仓库或可复现的测试准备步骤提供，不能偷偷依赖开发者私有 outputs。

精简使用包不含 `tests/`、pytest 配置、研发报告、原始 holdout、评分或数据库，因此不要在使用包中照抄完整研发测试流程；用 Web/CLI 与正式导出进行使用验证。

### 贡献原则

修复只覆盖可复现的问题，添加针对性回归。保持原文证据、节点/边身份、栏宽和版本绑定；不要以更改评分门槛、删除失败案例或清空待审项代替修复。新实验使用新目录，历史结果保持可追溯。

### 发布形态

- GitHub `main`：完整研发代码、README、必要测试和构建配置。
- Release 的 `Scientific_Figure_Agent` 目录包：相同运行源码及预构建前端，不含过程测试和私有材料。
- 私有证据包：独立保存，不上传到公开仓库或公开 Release。

本次工程预览发布页：
[`v0.1.0-engineering.20260928`](https://github.com/Slaughter-1/scientific-figure-agent/releases/tag/v0.1.0-engineering.20260928)。
下载命名的 `Scientific_Figure_Agent` 使用包和同名 `.sha256` 校验文件；Release 不代表 R2/S5 质量通过。

只有正式 push 后从 GitHub 新 clone、安装并实际通过测试与业务验证，才能报告“远端版本完整可用”。GitHub 的自动 Source code ZIP 不一定含预构建前端；普通使用者优先下载命名的使用包附件。

## 12. 常见问题

**页面只显示 JSON 或提示 Frontend is not built。** 确认 `frontend/dist/index.html` 存在，按第 3 节构建后重启后端；确认运行的是当前目录，而不是另一个旧安装。

**修改后还是旧页面。** 重建前端、重启当前服务，再强制刷新浏览器。检查 `python -c "import figure_agent; print(figure_agent.__file__)"` 的实际位置。

**中文变方块或换行与别的机器不同。** 检查含中文字形的字体是否实际可被 Matplotlib 解析，安装字体后重启进程。`check-env` 不完整检查全部字形；图片文件存在不代表中文正常。

**Node 构建报版本不支持。** 检查 `node --version` 和 lockfile 的 engines，使用满足约束的版本，不随意删除 lockfile 或升级到未知依赖组合。

**生成成功但导出 409。** 可能是待审未解决、候选版本过期、没有选择、Contract 冲突、素材许可不足或文件被修改。读取错误详情及当前候选，不绕过正式门禁。

**为什么三候选有些不好看？** 规则解析与布局有实际限制。文件生成成功、启发式高分、完整性校验通过都不等同于论文终稿质量。

**为什么没有 API Key 配置？** 默认生成链是规则式。存在 provider 源文件不代表默认流程在调用外部 LLM。

**Figma 显示 unavailable，是否意味着本地工具不可用？** 否。本地图稿生成与远端 Figma 是分开的；本次远端范围排除。

**能否直接编辑 Draw.io 再覆盖任务文件？** 可以编辑独立导出的副本；不要覆盖任务内部已登记字节，否则版本与哈希校验会拒绝。该编辑不自动回写任务 Spec。

## 13. 当前限制与验收状态

2026-09-28 工程交付记录如下，不是对所有未来提交的测试承诺：

| 项目 | 状态 |
|---|---|
| 源码/应用恢复、API、业务闭环 | 已有通过记录 |
| 业务闭环 | 33/33 断言通过 |
| D 素材样例与许可证流程 | 54/54 断言通过，限已测正负路径 |
| 原生 Draw.io | 31.5.2 CLI，sequence/branch/mixed × 两栏共六个代表通过；非全部布局/完整 GUI 验收 |
| R2 原结果 | FAIL 保留 |
| S5 原报告 | FAIL 保留 |
| S5 协议符合性 | FAIL |
| 合格 S5 质量验收 | NOT_ESTABLISHED / S5_AGENT_INCOMPLETE |
| 人工评审 | 本周期未参与，也不再作为本次工程交付前置 |
| C/Figma | 排除，未用本地模拟替代远端验收 |

尚有复杂语义误判、长图/密集图、线条交叉和条件标签安放等限制。纯包含关系不应被误画成数据流。`needs_review` 需要真实处理，不是可以任意删除的日志。

## 14. 许可证与第三方材料

本次工程交付没有附带项目级开源 `LICENSE`；发布整理时如仓库已有经维护者确定的许可证，应以实际根目录文件为准。**不要因仓库公开，就自行把整个项目标为 MIT 或 Apache-2.0。**

Python/npm 依赖及用户引用的图标、模板拥有各自许可证。项目中的 Heroicons 素材验收使用了带 MIT 许可证据的样例，该许可证只说明相应素材，不自动成为本项目代码许可证。保留所分发第三方材料的原许可证和来源。

维护者：GitHub 仓库 `Slaughter-1/scientific-figure-agent`。提交问题时附复现步骤、版本、脱敏输入与错误输出；不要上传访问令牌、私人论文、任务数据库或未授权素材。
