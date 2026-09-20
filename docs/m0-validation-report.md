# M0 验证报告

当前报告记录本地可复现链路，以及外部 Figma MCP 的连接状态。Figma 项在具备连接后应重新运行并更新。

```json
{
  "drawio": {
    "status": "verified_local_fallback",
    "file_or_frame": "outputs/m0/workflow.drawio",
    "editable": true,
    "required_labels": ["User Query", "Planner", "Tool Selection", "Environment", "Observation", "Search Tool", "Code Tool", "Reflection", "Answer"],
    "export_formats": ["drawio", "svg", "pdf"]
  },
  "figma": {
    "status": "unverified_mcp_unavailable",
    "file_or_frame": null,
    "node_count": null,
    "editable": false,
    "required_labels": ["User Query", "Planner", "Tool Selection", "Environment", "Observation", "Search Tool", "Code Tool", "Reflection", "Answer"],
    "export_formats": [],
    "limitations": ["No callable official Figma MCP is exposed in the current Codex session.", "Native canvas editability and export remain to be verified in a connected Figma file."]
  },
  "matplotlib": {
    "status": "verified",
    "artifacts": ["outputs/m0/benchmark.pdf", "outputs/m0/benchmark.svg", "outputs/m0/benchmark.png"]
  }
}
```
