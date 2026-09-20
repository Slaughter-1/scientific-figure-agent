# Scientific Figure Agent 下一阶段设计：数据输入与 Figma 连接层

## 目标

把当前“只接受 Figure Spec”的原型扩展为可用的输入适配层，并为真实 Figma MCP 保留稳定的连接边界：CSV/JSON 可以直接生成 plot Figure Spec，Figma scene 可以通过注入的 transport 写入真实 Canvas，同时继续支持离线运行和明确的不可用状态。

## 当前问题

当前项目已经能渲染 plot Figure Spec，但用户必须手写 Spec；`render_figma_spec` 能编译本地 scene，却没有实际的外部写入边界。下一阶段应先解决输入和连接协议，避免把 CSV 解析、图表语义、Figma 权限和 MCP 细节混在渲染器里。

## 成功标准

1. `CSV/JSON → normalized table → plot Figure Spec → PDF/SVG/PNG` 成为可运行链路。
2. 输入列名、长度、数值类型和空值错误都能给出具体字段和行号。
3. CLI 支持 `plot --input <path> --kind <kind> --x <column> --y <column>`，并生成 plot Spec、图表和 manifest。
4. Figma backend 接受可注入的 `FigmaTransport`，transport 成功时返回外部文件/Frame 标识；未注入时继续返回 `unavailable`，不伪造远程结果。
5. 同一 plot Spec 和结构 Spec 的 provenance、Spec hash、backend status 都进入 manifest。

## 范围

### 包含

- CSV 和 JSON records 两种数据输入；
- bar、line、scatter、heatmap 的输入适配；
- 明确的列映射、数值转换和错误报告；
- Figma transport 协议、注入式 adapter 和离线 transport；
- CLI plot 命令和端到端验收；
- 文档化的真实 MCP 接入点。

### 不包含

- 自动猜测实验指标含义或单位；
- 直接读取 Excel、数据库或远程 URL；
- 在没有 Figma MCP API 证据时猜测工具调用格式；
- 自动发布 Figma 社区文件；
- 视觉模型生成的投稿级美化。

## 架构

```text
CSV / JSON records
        ↓
Input Adapter + Column Mapping
        ↓
Normalized Table
        ↓
Plot Spec Builder ───────→ Matplotlib backend
        ↓                         ↓
Figure Spec + provenance      PDF/SVG/PNG

Figure Spec → Figma Scene Compiler → FigmaTransport (optional)
                                          ↓
                                  file/frame identifier
```

输入适配器只负责数据形状和类型，不决定学术解释；Plot Spec Builder 负责把明确的列映射转换为已有 `data.kind/x/y/matrix` 结构。FigmaTransport 是依赖注入边界，实际 MCP connector 由宿主环境提供，仓库只定义输入输出契约。

## 核心接口

```python
def load_table(path: str | Path, *, format: str | None = None) -> dict[str, Any]: ...
def build_plot_spec(
    table: dict[str, Any], *, kind: str, x_column: str | None = None,
    y_column: str | None = None, matrix_columns: list[str] | None = None,
    title: str | None = None,
) -> dict[str, Any]: ...

class FigmaTransport(Protocol):
    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]: ...

def render_figma_spec(
    spec: dict[str, Any], output_dir: str | Path,
    transport: FigmaTransport | None = None,
) -> dict[str, Any]: ...
```

`load_table` 的输出保持 JSON 可序列化：

```json
{
  "columns": ["method", "accuracy"],
  "rows": [
    {"method": "Baseline", "accuracy": 0.71},
    {"method": "Ours", "accuracy": 0.83}
  ],
  "provenance": {"source": "results.csv", "format": "csv"}
}
```

`build_plot_spec` 必须将来源写入 `spec.provenance`，并把表格中的原始列名保存在 `data.source_columns`。缺失列、空数据、非矩形 heatmap 和无法转换为数值的单元格都返回结构化错误或抛出包含列名/行号的 `ValueError`。

## Figma 连接语义

- `transport is None`：写入本地 scene JSON，返回 `status=unavailable`；
- transport 返回 `status=mock`：用于离线回归；
- transport 返回 `status=connected` 且包含 `file_or_frame`：记录真实外部标识；
- transport 抛出异常：返回 `status=error` 和可读错误，不吞掉本地 scene 产物。

真实 MCP 工具的调用参数、权限和文件创建策略由宿主连接层决定，不写入核心渲染器，也不在没有实测工具 schema 时编造调用代码。

## 验证策略

- CSV：表头、空行、数值列和 UTF-8 中文列名；
- JSON：records 数组、空数组、缺列和混合类型；
- Plot Spec：四种 kind 的字段完整性、数据长度和 provenance；
- CLI：成功生成 Spec、图表和 manifest，错误输入返回非零状态；
- Figma：mock transport 成功、无 transport、transport 失败三种状态；
- 回归：现有 35 个测试全部通过。

## 风险与处理

- 指标列的单位和统计含义无法从 CSV 推断：要求用户通过参数提供标签，不自动臆造。
- 远程 Figma 连接变化：transport 隔离，scene JSON 永远作为本地证据保留。
- 大文件输入：第一版限制在可读入内存的研究结果表，超过限制时给出明确错误。
