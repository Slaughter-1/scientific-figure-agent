from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .environment import build_environment_report
from .artifacts import build_manifest
from .data import load_table
from .plot_planner import build_plot_spec
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
    plot_parser = subparsers.add_parser("plot")
    plot_parser.add_argument("--input", required=True)
    plot_parser.add_argument("--kind", required=True, choices=["bar", "line", "scatter", "heatmap"])
    plot_parser.add_argument("--x")
    plot_parser.add_argument("--y")
    plot_parser.add_argument("--matrix-columns")
    plot_parser.add_argument("--title")
    plot_parser.add_argument("--output-dir", required=True)
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
    if args.command == "plot":
        try:
            table = load_table(args.input)
            matrix_columns = [item.strip() for item in args.matrix_columns.split(",") if item.strip()] if args.matrix_columns else None
            spec = build_plot_spec(table, kind=args.kind, x_column=args.x, y_column=args.y, matrix_columns=matrix_columns, title=args.title)
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            spec_path = output_dir / "plot-spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            from .backends.plot_backend import render_plot_spec

            rendered = render_plot_spec(spec, output_dir, "figure")
            artifacts = {"matplotlib": {"status": "ok", "spec": str(spec_path), **{key: str(value) for key, value in rendered.items()}}}
            manifest = build_manifest(spec, artifacts)
            (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"figure-agent plot error: {exc}", file=sys.stderr)
            return 2
    return 2
