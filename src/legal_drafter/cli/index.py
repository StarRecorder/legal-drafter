from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legal_drafter import ServiceTopic, SourceConfig, refresh_index
from legal_drafter.exceptions import LegalDrafterError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "refresh":
        parser.error("a subcommand is required")

    try:
        stats = refresh_index(
            SourceConfig(
                index_path=Path(args.index_path),
                oc=args.oc,
                service_topic=ServiceTopic(args.service_topic) if args.service_topic else None,
            ),
            rebuild=args.rebuild,
        )
    except LegalDrafterError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "authority_count": stats.authority_count,
        "article_count": stats.article_count,
        "snapshot_at": stats.snapshot_at.isoformat() if stats.snapshot_at else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legal-drafter-index", description="법령 인덱스 관리 CLI")
    subparsers = parser.add_subparsers(dest="command")

    refresh_parser = subparsers.add_parser("refresh", help="law.go.kr에서 법령 인덱스를 다시 생성합니다.")
    refresh_parser.add_argument("--index-path", default="law_index.sqlite3", help="SQLite 인덱스 파일 경로")
    refresh_parser.add_argument(
        "--service-topic",
        choices=[topic.value for topic in ServiceTopic],
        default=ServiceTopic.GENERAL.value,
        help="법령 수집과 검색에 사용할 주제 선택지",
    )
    refresh_parser.add_argument("--oc", help="law.go.kr OC 키. 생략 시 환경 변수나 .env에서 읽습니다.")
    refresh_parser.add_argument("--rebuild", action="store_true", help="기존 인덱스를 삭제하고 다시 생성합니다.")
    return parser


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
