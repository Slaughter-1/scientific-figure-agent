# Figma 最小接入记录

已完成一次真实 Figma smoke test：

1. 通过当前 Figma 连接创建 Design 文件 `Scientific Figure Agent Smoke Test`。
2. 将 `outputs/research/kate_method/candidate_01/figure-spec.json` 转换为原生 Figma 节点。
3. 验证了 Frame、Rectangle、Text、Line 四类节点均为原生节点。
4. 通过截图检查文字、连线和画布边界，并修复了字体和第五个节点被裁剪的问题。

结果和文件标识记录在 [`outputs/research/figma-smoke-test.json`](../outputs/research/figma-smoke-test.json)。

## 当前连接方式

仓库核心仍使用 `FigmaTransport` 协议，保持本地 scene、mock、connected、error 四种状态。当前运行环境的真实连接通过 Figma MCP 的 `use_figma` 工具执行；核心代码不写死 MCP 调用，因此离线运行仍能生成 `figure.figma-scene.json`。

## 后续接入范围

下一步可以把候选 Figure Spec 的节点创建逻辑封装成仓库内的 transport adapter，并在每次真实写入后自动回填 file key、frame id、节点计数、截图检查结果和导出链接。当前 smoke test 已证明账号、计划和写入权限可用，不需要额外注册账号。
