# M3 验证报告

M3 将 Draw.io 后端整理为统一的 `render_drawio_spec` 接口。输入经过 Figure Spec 校验后，会在同一个输出目录生成：

- 可编辑的 `.drawio` XML，包含节点、边和分组容器；
- SVG 预览，适合继续编辑或嵌入论文工作流；
- PDF 预览，适合直接检查版式。

布局方向、间距、节点类型颜色、标题和分组信息会参与输出。`check_drawio_output` 支持默认的 M0 工作流标签检查，也支持为任意 Figure Spec 传入自己的必需标签集合。

验证命令：

```powershell
python -m pytest -q
python scripts/render_m0_drawio.py
```

结果：19 个测试通过；M0 示例仍能生成 `workflow.drawio`、`workflow.svg` 和 `workflow.pdf`。

当前实现使用本地 XML 和 Matplotlib 预览生成，不依赖 Draw.io GUI 或远程 MCP，因此可以在无外部连接的环境中稳定运行。后续接入 Draw.io MCP 时，可以复用同一个 Figure Spec 和验收检查器。
