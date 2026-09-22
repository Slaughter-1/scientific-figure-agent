# RC2 Closeout Audit Evidence

本包来自当前工作区快照，不是上一轮 188 测试的旧 ZIP。

## 本轮结果

- 语义边界回归：并列模态不生成数据流；否定并行进入待审；模糊分支尾部不生成孤立节点；Critic 识别裸“返回目标”反馈。
- 反馈边在 pipeline 布局使用独立外部通道；swimlane 路由也会检测并分离反向共线的正向边。
- 导出前会比较任务根目录 Contract 与已确认修订 Spec 内嵌 Contract；ZIP 重读会交叉验证 Contract、request/source、candidate pointer、revision、selected binding 和 evidence manifest。
- `python -m pytest -q`：205 passed, 22 warnings。
- `cd frontend; npm run build`：成功。
- 真实 API 任务：创建 → 分析 → 生成 3 候选 → 选择 candidate_02 → 导出；正式 ZIP 重新读取并校验文件 hash、Contract、输入摘要、任务、候选和 Spec revision。

## 证据

`task/` 是同一任务的原始 request、Contract、三个候选的 Spec/Draw.io/SVG/PDF/PNG、修订目录、审阅记录、任务级 `evidence-manifest.json` 和实际导出 ZIP。`verification/` 保存完整日志、语义烟测和工作区身份。最新本地 API 复跑产物位于 `outputs/rc2-closeout-task-v2/`。

## 边界

源码和测试已在本轮验证后冻结到本地 Git 提交；具体提交、产物 SHA-256 和环境记录见 `docs/RC2_SOURCE_FREEZE.md` 与 `outputs/rc2-closeout-task-v2/freeze-manifest.json`。生成产物仍作为任务证据保存，不把未提交的旧 HEAD 当作本轮源码身份。此包不是独立人工视觉 holdout，也不证明投稿级质量。历史 Figma M0 记录仍保留，但当前几何修订尚未完成新的真实远程 Figma smoke；本包也没有把未经复核的外部素材标成可投稿成品。

## 本轮收尾边界

- `candidate_02` 的 `node_0→node_2` 与 `node_2→node_3` 不再反向共线；新增 `edge_reverse_overlap` 几何错误检查，防止未来回归。
- 根 Contract、request/source、候选指针、修订身份和 ZIP 内 evidence 选择绑定必须相互一致；故障注入测试会拒绝旧修订号和错误输入摘要。
- 204 项 Python 回归和 fresh API 三候选 smoke 已执行；真实远程 Figma 写入、独立人工 holdout、外部素材许可证审计仍是单独发布门槛。
