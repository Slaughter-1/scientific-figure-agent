from __future__ import annotations

import argparse
import json
from pathlib import Path

from .environment import build_environment_report
from .artifacts import build_manifest
from .router import render_backends
from .spec import load_spec, require_valid_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="figure-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-env")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--spec", required=True)
    render_parser.add_argument("--backend", required=True)
    render_parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "check-env":
        print(json.dumps(build_environment_report(), indent=2))
        return 0
    if args.command == "render":
        spec = load_spec(args.spec)
        require_valid_spec(spec)
        backends = ["drawio", "figma", "matplotlib"] if args.backend == "all" else [args.backend]
        output_dir = Path(args.output_dir)
        results = render_backends(spec, backends, output_dir)
        manifest = build_manifest(spec, results)
        (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 2 if any(result.get("status") == "error" for result in results.values()) else 0
    return 2
