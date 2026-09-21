from __future__ import annotations

import argparse

import uvicorn

from .app.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="figure-agent-web")
    parser.add_argument("--data-dir", default="figure-agent-data")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(create_app(args.data_dir), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
