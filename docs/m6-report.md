# M6 验证报告

M6 增加了结构化 Critic/Refiner：

- `critique_spec` 检查 Figure Spec 校验错误、缺少标题、重复标签、悬空边和无连接图；
- 每条发现包含稳定的 `code`、`severity` 和 `message`，便于后续接入 LLM 评审器或 CI；
- `refine_spec` 只执行低风险元数据修复：补齐空样式对象和默认标题，不会擅自删除边或改写研究内容。

验证命令：

```powershell
python -m pytest -q
```

结果：22 个测试通过。
