# Visual Product 阶段验收报告

本阶段将原型推进到可审阅的本地 Web 工作流，覆盖中文渲染、候选视觉差异、证据审阅、实验数据图、许可证登记和 Figma 后备路径。

## 已完成

- 视觉样式层提供 editorial、swimlane、loop 和 hierarchy 设计族；布局层为节点和边生成不同位置与路线。
- 中文字体链路使用 Noto Sans SC，并保留 SVG 文本和 PDF 字体；Web 页面提供中文字体回退。
- 三个候选保存设计族、适用场景、取舍、评分和 preview fingerprint，视觉 Critic 可以识别重复候选。
- Web 页面显示候选预览、证据面板、评分条、源文件下载和预览失败状态。
- Figure Contract 能区分明确节点和不确定节点；节点缺少 evidence 时结构 Critic 报告严重问题。
- Review action 会写入 reviews 和 versions 目录，并记录 base_version、reason、approved_by 和时间。
- CSV/JSON 表格保存列类型、列级 provenance、多系列、误差线、单位和显著性标记。
- 模板和用户素材保存来源、许可证证据、审批状态、哈希、格式和可编辑性；存在 review_required 时 manifest 不会标记 publish_ready。
- Figma 不可用时保留本地 scene；注入 transport 后可以返回真实 file/frame 标识。

## 验证结果

```text
python -m pytest -q
113 passed, 6 warnings

npm run build
passed
```

警告来自 Starlette/httpx 的依赖弃用提示，不影响当前功能。前端内置页面需要先执行 `npm run build`，服务重启后访问 `http://127.0.0.1:8765/`。

## 当前边界

三候选现在具有可解释的版式和视觉差异，但仍属于结构化学术图范式；图标化插画、复杂 Figma 组件库和自动选择投稿级最终稿仍需要人工审阅。Figma 真实写入继续依赖用户已有账号、权限和外部 transport，系统不会自动注册账号。网络模板仍先登记为 TemplateRecord，许可证不完整时只能进入审阅流程。

## 下一步评测

`eval_cases/visual_quality/` 预留 Self-RAG loop、RAG 分支、中文 Agent 方法段落和多系列实验 CSV 的固定案例。评测脚本 `scripts/build_evaluation_report.py` 汇总节点召回率、边召回率、分支/循环召回率和证据覆盖率。
