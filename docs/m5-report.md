# M5 验证报告

Matplotlib 后端现在提供 `render_plot_spec`，统一消费 plot Figure Spec 的 `data.kind`，支持 `bar`、`line`、`scatter` 和 `heatmap` 四种基础图表。每次渲染会同时输出 PDF、SVG 和 300 DPI PNG；标题、坐标轴标签和网格样式来自 Figure Spec。

验证命令：

```powershell
python -m pytest -q
```

结果：20 个测试通过，覆盖柱状图的既有接口以及其余三种图表的向量和位图输出。
