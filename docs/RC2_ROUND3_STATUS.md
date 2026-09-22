# RC2 Round 3 修复记录

本轮根据最新源码与产物审查结果继续收口，优先处理几何一致性、解析旁路、保守语义和 Critic 源文核对。

## 已修复

### 统一节点几何

`layouts.node_size` 现在是节点几何的唯一来源。Draw.io XML、Matplotlib SVG/PDF/PNG、布局避障和分组框都使用同一组 `style.node.width/height` 或 `style.node_width/node_height`。

这消除了此前的三套尺寸：路由尺寸、预览硬编码尺寸和 Draw.io 默认尺寸不一致的问题。当前候选的 XML 节点尺寸分别与其 Spec 中的 180×72、210×76、190×76 一致。

### PDF 兼容性

PDF 输出改用 Matplotlib Type 3 glyph outlines，避免 TrueType 声明与嵌入字体程序不一致。Round 3 smoke test 中，MuPDF 可以渲染标题、中文节点文字和条件标签，Poppler 转换无字体 mismatch warning。

### 解析路径

所有非箭头自然语言都进入显式 Prose parser；不再通过 `系统首先` 等固定前缀回退到旧解析器。新增了无害前缀、中文序列、否定关系和原始字符偏移回归。

### 保守语义

- `系统支持图像、文本两种输入` 作为输入类型分组，不生成图像→文本数据流；
- `不并行调用` 生成待审项，不生成肯定的并行扇出；
- 分支后的下一句从所有明确分支臂继续，而不是留下孤立的后续节点；
- 复合的命名角色动作保留为一个明确阶段，避免无证据拆出中间节点；
- `工具返回证据` 不再被当作反馈控制流。

### Critic 与图结构

Critic 现在同时读取：

- `metadata.source_text`；
- 节点 evidence；
- 边 evidence。

它可以发现完整原文描述的分支、并行和反馈在 Spec 中被删减的情况，并区分“返回结果”和“返回到已有阶段”。候选环检测改为标准 DFS，不再根据节点数组顺序误判无环图。

## 验证

```text
python -m pytest -q
188 passed, 16 warnings

frontend: npm run build
vite build succeeded
```

新增定向回归位于：

```text
tests/test_rc2_round3_regressions.py
```

Round 3 smoke 产物位于：

```text
outputs/rc2-round3-smoke/
```

三个候选的 `critique_spec_geometry` 均返回空严重问题；PDF 已分别用 MuPDF 和 Poppler 做渲染检查。

最新审查证据包位于：

```text
evidence/rc2-round3-audit-evidence-20260922.zip
```

## 尚未关闭

- 还没有生成新的独立人工 holdout；本轮反例只能作为开发回归；
- 还没有重新取得用户提到的精确三轮提示词文件和原始已评分盲评 JSON；
- Figma 真实远程写入和正式外部资产许可证审计仍按原计划单独验收；
- 当前候选布局已经避免节点穿越，但不应仅凭自动几何检查宣称投稿级美观。

## 后续收口（2026-09-22）

- API 现在为每个任务维护 `evidence-manifest.json`，绑定请求输入 hash、Contract、候选当前修订、节点/边证据覆盖、审阅动作和实际文件 hash；正式导出 ZIP 同时保存所选修订的同任务证据快照，并在重新读取 ZIP 时校验证据清单、任务和候选身份。
- 分支后的下一句只有在原文明确写出“汇合/合并/汇总/进入/交给”等汇合关系时才连接所有命名分支臂；裸的后续句继续保留 `unresolved_branch_join` 待审，不补猜测边。`不得/不应/不允许并行调用` 等否定措辞也只生成待审项，不生成肯定的扇出。
- Figma scene 编译器改用与 Draw.io、Matplotlib 预览相同的节点宽高 token，边端点也从该几何计算。新增烟测核对 Draw.io XML、Figma RECTANGLE、SVG/PDF 页面尺寸和 Poppler 转换。

本次验证：

```text
python -m pytest -q
195 passed, 18 warnings

cd frontend; npm run build
vite build succeeded
```

几何/PDF smoke 对三个候选均通过：节点尺寸与 XML/Figma 一致，SVG 与 PDF 页面尺寸一致，MuPDF 可提取文字，PDF 使用 Type 3 字形，Poppler 无 stderr。上述结果仍不替代独立人工视觉评测、真实 Figma 远程 smoke 或正式 holdout。

## RC2 收尾复核（2026-09-22）

根据最新技术审查，本轮只处理两个明确缺口：

- 导出前比较任务根目录 `figure-contract.json` 与确认修订 Spec 的内嵌 Contract；ZIP 重读进一步核对 Contract 内容、request/source 摘要、Spec source、候选指针、候选修订、selected binding 和 evidence manifest。
- swimlane 路由在发现不同边反向占用同一水平或垂直线段时，尝试使用图外通道和目标侧端口；几何 Critic 的 `edge_reverse_overlap` 同时检查两个方向。`candidate_02` 的 `node_0→node_2`、`node_2→node_3` 以及 `node_1→node_3` 与反馈边均已分离，五条语义关系保持不变。

新增回归覆盖：

```text
根 Contract 与确认 Spec 不一致 -> 导出 409
evidence 旧 revision / 错误 source 摘要 -> verify_package 拒绝
三个布局候选 -> 无水平或垂直 edge_reverse_overlap
```

本轮验证：

```text
python -m pytest -q
205 passed, 22 warnings
```

fresh API smoke 重新创建任务、生成三个候选、选择并导出 `candidate_02`，ZIP `verify_package` 返回 `verified`；实际 PNG 目视检查显示分析代理到回答代理的路径走独立外侧通道。产物保存在 `outputs/rc2-closeout-task-v2/`。

源码和测试已冻结到本地 Git 提交。真实远程 Figma 写入、独立人工 holdout 和外部素材许可证审计仍未关闭；这些门槛不因本轮代码回归而自动变为 PASS。
