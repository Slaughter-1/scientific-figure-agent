from __future__ import annotations

import argparse
import json

from .environment import build_environment_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="figure-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-env")
    args = parser.parse_args(argv)
    if args.command == "check-env":
        print(json.dumps(build_environment_report(), indent=2))
        return 0
    return 2
