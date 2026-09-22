# RC 收口计划与验收边界

依据：2026-09-21《技术审查摘要》最新回复。优先级：历史 P0 → Figma M0 → 独立视觉评测 → 实际外部资产的许可审计。

| Gate | 本轮开发与验收 | 交付证据 |
|---|---|---|
| G1 修订一致性 | 选择绑定 revision 与实际 Spec hash；陈旧编辑拒绝；产物校验；ZIP 写入后重新读取校验 | API 回归、前后修订、ZIP、完整 pytest 日志 |
| G2 审阅语义 | issue 逐条处理，记录 issue_revision / resolution / reason / evidence_refs / resolved_at / result_revision；拒绝空白或重复证据 | API 回归与审阅日志 |
| G3 Contract | 初始编译及导出校验必需节点、边方向、边类型及条件标签 | Contract 反例回归 |
| G4 格式一致性 | 同一个 Spec 的 Draw.io、SVG、PDF、PNG；条件标签与删除结果核对 | XML/SVG 检查、PDF 文本提取与 PNG 实图 |
| G5 几何 | 保留穿节点反例，反馈路由避障；画布包含边、标签和分组；统一 Draw.io 与预览节点几何 | 路由检查、实际渲染 smoke |
| G6 Figma | 固定中文 M0、group、条件反馈边；真实写入、读回、SVG/PDF 导出 | 真实工具日志和远程标识；连接失败只能记未通过 |
| G7 许可证 | 真正嵌入的外部资源必须有明确许可和证据；发现用的目录链接不作为已复用模板 | 发布门禁回归 |
| G8 独立视觉 | 单栏/双栏尺寸的人工盲评；不能由 heuristic 评分或自动测试替代 | 独立评审表，未评审不能标通过 |

Figma 的 mock 测试只验证协议，不证明远程写入；PNG/PDF 渲染成功不代表审美或投稿质量通过。失败时保留中间产物。完整结果与未关闭项记录在本文件后续验收记录中。

## 本轮记录

- `python -m pytest -q`：`139 passed, 16 warnings`；
- `npm run build`：Vite production build 成功；
- Figma M0 本地 scene/parity/mock/显式 connected identity 测试通过；
- 真实 Figma `whoami` 因 MCP HTTP transport 错误未取得远程身份，G6 不宣称通过；
- G8 独立人工单栏/双栏盲评尚未执行，系统不会将 `publish_ready` 标记为 true。

## RC1 冻结记录

最新审查要求进入验收冻结后，已将当前 60 个候选复制到 `outputs/visual-benchmark-rc1/snapshot/`，生成 120 条匿名评审条件和 [freeze-manifest.json](../outputs/visual-benchmark-rc1/freeze-manifest.json)。冻结包内保留原始候选的文件哈希，不再重新渲染。案例来源已明确标为 `ai_authored_synthetic`，尚未作为人工金标准。

`outputs/visual-benchmark-rc1/reviewer/index.html` 是不带 candidate/revision 名称的盲评页面；`private-mapping.json` 只留在本地，不应交给评审员。评审门槛按单栏、双栏分别计算：可读性均值 ≥4.5、箭头清晰度均值 ≥4.3、美观度均值 ≥4.0，且硬失败为 0。空白评分当前明确为 `release_ready=false`。

R1 已有真实 Figma M0：File `8nWpDqYrB3S2aUbUiPnwKS`，Frame `1:2`；读回包含中文 TEXT、RECTANGLE、VECTOR 边和 `agent-loop` GROUP；Figma 实际导出 PDF 已保存至 `outputs/figma-m0-rc1/export.pdf`，SVG 已保存至同目录。该结论只覆盖固定 M0，不代表所有候选都自动接入 Figma。
