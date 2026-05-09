from __future__ import annotations

from legal_drafter.models import DraftResult


def render_markdown(result: DraftResult) -> str:
    lines: list[str] = [f"# {result.title}", ""]
    lines.append(f"- 문서 유형: `{result.document_kind.value}`")
    if result.service_topic is not None:
        lines.append(f"- 서비스 주제: `{result.service_topic.value}`")
    lines.append(f"- 신뢰도: `{result.confidence:.3f}`")
    lines.append(f"- 사람 검토 필요: `{'예' if result.review_required else '아니오'}`")
    if result.index_snapshot_at is not None:
        lines.append(f"- 인덱스 기준 시각: `{result.index_snapshot_at.isoformat()}`")
    lines.append(f"- 생성 시각: `{result.generated_at.isoformat()}`")
    if result.review_flags:
        lines.append(f"- 검토 플래그: `{', '.join(flag.value for flag in result.review_flags)}`")
    lines.extend(["", "## 요약", "", result.summary, "", "## 본문", ""])

    for provision in result.provisions:
        lines.append(f"### {provision.heading}")
        lines.append("")
        lines.append(provision.body)
        lines.append("")
        lines.append(f"- 지원 수준: `{provision.support_level.value}`")
        if provision.review_note:
            lines.append(f"- 검토 메모: {provision.review_note}")
        if provision.citations:
            lines.append("- 근거 조문:")
            for citation in provision.citations:
                lines.append(f"  - {citation.reference}: {citation.excerpt}")
        lines.append("")

    lines.extend(["## 전체 인용", ""])
    for citation in result.citations:
        lines.append(f"- {citation.reference}")
    return "\n".join(lines).strip()
