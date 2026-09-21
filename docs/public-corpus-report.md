# Public LLM/Agent 论文评测集

本轮从公开论文页面和官方代码仓库筛选了 20 个案例，覆盖工具调用、RAG、Agent planning、网页代理、长程任务、多智能体和 LLM 可解释性：在原有 12 个案例基础上加入 LlamaIndex、WebArena、BrowserGym、Mind2Web、MetaGPT、CAMEL、Gorilla 和 Toolformer。

案例清单与来源在 [`research_data/public_paper_corpus.json`](../research_data/public_paper_corpus.json)。原始公开仓库下载到 `research_data/github/`，该目录被 Git 忽略；项目只提交整理后的方法链、来源和评测输出。

## 评测方式

每个案例的 `method_chain` 是根据论文摘要、官方 README 或本地论文分析整理的可审计流程摘要。系统使用这条摘要生成 Figure Contract、三个候选 Figure Spec 和 Draw.io/SVG/PDF 产物，再将候选节点和边与摘要中的期望链进行比较。

当前结果：

```text
case_count: 20
mean_node_recall: 1.0
mean_edge_recall: 1.0
mean_evidence_coverage: 1.0
```

这些指标代表当前规则解析器对已整理方法链的回归一致性，不代表模型已经理解了完整论文，也不代表对论文原图的视觉相似度。要评估科学语义准确率，还需要为每个案例补充人工核验的节点、边、分支、循环和禁止添加项。

## 已生成产物

- [`evaluation.json`](../outputs/research/public_corpus/evaluation.json)：聚合指标；
- [`cases.json`](../outputs/research/public_corpus/cases.json)：每个案例的期望链、实际 Spec 和指标；
- 每个案例目录：Figure Contract、三个候选、Draw.io、SVG 和 PDF。

## 下一步

下一轮将从 20 个案例中挑选复杂案例进行人工金标准标注，重点补充 RAG 的循环检索、AgentBench/VAKRA 的多跳关系、TPS-Bench 的并行分支、AutoGen/MetaGPT/CAMEL 的多智能体拓扑和网页代理的状态转移，然后再报告真正的节点召回率、边方向准确率和分支召回率。
