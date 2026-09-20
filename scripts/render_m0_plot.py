from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from figure_agent.backends.plot_backend import render_bar_chart


if __name__ == "__main__":
    data = json.loads((ROOT / "examples/m0/results.json").read_text(encoding="utf-8"))
    outputs = render_bar_chart(data, ROOT / "outputs/m0", "benchmark")
    for kind, path in outputs.items():
        print(f"{kind}: {path}")
