from __future__ import annotations

import argparse
from pathlib import Path

from legal_drafter.demo_server import serve_demo


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    serve_demo(
        index_path=Path(args.index_path),
        model=args.model,
        host=args.host,
        port=args.port,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-drafter-demo", description="로컬 데모 페이지 서버를 실행합니다.")
    parser.add_argument("--index-path", default="law_index.sqlite3", help="SQLite 인덱스 파일 경로")
    parser.add_argument("--model", default="llama3.2", help="기본 Ollama 모델명")
    parser.add_argument("--host", default="127.0.0.1", help="바인딩 호스트")
    parser.add_argument("--port", type=int, default=8000, help="바인딩 포트")
    return parser


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
