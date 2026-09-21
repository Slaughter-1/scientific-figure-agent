from __future__ import annotations

import argparse
import json
from pathlib import Path

from figure_agent.evaluation import build_evaluation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Scientific Figure Agent evaluation report")
    parser.add_argument("cases", type=Path, help="JSON file containing a list of case results")
    parser.add_argument("--output", type=Path, default=Path("evaluation-report.json"))
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    build_evaluation_report(cases, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
