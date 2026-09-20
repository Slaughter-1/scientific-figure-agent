# 下一阶段验证报告

本阶段完成了统一渲染编排的第一版：

- Draw.io、Figma scene 和 Matplotlib 由同一个 router 调度；
- Figma 未连接时生成本地 `figure.figma-scene.json`，状态明确为 `unavailable`；
- 每次运行生成 `manifest.json`，包含 Spec SHA-256、后端状态、产物路径和限制；
- Draw.io 与 Figma scene 通过节点、标签和边端点 parity 检查。

运行示例：

```powershell
python scripts/render_next_stage.py render --spec examples/m0/workflow.json --backend all --output-dir outputs/next-stage
```

验证命令：

```powershell
python -m pytest -q
```

当前环境下 Figma MCP 未连接，因此报告中的 Figma 状态为 `unavailable`；本地 scene JSON 仍可用于检查和后续 MCP 写入。
