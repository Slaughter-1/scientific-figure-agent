# M8 验证报告

M8 完成了 CSV/JSON → Plot Spec → Matplotlib 的直接入口，并为 Figma scene 写入增加了可注入 transport 边界。

CSV 示例：

```powershell
python scripts/plot_next_stage.py plot --input examples/m8/results.csv --kind bar --x method --y accuracy --output-dir outputs/m8 --title "Benchmark Accuracy"
```

该命令生成 `plot-spec.json`、PDF、SVG、PNG 和 `manifest.json`。表格来源、列映射和 Spec hash 都保存在产物中。

Figma transport 支持三种状态：没有 transport 时为 `unavailable`，离线 driver 时为 `mock`，外部连接成功时由 transport 返回 `connected` 和 `file_or_frame`。transport 失败时仍保留本地 scene JSON。

验证结果：

```text
47 passed
```
