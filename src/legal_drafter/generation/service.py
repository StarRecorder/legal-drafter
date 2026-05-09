from __future__ import annotations

from datetime import UTC, datetime, timedelta

from legal_drafter.analysis import analyze_request_with_fallback
from legal_drafter.exceptions import ProviderError
from legal_drafter.index import SQLiteIndex
from legal_drafter.models import (
    Citation,
    DocumentKind,
    DraftRequest,
    DraftResult,
    GenerationOptions,
    Provision,
    RetrievalQuery,
    ReviewFlag,
    SupportLevel,
)
from legal_drafter.providers import LLMProvider
from legal_drafter.text_style import normalize_legal_text
from legal_drafter.retrieval import retrieve_authority_hits
from legal_drafter.topic_profiles import get_section_profile

from .templates import TemplateSection, get_template

SUPPORT_SCORES = {
    SupportLevel.STRONG: 1.0,
    SupportLevel.PARTIAL: 0.7,
    SupportLevel.WEAK: 0.4,
}


def generate_draft_from_request(
    request: DraftRequest,
    provider: LLMProvider,
    options: GenerationOptions,
) -> DraftResult:
    index = SQLiteIndex(options.index_path)
    index.require_ready()
    stats = index.get_stats()
    flags: set[ReviewFlag] = set()

    analysis, analysis_flags = analyze_request_with_fallback(request, provider)
    flags.update(analysis_flags)

    if stats.snapshot_at and _is_stale(stats.snapshot_at, options.freshness_days):
        flags.add(ReviewFlag.STALE_INDEX)

    provisions: list[Provision] = []
    all_citations: list[Citation] = []
    found_any_hits = False
    template = get_template(analysis.document_kind)
    for section in template:
        section_hits = _retrieve_section_hits(
            request=request,
            options=options,
            document_kind=analysis.document_kind,
            analysis_queries=analysis.search_queries,
            section=section,
        )
        if section_hits:
            found_any_hits = True
        selected_hits, matched_hits = _select_section_hits(section_hits, section, options.citations_per_provision)
        citations = _dedupe_citations(tuple(hit.citation for hit in selected_hits))
        body = _build_provision_body(
            provider=provider,
            request=request,
            document_kind=analysis.document_kind,
            section=section,
            citations=citations,
            regulatory_topics=analysis.regulatory_topics,
            flags=flags,
        )
        support_level = _determine_support_level(matched_hits, citations)
        review_note = _build_review_note(support_level, citations, flags)
        if support_level == SupportLevel.WEAK:
            flags.add(ReviewFlag.LOW_SUPPORT)
        provisions.append(
            Provision(
                heading=section.heading,
                body=body,
                citations=citations,
                support_level=support_level,
                review_note=review_note,
            )
        )
        all_citations.extend(citations)

    if not found_any_hits:
        flags.add(ReviewFlag.NO_AUTHORITIES_FOUND)

    confidence = _calculate_confidence(tuple(provisions), stats.snapshot_at, options.freshness_days)
    review_required = bool(flags) or any(provision.support_level == SupportLevel.WEAK for provision in provisions)
    return DraftResult(
        title=_build_title(analysis.document_kind, request.organization_name),
        document_kind=analysis.document_kind,
        service_topic=request.service_topic,
        summary=_build_summary(
            analysis.document_kind,
            analysis.summary,
            len(provisions),
            len(_dedupe_citations(tuple(all_citations))),
        ),
        provisions=tuple(provisions),
        citations=_dedupe_citations(tuple(all_citations)),
        confidence=confidence,
        review_required=review_required,
        review_flags=tuple(sorted(flags, key=lambda item: item.value)),
        generated_at=datetime.now(UTC),
        index_snapshot_at=stats.snapshot_at,
    )


def _select_section_hits(hits, section: TemplateSection, citation_limit: int):
    matches = [hit for hit in hits if _matches_section(hit, section)]
    if matches:
        return matches[:citation_limit], matches
    return hits[:citation_limit], []


def _retrieve_section_hits(
    request: DraftRequest,
    options: GenerationOptions,
    document_kind: DocumentKind,
    analysis_queries: tuple[str, ...],
    section: TemplateSection,
):
    section_profile = get_section_profile(request.service_topic, document_kind, section.heading)
    return retrieve_authority_hits(
        RetrievalQuery(
            text=request.prompt,
            index_path=options.index_path,
            document_kind=document_kind,
            service_topic=request.service_topic,
            section_heading=section.heading,
            authority_keywords=section_profile.authority_keywords,
            search_queries=(
                *analysis_queries,
                *section_profile.retrieval_queries,
                *section.keywords,
            ),
            top_k=max(options.citations_per_provision * 3, options.top_k // 3, options.citations_per_provision),
            effective_only=True,
        )
    )


def _matches_section(hit, section: TemplateSection) -> bool:
    haystack = " ".join(filter(None, [hit.authority_name, hit.article_title or "", hit.excerpt]))
    return any(keyword in haystack for keyword in section.keywords)


def _build_provision_body(
    provider: LLMProvider,
    request: DraftRequest,
    document_kind: DocumentKind,
    section: TemplateSection,
    citations: tuple[Citation, ...],
    regulatory_topics: tuple[str, ...],
    flags: set[ReviewFlag],
) -> str:
    try:
        drafted = provider.draft_provision(
            request=request,
            document_kind=document_kind,
            heading=section.heading,
            instruction=section.instruction,
            citations=citations,
            regulatory_topics=regulatory_topics,
        ).strip()
        return normalize_legal_text(drafted, heading=section.heading)
    except ProviderError:
        flags.add(ReviewFlag.PROVIDER_ERROR)
        return normalize_legal_text(
            _fallback_provision_text(request, document_kind, section, citations),
            heading=section.heading,
        )


def _fallback_provision_text(
    request: DraftRequest,
    document_kind: DocumentKind,
    section: TemplateSection,
    citations: tuple[Citation, ...],
) -> str:
    organization = request.organization_name or "회사"
    service = request.service_description or "서비스"
    citation_note = (
        f" 관련 사항은 {', '.join(citation.reference for citation in citations[:2])} 등 관계 법령의 범위에서 정합니다."
        if citations
        else " 관련 사항은 관계 법령과 실제 운영 구조를 추가로 확인하여 정합니다."
    )
    if document_kind == DocumentKind.PRIVACY_POLICY:
        return (
            f"{organization}는 {service} 운영 과정에서 {section.instruction} "
            f"정보주체의 권리를 침해하지 않도록 관계 법령에 따라 최소한의 기준을 적용합니다."
            f"{citation_note}"
        )
    return (
        f"{organization}는 {service} 이용과 관련하여 {section.instruction} "
        f"이용자 보호와 법령 준수를 위하여 필요한 기준을 이 약관에 따라 운영합니다."
        f"{citation_note}"
    )


def _determine_support_level(matched_hits, citations: tuple[Citation, ...]) -> SupportLevel:
    if len(matched_hits) >= 2 and len(citations) >= 2:
        return SupportLevel.STRONG
    if matched_hits and citations:
        return SupportLevel.PARTIAL
    return SupportLevel.WEAK


def _build_review_note(
    support_level: SupportLevel,
    citations: tuple[Citation, ...],
    flags: set[ReviewFlag],
) -> str | None:
    notes: list[str] = []
    if not citations:
        notes.append("직접 연결된 조문 근거를 찾지 못해 추가 검토가 필요합니다.")
    elif support_level == SupportLevel.WEAK:
        notes.append("조문 연결성이 약해 전문 검토가 필요합니다.")
    if ReviewFlag.PROVIDER_ERROR in flags:
        notes.append("LLM 제공자 오류로 일부 문장이 템플릿 기반으로 대체되었습니다.")
    if ReviewFlag.STALE_INDEX in flags:
        notes.append("법령 인덱스가 오래되어 최신성 검토가 필요합니다.")
    return " ".join(notes) if notes else None


def _calculate_confidence(
    provisions: tuple[Provision, ...],
    snapshot_at: datetime | None,
    freshness_days: int,
) -> float:
    if not provisions:
        return 0.0
    average = sum(SUPPORT_SCORES[provision.support_level] for provision in provisions) / len(provisions)
    if snapshot_at and _is_stale(snapshot_at, freshness_days):
        average *= 0.85
    return round(average, 3)


def _build_title(document_kind: DocumentKind, organization_name: str | None) -> str:
    owner = organization_name or "서비스"
    if document_kind == DocumentKind.PRIVACY_POLICY:
        return f"{owner} 개인정보 처리방침 초안"
    return f"{owner} 서비스 이용약관 초안"


def _build_summary(document_kind: DocumentKind, analysis_summary: str, provision_count: int, citation_count: int) -> str:
    doc_label = "개인정보 처리방침" if document_kind == DocumentKind.PRIVACY_POLICY else "서비스 이용약관"
    return f"{analysis_summary} {provision_count}개 조항과 {citation_count}개 근거 인용을 포함한 {doc_label} 초안입니다."


def _dedupe_citations(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
    result: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (citation.authority_id, citation.article_number)
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return tuple(result)


def _is_stale(snapshot_at: datetime, freshness_days: int) -> bool:
    return snapshot_at < datetime.now(UTC) - timedelta(days=freshness_days)
