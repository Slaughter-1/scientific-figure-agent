# 当前质量审查与后续计划

## 验证结果

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 回归测试 | 通过 | 72 tests passed |
| Python 语法编译 | 通过 | `python -m compileall -q src tests` |
| Python 模块入口 | 通过 | `python -m figure_agent --help` |
| wheel 构建 | 通过 | `pip wheel --no-deps . --wheel-dir dist` |
| 论文段落候选生成 | 通过 | KATE、Towards Atoms 各 3 个候选 |
| CSV 数据图 | 通过 | KATE BFCL/AppWorld、CounterFact 汇总 |
| 本地矢量导出 | 通过 | Draw.io、SVG、PDF、PNG |
| 真实 Figma 写入 | 通过 | Frame `2:3`，14 个原生子节点 |
| provenance / license manifest | 通过 | `research_data/sources.json` 和各输出 manifest |

## 当前质量等级

当前项目达到“可复现实验原型”阶段：输入、Figure Contract、Figure Spec、三候选、局部数据图、Draw.io/SVG/PDF/PNG、Figma 原生 smoke test 和检查报告已经贯通。核心库的外部连接通过协议注入，离线环境可以继续运行。

它还没有达到“自动生成可直接投稿的最终科研图”阶段。视觉精修尚未形成完整的自动迭代闭环，网络模板检索目前是本地可审计目录，Figma 写入已经验证但真实 MCP 调用仍通过外部 bridge 注入。

## 已识别风险

- 复杂论文中的跨层依赖仍可能被简化；显式 `[A | B]` 分支、自然语言分支和明确的 `loop back to`/`循环回到` 语法已经支持，开放式循环表述仍需要语义审阅。
- 当前 Plot Spec 已支持单系列误差线（bar/line/scatter）并记录误差列 provenance；分组、多系列、显著性标记和单位规范仍有限。
- 远程模板的实时搜索、许可证证据抓取和缓存尚未接入；未知许可证不会自动标记为可投稿。
- Figma 的真实写入依赖当前 MCP/API 连接和账号权限；本地 scene 与 Draw.io 后备路径已经可用。
- 已建立 12 个公开 LLM/NLP/Agent 案例的回归语料，当前指标验证的是人工整理 method chain 的解析一致性；M15 仍需扩展到 20–30 个案例并加入独立人工标注。

## 后续优先级

1. 将 `ConnectedFigmaDriver` 接入候选选择流程，新增 `figure-agent push-figma --candidate ...`，自动写回 file key、Frame ID、节点计数和截图结果。
2. 扩展 Figure Contract 解析，加入事实句/方法句/结果句/约束句分类、分支和循环关系，并对不确定语义生成 `needs_review`。
3. 增加 Plot Spec 的多系列、误差线、单位、显著性和分组轴支持。
4. 接入网络模板搜索适配器，所有搜索结果先进入 `TemplateRecord`，许可证证据和下载时间写入 manifest。
5. 建立 20–30 个 LLM/NLP/Agent 案例，执行节点召回率、边方向准确率、证据覆盖率、视觉检查通过率和导出成功率评测。
6. 增加候选对比页面或 HTML 报告，让用户可以查看三种方案、评分、证据和许可证取舍后锁定候选。
