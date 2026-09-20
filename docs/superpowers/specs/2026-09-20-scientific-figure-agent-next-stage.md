# Scientific Figure Agent 下一阶段设计：Figma 原生后端与跨后端编排

## 目标

下一阶段把现有 Figure Spec 编译成可编辑的 Figma 原生节点，并建立 Draw.io、Figma、Matplotlib 之间的语义一致性检查。用户可以用同一份 Spec 生成草图、精修图和数据图，系统会输出统一的产物清单与检查结果。

## 成功标准

1. 给定合法的 architecture/workflow/graph Figure Spec，系统能编译出 Figma 场景描述，包含 Frame、Text、Rectangle、Line/Arrow 和 Group 的节点树。
2. 有 Figma MCP 连接时，场景描述能写入真实 Figma Canvas，并返回文件或 Frame 标识；没有连接时，仍能生成可审查的本地场景 JSON，不把模拟结果标记为真实 Figma。
3. 同一份 Spec 在 Draw.io 和 Figma 产物中具有相同的节点 ID、标签、边端点、分组关系和布局方向。
4. 每次渲染都生成 `manifest.json`，记录输入摘要、Spec 哈希、后端状态、产物路径、检查结果和限制。
5. `figure-agent render` 能选择 `drawio`、`figma`、`matplotlib` 或 `all`，并在后端不可用时返回可解释状态和本地后备产物。

## 范围

### 包含

- Figma 原生场景编译器和可选 MCP 写入适配器。
- Frame、Group、Rectangle、Text、Line/Arrow 五类 Figma 节点。
- academic_clean style token 到 Figma 属性的映射。
- 跨后端语义 parity checker。
- 统一 Artifact Manifest 和 CLI render 命令。
- 离线 mock driver，用于无账号、无 MCP 环境的确定性测试。

### 不包含

- Figma 账号登录、权限申请或自动发布社区文件。
- 复杂自动布局优化和像素级 Draw.io/Figma 对齐。
- 对语义节点进行自动增删；这类问题继续由 Critic 报告。
- 完整 Web 画布编辑器。

## 架构

```text
Figure Spec
    ↓
Backend Router
    ├── Draw.io renderer → .drawio/.svg/.pdf
    ├── Figma scene compiler → scene.json → optional Figma MCP writer
    └── Matplotlib renderer → .pdf/.svg/.png
    ↓
Artifact Inspector + Parity Checker
    ↓
manifest.json
```

Figma 后端分为两个边界：纯 Python 的 scene compiler 负责把 Spec 转换为可测试的节点树；driver 负责把节点树发送到 Figma MCP 或写入本地 mock 文件。这样 MCP 不可用不会阻塞核心编译和测试。

## 核心接口

```python
class FigmaDriver(Protocol):
    def write_scene(self, scene: dict[str, Any]) -> dict[str, Any]: ...


def compile_figma_scene(spec: dict[str, Any]) -> dict[str, Any]: ...
def render_figma_spec(
    spec: dict[str, Any], output_dir: str | Path, driver: FigmaDriver | None = None
) -> dict[str, Path | str | bool]: ...
def compare_semantics(spec: dict[str, Any], artifact: dict[str, Any]) -> list[dict[str, str]]: ...
def build_manifest(spec: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]: ...
```

Scene 节点使用稳定的 `source_id` 回指 Figure Spec：

```json
{
  "kind": "FRAME",
  "source_id": "planner",
  "name": "Planner",
  "x": 240,
  "y": 80,
  "width": 160,
  "height": 64,
  "fills": [{"color": "#E8EEF7"}],
  "children": []
}
```

真实 MCP 写入成功时，manifest 的 `figma.status` 为 `connected`，并记录返回的 `file_or_frame`；mock 或未配置时分别记录 `mock` 或 `unavailable`，不得伪造真实文件标识。

## 验收策略

- 单元测试：每种节点类型、方向、分组、颜色 token 和空图输入都有确定性断言。
- Figma mock 测试：scene JSON 可序列化，节点数量和 `source_id` 唯一。
- 真实 MCP 冒烟：仅在环境报告显示连接可用时执行；否则测试明确记录 `unavailable`。
- parity 测试：从 Draw.io XML 和 Figma scene 提取节点/边语义，集合必须与 Spec 相等。
- manifest 测试：路径、哈希、后端状态和限制字段完整，JSON 可复现。

## 风险与处理

- Figma MCP API 或权限变化：driver 隔离并保留 mock，不让核心测试依赖账号。
- Figma 与 Draw.io 坐标系不同：只比较语义、方向和风格 token，不要求像素一致。
- 文本过长导致节点溢出：scene compiler 设置最小宽度，Critic 只报告需要人工确认的截断风险。
- 后端部分失败：manifest 记录每个后端独立状态，`all` 模式继续生成可用的本地产物。
