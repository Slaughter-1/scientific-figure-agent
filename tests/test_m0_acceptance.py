def test_m0_acceptance_artifacts_exist():
    from pathlib import Path

    required = [
        Path("examples/m0/workflow.json"),
        Path("outputs/m0/benchmark.pdf"),
        Path("outputs/m0/benchmark.svg"),
        Path("outputs/m0/workflow.drawio"),
        Path("docs/m0-validation-report.md"),
        Path("docs/m0-report.md"),
    ]
    assert all(path.exists() for path in required)
