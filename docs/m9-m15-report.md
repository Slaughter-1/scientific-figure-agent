# M9–M15 实施报告

## 已交付

- **M9**：`FigureRequest` 统一 `paper_text`、`figure_caption`、`csv`、`json`、`existing_spec` 和 `user_assets` 请求；Figure Spec 0.2 增加 provenance、evidence、constraints、template_refs、asset_refs、panel、candidate_id、review_notes 等字段。解析节点保留输入句证据。
- **M10**：建立可审计模板目录和 `search_templates`，记录来源、许可证状态、可编辑性、支持图类型、组件和限制。`open_license_first` 只返回已验证或项目自有记录。
- **M11**：组件包生成器输出 manifest、尺寸/颜色规范和逐组件提示词；SVG、PNG、PDF、Draw.io、Figma JSON 素材可登记并映射回节点。
- **M12**：同一 Figure Contract 默认生成三种候选布局，分别偏向结构完整、论文版式和视觉层级，并记录证据、结构、可读性、风格与许可证评分。
- **M13**：已有 Figma scene compiler 和 `FigmaTransport` 作为连接层；离线输出本地 scene，注入 transport 时支持 mock、connected 和 error 状态，不猜测未知 MCP schema。
- **M14**：新增 scene 几何检查和 SVG 检查，检测节点重叠、越界、缺失尺寸、缺失文字，并在 `inspect` 输出 `visual_findings`。
- **M15**：新增确定性案例评测 API，统计节点召回率、边召回率和证据覆盖率，可聚合 20–30 个外部案例。

## 当前链路

```text
论文段落 / CSV / JSON
  → Figure Contract / Plot Spec
  → 模板目录或组件包
  → 三个 Figure Spec 候选
  → Draw.io / Matplotlib / 本地 Figma scene
  → 结构 Critic + 视觉检查
  → SVG / PDF / PNG / 可编辑源
  → manifest、provenance、license、评测结果
```

## 验收结果

当前回归套件共 **92 个测试通过**。除既有 CLI 外，已增加 Spec 0.3 迁移、SQLite 任务仓储、FastAPI 本地 API、候选导出 ZIP、LLM Provider 协议和 React/Vite 前端构建验证。

## 边界与后续工作

当前 P0/P1 已完成本地任务目录、SQLite 持久化、论文分析、候选生成、候选选择和图包导出。真实 Figma 文件写入仍取决于运行环境是否提供实际 MCP transport；模板检索仍是可审计的本地注册表；LLM Provider 已提供协议、Mock、Unavailable 和 OpenAI-compatible 实现，但默认仍使用规则解析器。下一阶段接入 LLM 语义规划、官方模板网络适配器、完整审阅操作和视觉自动精修。
