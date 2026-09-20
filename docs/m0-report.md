# Scientific Figure Agent M0 报告

## 结果

M0 已验证本地 Figure Spec、Matplotlib 和 Draw.io 兼容输出链路。Figma 原生画布暂未验证，因为当前 Codex 会话没有可调用的 Figma MCP 连接。

| 成功标准 | 状态 | 证据 |
|---|---|---|
| 固定 Figure Spec 可通过校验 | 通过 | `examples/m0/workflow.json`、`tests/test_spec.py` |
| 生成 Draw.io 可编辑源和矢量导出 | 通过（本地后备） | `outputs/m0/workflow.drawio`、`workflow.svg`、`workflow.pdf` |
| CSV/JSON 示例生成 Matplotlib 矢量图 | 通过 | `outputs/m0/benchmark.svg`、`benchmark.pdf` |
| Figma 原生节点和导出 | 未验证 | `docs/m0-validation-report.md` |

## 验证命令

```powershell
python -m pytest -q
python scripts/check_environment.py
python scripts/render_m0_plot.py
python scripts/render_m0_drawio.py
```

## 当前限制

- M0 使用手写 Figure Spec；文本到 Figure Spec 的 Planner 属于 M2。
- Draw.io 使用本地 XML/SVG/PDF 后备生成器；官方 MCP 的具体连接尚未在当前环境中运行。
- Figma 只准备了 smoke prompt，未声称原生画布验证成功。
- Critic/Refiner 尚未实现。

## 下一步

先在有 Figma MCP 的连接中运行 `examples/m0/figma_prompt.md`，更新验证报告；随后进入 M1，完善 Figure Spec Schema 和更多样例。
