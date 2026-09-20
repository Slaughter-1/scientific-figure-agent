# M7 验证报告

M7 将 M2 的基线解析器扩展为带证据溯源的 Figure Planner，并增加轻量级 Figure Classifier。

- 每个解析节点包含 `evidence: [{"source": "input_text", "quote": "..."}]`；
- 分类器支持 `architecture`、`workflow`、`graph` 和 `plot`；
- 字典输入优先使用已有 `figure_type`，包含 plot data 时可识别为 `plot`；
- 文本分类只使用可解释关键词，无法确定时回退到 `workflow`，不会虚构新的研究模块。

验证命令：

```powershell
python -m pytest -q
```

结果：35 个测试通过，M2 的五个固定案例均保留原有节点和边数量，并新增证据字段。
