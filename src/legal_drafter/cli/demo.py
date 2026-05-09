from __future__ import annotations

import argparse
from pathlib import Path

from legal_drafter.demo_server import serve_demo
from legal_drafter.runtime import get_default_artifact_root, get_default_index_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    serve_demo(
        index_path=Path(args.index_path),
        model=args.model,
        host=args.host,
        port=args.port,
        artifact_root=Path(args.artifact_root) if args.artifact_root else None,
        strict_rendering=args.strict_rendering,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-drafter-server", description="법률 문서 생성 백엔드 API 서버를 실행합니다.")
    parser.add_argument("--index-path", default=str(get_default_index_path()), help="SQLite 인덱스 파일 경로")
    parser.add_argument("--model", default="llama3.2", help="기본 Ollama 모델명")
    parser.add_argument("--host", default="127.0.0.1", help="바인딩 호스트")
    parser.add_argument("--port", type=int, default=8000, help="바인딩 포트")
    parser.add_argument("--artifact-root", default=str(get_default_artifact_root()), help="산출물 저장 디렉터리")
    parser.add_argument("--strict-rendering", action="store_true", help="브라우저 렌더링 실패 시 에러로 처리")
    return parser


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
