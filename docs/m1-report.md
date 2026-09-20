# M1 验证报告

M1 已将 Figure Spec 扩展为四类图的统一契约，并增加了可复用的样例集。

已覆盖：

- `architecture`：模块、数据流和分组容器；
- `workflow`：按阶段排列的流程节点；
- `graph`：依赖关系和控制流；
- `plot`：图表类型和数据块；
- groups 的节点引用校验；
- plot 数据块和图表类型校验。

验证命令：

```powershell
python -m pytest -q
```

结果：13 个测试通过。

Draw.io MCP 已安装到本机：

```text
drawio-mcp 1.6.0
```

Figma MCP 仍属于远程/账号连接型能力，需要在 Codex/Figma 连接中配置，无法通过本地 npm 包完成。
