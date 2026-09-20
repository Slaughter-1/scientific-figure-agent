from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from figure_agent.backends.drawio_backend import render_drawio_spec
from figure_agent.spec import load_spec, require_valid_spec


if __name__ == "__main__":
    spec = load_spec(ROOT / "examples/m0/workflow.json")
    require_valid_spec(spec)
    output_dir = ROOT / "outputs/m0"
    render_drawio_spec(spec, output_dir, "workflow")
    print(f"drawio: {output_dir / 'workflow.drawio'}")
    print(f"svg: {output_dir / 'workflow.svg'}")
    print(f"pdf: {output_dir / 'workflow.pdf'}")
