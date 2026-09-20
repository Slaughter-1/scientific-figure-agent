# Scientific Figure Agent M0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the minimum Scientific Figure Agent chain by producing one editable Draw.io workflow, one Figma canvas demo, and one Matplotlib PDF/SVG demo from a shared example specification.

**Architecture:** M0 uses a frozen hand-written Figure Spec as the source of truth. A local Python smoke runner validates the Spec and produces the Matplotlib artifact; the official Draw.io and Figma MCP integrations are exercised with the same semantic content. No text-to-Spec planner or automatic critic is implemented in M0.

**Tech Stack:** Python 3.10+, JSON Schema-compatible validation implemented with the Python standard library, Matplotlib, official draw.io MCP/plugin, official Figma MCP `use_figma`, SVG/PDF export.

**Spec:** `docs/superpowers/specs/2026-09-20-scientific-figure-agent-design.md`

## Global Constraints

- The Figure Spec is the stable interface; backends do not reinterpret the paper text.
- V1 supports `architecture`, `workflow`, `graph`, and `plot`; M0 exercises `workflow` and `plot` only.
- Every generated artifact must retain a source `.json` or `.py` representation.
- M0 must not claim automatic semantic correctness from a hand-written Spec.
- Figma output is an integration smoke test and must remain editable native canvas content.
- Draw.io/SVG remains the reproducible fallback when Figma access is unavailable.

## Review Focus

- Invalid node references: the validator must reject an edge whose source or target ID is absent.
- Duplicate node IDs: the validator must reject duplicates before any backend runs.
- Unsupported semantic types: the validator must reject unknown node and edge types with a useful path.
- Export readability: the Matplotlib smoke output must contain labels, a legend when needed, and vector PDF/SVG files.
- Backend parity: the Draw.io and Figma smoke prompts must use the same nodes, edges, labels, and direction as `examples/m0/workflow.json`.

### Task 1: Create the M0 project skeleton and environment report

**Files:**
- Create: `README.md`
- Create: `requirements.txt`
- Create: `src/figure_agent/__init__.py`
- Create: `src/figure_agent/environment.py`
- Create: `src/figure_agent/cli.py`
- Create: `scripts/check_environment.py`
- Create: `tests/test_environment.py`

**Interfaces:**
- `scripts/check_environment.py` prints JSON with Python version, Matplotlib availability, draw.io executable availability, and the expected Figma MCP prerequisite status.
- `src.figure_agent.cli.main(argv: list[str]) -> int` accepts `check-env` and returns a process status.

- [ ] **Step 1: Write the failing environment test**

```python
def test_environment_report_has_required_keys():
    from figure_agent.environment import build_environment_report

    report = build_environment_report()
    assert {"python", "matplotlib", "drawio", "figma_mcp"} <= report.keys()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_environment.py -q`

Expected: FAIL because `figure_agent.environment` does not exist.

- [ ] **Step 3: Implement the environment report and CLI**

Use `importlib.util.find_spec("matplotlib")` for the Python package check, `shutil.which("drawio")` and `shutil.which("drawio.exe")` for the desktop executable check, and report Figma MCP as `"manual_smoke_required"` rather than probing credentials or browser state.

The report shape must be:

```python
{
    "python": {"version": "3.12.0", "ok": True},
    "matplotlib": {"installed": True, "version": "3.10.0"},
    "drawio": {"executable": None, "plugin_fallback": True},
    "figma_mcp": {"status": "manual_smoke_required"},
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_environment.py -q`

Expected: PASS.

- [ ] **Step 5: Run the environment command and record its output**

Run: `python scripts/check_environment.py`

Expected: valid JSON written to stdout and no credential or session data printed.

- [ ] **Step 6: Commit**

```bash
git add README.md requirements.txt src/figure_agent scripts/check_environment.py tests/test_environment.py
git commit -m "chore: scaffold scientific figure agent m0"
```

### Task 2: Define and validate the shared Figure Spec

**Files:**
- Create: `schemas/figure_spec_schema.json`
- Create: `examples/m0/workflow.json`
- Create: `src/figure_agent/spec.py`
- Create: `tests/test_spec.py`

**Interfaces:**
- `load_spec(path: str | Path) -> dict`
- `validate_spec(spec: dict) -> list[str]`; an empty list means valid.
- `require_valid_spec(spec: dict) -> None`; raises `ValueError` with all validation errors.

- [ ] **Step 1: Write failing validator tests**

```python
def test_valid_workflow_spec_has_no_errors():
    from figure_agent.spec import load_spec, validate_spec

    spec = load_spec("examples/m0/workflow.json")
    assert validate_spec(spec) == []


def test_unknown_edge_target_is_rejected():
    from figure_agent.spec import validate_spec

    spec = {"figure_type": "workflow", "nodes": [{"id": "a", "type": "process", "label": "A"}], "edges": [{"source": "a", "target": "missing", "type": "data_flow"}]}
    errors = validate_spec(spec)
    assert any("missing" in error for error in errors)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_spec.py -q`

Expected: FAIL because the Spec loader and validator are not implemented.

- [ ] **Step 3: Implement the schema and validator**

The validator must check required top-level fields, unique node IDs, node types, edge types, existing edge endpoints, supported layout directions, and hex colors. Keep it dependency-free in M0; the JSON Schema file documents the same contract for later replacement by a standard JSON Schema library.

- [ ] **Step 4: Add the fixed M0 workflow example**

Use these nodes and edges so every backend has the same smoke target:

```text
User Query → Planner → Tool Selection → Environment → Observation
                         Tool Selection → Search Tool
                         Tool Selection → Code Tool
Observation → Reflection → Answer
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_spec.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add schemas examples/m0 src/figure_agent/spec.py tests/test_spec.py
git commit -m "feat: add figure spec contract and validator"
```

### Task 3: Build the Matplotlib smoke backend

**Files:**
- Create: `src/figure_agent/backends/plot_backend.py`
- Create: `examples/m0/results.json`
- Create: `scripts/render_m0_plot.py`
- Create: `tests/test_plot_backend.py`
- Create: `outputs/m0/.gitkeep`

**Interfaces:**
- `render_bar_chart(data: dict, output_dir: Path, stem: str) -> dict[str, Path]`
- The return value contains `pdf`, `svg`, and `png` paths.

- [ ] **Step 1: Write the failing plot test**

```python
def test_render_bar_chart_writes_vector_and_preview_files(tmp_path):
    from figure_agent.backends.plot_backend import render_bar_chart

    outputs = render_bar_chart(
        {"methods": ["Baseline", "Ours"], "accuracy": [0.71, 0.83]},
        tmp_path,
        "benchmark",
    )
    assert outputs["pdf"].exists()
    assert outputs["svg"].exists()
    assert outputs["png"].exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_plot_backend.py -q`

Expected: FAIL because the backend is not implemented.

- [ ] **Step 3: Implement the backend**

Use a non-interactive Matplotlib backend, set figure dimensions in inches, use a color-blind-friendly two-color palette, label the y-axis as `Accuracy`, and save PDF/SVG before PNG. Do not embed random data; read the fixed `examples/m0/results.json` file in the script.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_plot_backend.py -q`

Expected: PASS.

- [ ] **Step 5: Render and inspect the smoke artifact**

Run: `python scripts/render_m0_plot.py`

Expected: `outputs/m0/benchmark.pdf`, `outputs/m0/benchmark.svg`, and `outputs/m0/benchmark.png` exist. Open the PNG and confirm labels are not clipped.

- [ ] **Step 6: Commit**

```bash
git add src/figure_agent/backends examples/m0/results.json scripts/render_m0_plot.py tests/test_plot_backend.py outputs/m0/.gitkeep
git commit -m "feat: add matplotlib m0 smoke backend"
```

### Task 4: Verify the official Draw.io integration with the shared Spec

**Files:**
- Create: `examples/m0/drawio_prompt.md`
- Create: `src/figure_agent/backends/drawio_backend.py`
- Create: `scripts/check_drawio_output.py`
- Create: `tests/test_drawio_output.py`
- Generated during execution: `outputs/m0/workflow.drawio`, `outputs/m0/workflow.svg`, `outputs/m0/workflow.pdf`

**Interfaces:**
- `check_drawio_output(path: str | Path) -> list[str]`; checks that the artifact exists, contains all required labels, and includes the expected editable Draw.io structure.

- [ ] **Step 1: Write the failing output test**

```python
def test_drawio_output_contains_shared_workflow_labels(tmp_path):
    from figure_agent.backends.drawio_backend import check_drawio_output

    errors = check_drawio_output(tmp_path / "workflow.drawio")
    assert errors == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_drawio_output.py -q`

Expected: FAIL because the smoke artifact and checker do not exist.

- [ ] **Step 3: Write the Draw.io smoke prompt**

The prompt must embed the exact node labels and edge direction from `examples/m0/workflow.json`, request an editable `.drawio` file, and request SVG/PDF export with embedded diagram data. It must not ask the model to invent additional modules or styling.

- [ ] **Step 4: Generate the artifact through the official draw.io MCP/plugin**

Use the official `jgraph/drawio-mcp` route available to Codex. Save the native `.drawio` file and exports under `outputs/m0/`.

- [ ] **Step 5: Implement and run the checker**

Parse the `.drawio` XML with Python’s standard library, verify every required label appears, verify at least one edge element exists, and report missing labels as explicit errors.

Run: `python -m pytest tests/test_drawio_output.py -q`

Expected: PASS after the generated artifact is present.

- [ ] **Step 6: Commit**

```bash
git add examples/m0/drawio_prompt.md scripts/check_drawio_output.py tests/test_drawio_output.py
git commit -m "test: verify drawio m0 integration"
```

### Task 5: Verify the Figma native-canvas integration

**Files:**
- Create: `examples/m0/figma_prompt.md`
- Create: `docs/m0-validation-report.md`
- Create: `tests/test_m0_report.py`

**Interfaces:**
- The report records `status`, `file_or_frame`, `node_count`, `required_labels`, `editable`, `export_formats`, and `limitations`.

- [ ] **Step 1: Write the validation-report test**

```python
def test_m0_report_requires_editable_figma_status():
    import json
    from pathlib import Path

    report = json.loads(Path("docs/m0-validation-report.md").read_text(encoding="utf-8").split("```json", 1)[1].split("```", 1)[0])
    assert report["figma"]["editable"] is True
    assert report["figma"]["required_labels"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_m0_report.py -q`

Expected: FAIL because the report does not exist.

- [ ] **Step 3: Write the Figma smoke prompt**

The prompt must ask `use_figma` to create native Frames, Text nodes, Rectangles, Lines/Arrows, and groups matching the shared workflow labels and left-to-right layout. It must explicitly avoid rasterizing the result.

- [ ] **Step 4: Execute the Figma smoke test**

Run the prompt through the connected official Figma MCP, inspect the created Figma frame, and export one SVG or PDF. Record the file/frame identifier only; do not record credentials or private session data.

- [ ] **Step 5: Write the validation report and run the test**

Record the exact labels found, approximate node count, editability, export formats, and any manual limitations. Run: `python -m pytest tests/test_m0_report.py -q`

Expected: PASS when the frame is native and editable.

- [ ] **Step 6: Commit**

```bash
git add examples/m0/figma_prompt.md docs/m0-validation-report.md tests/test_m0_report.py
git commit -m "test: record figma native canvas smoke result"
```

### Task 6: Produce the M0 report and verify the whole chain

**Files:**
- Modify: `README.md`
- Create: `docs/m0-report.md`
- Create: `tests/test_m0_acceptance.py`

**Interfaces:**
- The acceptance test verifies the Spec, Matplotlib outputs, Draw.io outputs, and Figma report are all present and reference the same required labels.

- [ ] **Step 1: Write the failing acceptance test**

```python
def test_m0_acceptance_artifacts_exist():
    from pathlib import Path

    required = [
        Path("examples/m0/workflow.json"),
        Path("outputs/m0/benchmark.pdf"),
        Path("outputs/m0/benchmark.svg"),
        Path("outputs/m0/workflow.drawio"),
        Path("docs/m0-validation-report.md"),
    ]
    assert all(path.exists() for path in required)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_m0_acceptance.py -q`

Expected: FAIL until all smoke artifacts exist.

- [ ] **Step 3: Write the M0 report**

Document the environment report, commands run, artifact paths, labels checked, Figma integration result, Draw.io integration result, export formats, and limitations. State explicitly whether each success criterion passed.

- [ ] **Step 4: Update the README**

Add a quick-start section that points to the M0 example, the environment check, the plot renderer, and the validation report. Keep the README focused on the tested scope; do not document unimplemented automatic planning.

- [ ] **Step 5: Run the complete verification suite**

Run: `python -m pytest -q`

Expected: PASS for all tests, with the only manual check being visual inspection of the PNG and Figma frame.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/m0-report.md tests/test_m0_acceptance.py
git commit -m "docs: complete scientific figure agent m0 validation"
```

## Self-review checklist

- The plan covers every M0 success criterion in the design spec.
- Figure Spec validation is implemented before any backend execution.
- Matplotlib output is deterministic and vector-first.
- Draw.io and Figma are tested against the same fixed semantic example.
- No task claims automatic text-to-Spec planning or automatic semantic correction.
- Placeholder scan completed: no placeholder markers or unspecified implementation step remains.
