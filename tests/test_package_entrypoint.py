import os
import subprocess
import sys


def test_module_entrypoint_is_runnable():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-m", "figure_agent", "--help"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "figure-agent" in result.stdout
