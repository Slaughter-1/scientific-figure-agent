from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from figure_agent.environment import build_environment_report


if __name__ == "__main__":
    print(json.dumps(build_environment_report(), indent=2))
