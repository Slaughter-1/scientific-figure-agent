# Scientific Figure Agent 设计说明

## 1. 目标

Scientific Figure Agent 面向 LLM、NLP 和 Agent 论文，将方法描述、图注或实验数据转换为可验证、可编辑、可导出的科研图。

第一阶段的目标链路是：

```text
方法描述 → Figure Spec → Draw.io 草图 → Figma 精修 → SVG/PDF
CSV/JSON → Figure Spec → Matplotlib → SVG/PDF
```

系统的核心价值不是模拟鼠标操作，而是建立一份跨后端复用的结构化 Figure Spec，使同一份图意可以在不同工具中保持一致。

## 2. 用户与成功标准

主要用户是需要制作 LLM/NLP/Agent 论文方法图、工作流图和实验结果图的研究者。

V1 成功标准：

1. 给定一段方法描述，能生成结构正确的 workflow Figure Spec。
2. 同一份 Spec 能生成可编辑 Draw.io 图。
3. 同一份 Spec 能生成基本符合学术风格的 Figma 图。
4. 给定 CSV/JSON，能生成适合论文尺寸的柱状图或折线图。
5. 输出包含 SVG/PDF，并能通过结构和视觉质量检查。

## 3. 范围

### V1 包含

- `architecture`、`workflow`、`graph`、`plot` 四类图。
- `model`、`tool`、`data`、`process`、`storage`、`decision` 六类节点。
- `data_flow`、`control_flow`、`dependency` 三类边。
- 左到右、上到下和分组布局。
- Draw.io、Figma、Matplotlib 三个后端。
- 学术风格模板、颜色语义、字体和线条规范。
- 结构 Critic、视觉 Critic 和一轮自动修正。
- SVG、PDF、PNG 以及 Figure Spec 元数据导出。

### V1 不包含

- 自由风格插画和 teaser 图。
- 整篇论文自动排版。
- 复杂公式的专门可视化。
- 无人审核的最终投稿承诺。
- 以 raster 图片作为唯一源文件。

## 4. 系统架构

```text
Input Parser
    ↓
Figure Classifier
    ↓
Figure Planner
    ↓
Figure Spec Validator
    ↓
┌──────────────┬──────────────┬──────────────┐
│ Draw.io      │ Figma        │ Matplotlib   │
│ 草图后端      │ 精修后端      │ 数据图后端    │
└──────────────┴──────────────┴──────────────┘
    ↓
Critic / Refiner
    ↓
Exporter
```

### Input Parser

统一接收方法描述、figure caption、用户约束和 CSV/JSON。解析失败或信息不足时，返回需要补充的字段，不直接臆造模块。

### Figure Classifier

根据输入内容判断图类型并选择后端。架构和 workflow 默认走 Draw.io → Figma；graph 默认走 Draw.io；plot 默认走 Matplotlib；混合图先拆分为结构面板和数据面板。

### Figure Planner

抽取节点、边、层级、输入输出和分组，生成 Figure Spec。每个节点可以携带 `evidence`，记录它来自哪段原文或用户输入，支持后续溯源。

## 5. Figure Spec

Figure Spec 是系统的稳定接口。后端不重新理解论文，只负责将 Spec 渲染成目标格式。

最小结构如下：

```json
{
  "schema_version": "0.1",
  "figure_type": "workflow",
  "title": "Agent Workflow",
  "layout": {"direction": "left-to-right", "spacing": 24},
  "nodes": [
    {
      "id": "planner",
      "label": "Planner",
      "type": "process",
      "group": "reasoning",
      "evidence": [{"source": "method.md", "quote": "..."}]
    }
  ],
  "edges": [
    {"source": "input", "target": "planner", "type": "data_flow", "label": "query"}
  ],
  "groups": [],
  "style": {
    "theme": "academic_clean",
    "font_family": "Arial",
    "font_sizes": {"title": 10, "node": 8, "annotation": 7},
    "colors": {
      "model": "#DCEBFA",
      "process": "#E8EEF7",
      "data": "#F2F4F7",
      "storage": "#EFE7FA"
    }
  }
}
```

Schema 校验必须在任何后端执行前完成，至少检查：节点 ID 唯一、边的端点存在、节点类型合法、布局方向合法、颜色和字体字段完整。

## 6. 后端接口

每个后端实现相同的接口：

```text
validate(spec) -> ValidationResult
render(spec, options) -> ArtifactSet
inspect(artifact) -> InspectionResult
```

- Draw.io 后端输出 `.drawio`，可选输出 SVG/PDF/PNG。
- Figma 后端把节点、文本、连接线和分组写入原生 Figma Canvas，保留可编辑结构。
- Matplotlib 后端读取 plot 数据、坐标轴、图例和尺寸设置，输出 PDF/SVG/PNG。

已有的官方 Draw.io MCP、Figma MCP 和 publication-chart 工具链作为执行基础；Scientific Figure Agent 自己负责语义规划、Spec、路由和质量验证。

## 7. 学术风格系统

默认使用 `academic_clean`：白色背景、统一无衬线字体、细线条、有限颜色、圆角模块和明确的阅读方向。

颜色只表达稳定语义，例如模型、工具、数据、存储和决策。禁止依赖颜色单独表达信息，也禁止默认使用 3D、阴影、渐变、装饰性插画和过小文字。

所有后端共享同一组 style tokens，避免 Draw.io 草图、Figma 精修图和数据图出现明显风格漂移。

## 8. Critic / Refiner

Critic 分为三层：

1. **结构检查**：遗漏模块、多余模块、孤立节点、无效端点、箭头方向和分组关系。
2. **视觉检查**：重叠、越界、未对齐、文字过小、颜色过多、线条不一致。
3. **科研规范检查**：标签是否来自输入、阅读顺序是否清晰、缩小到单栏或双栏宽度后是否可读。

第一版只自动修正确定性问题，例如间距、对齐、文字溢出和颜色 token；涉及语义增删时只给出建议并等待人工确认。

## 9. 交互形态

V1 先提供 CLI/API，而不是先开发完整画布编辑器：

```text
figure-agent generate --input method.md --type workflow --backend drawio
figure-agent render --spec figure.json --backend figma
figure-agent plot --input results.csv --kind bar --export pdf
figure-agent inspect --artifact outputs/figure.svg
```

每次运行保存输入摘要、Figure Spec、后端产物、检查结果和导出文件，便于复现和比较版本。

## 10. 验证策略

- Schema 单元测试：覆盖合法 Spec 和错误 Spec。
- 后端冒烟测试：每个后端至少生成一张固定示例图。
- 语义测试：用 5 个 LLM/Agent workflow 案例检查节点和连接关系。
- 导出测试：确认 SVG/PDF 可打开、无裁剪、文字可读。
- 一致性测试：同一 Spec 在多个后端中节点和边的集合一致。
- 人工评审：检查论文尺寸、灰度可读性和最终视觉层级。

## 11. 里程碑

- **M0**：确认 Draw.io MCP、Figma MCP、Matplotlib 的最小链路。
- **M1**：完成 Figure Spec Schema、Validator 和三个样例。
- **M2**：完成方法描述到 Spec 的 Planner，先支持 architecture/workflow。
- **M3**：完成 Draw.io 后端和 SVG/PDF 导出。
- **M4**：完成 Figma 原生节点后端和 academic_clean 模板。
- **M5**：完成 Matplotlib 数据图后端。
- **M6**：加入 Critic、Refiner 和跨后端一致性检查。

## 12. 主要风险

- Figma MCP 的写入能力依赖账号、文件权限和当前客户端配置，因此必须保留 Draw.io/SVG 作为本地可复现后备路径。
- 自动生成的结构可能在视觉上正确但语义上错误，因此所有节点都应尽量保存原文证据。
- 不同后端的布局算法不同，不能要求像素级一致；V1 只要求语义和视觉规范一致。
- “投稿级”需要明确目标会议、单双栏尺寸和字体规范，默认模板只能作为初稿标准。

## 13. 推荐的项目定位

项目不再定位为“另一个文本生成图片的 Agent”，而定位为：

> 面向 LLM/NLP/Agent 论文的科研图编译器：以 Figure Spec 为中间表示，将论文语义可靠地编译为可编辑 Draw.io 图、Figma 图和数据结果图，并通过结构化 Critic 进行验证。

