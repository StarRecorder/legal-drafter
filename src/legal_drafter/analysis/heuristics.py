from __future__ import annotations

from collections import Counter

from legal_drafter.exceptions import ProviderError
from legal_drafter.models import AnalysisResult, DocumentKind, DraftRequest, ProviderAnalysis, ReviewFlag
from legal_drafter.providers import LLMProvider
from legal_drafter.topic_profiles import get_topic_profile

PRIVACY_HINTS = (
    "개인정보",
    "처리방침",
    "보유기간",
    "수집항목",
    "제3자 제공",
    "위탁",
)
TERMS_HINTS = (
    "약관",
    "서비스",
    "회원",
    "이용자",
    "주문",
    "결제",
    "환불",
    "해지",
)

PRIVACY_QUERY_SEEDS = (
    "개인정보 처리방침",
    "개인정보 보호법",
    "개인정보 수집 이용 보유기간",
    "개인정보 제3자 제공 위탁",
)
TERMS_QUERY_SEEDS = (
    "서비스 이용약관",
    "전자상거래 소비자 보호",
    "온라인 서비스 이용자 의무",
    "약관의 규제에 관한 법률",
)

PRIVACY_TOPICS = (
    "수집 항목",
    "이용 목적",
    "보유 기간",
    "처리 위탁",
    "제3자 제공",
    "정보주체 권리",
    "안전성 확보 조치",
)
TERMS_TOPICS = (
    "서비스 제공",
    "이용자 의무",
    "계약 해지",
    "면책",
    "분쟁 해결",
    "준거법",
)


def analyze_request_with_fallback(
    request: DraftRequest,
    provider: LLMProvider | None,
) -> tuple[AnalysisResult, tuple[ReviewFlag, ...]]:
    fallback = _fallback_analysis(request)
    flags: set[ReviewFlag] = set()
    provider_analysis: ProviderAnalysis | None = None

    if provider is not None:
        try:
            provider_analysis = provider.analyze_request(request, fallback.document_kind)
        except ProviderError:
            flags.add(ReviewFlag.PROVIDER_ERROR)

    if provider_analysis is None:
        analysis = fallback
    else:
        chosen_kind = request.document_kind
        if chosen_kind == DocumentKind.AUTO:
            chosen_kind = provider_analysis.document_kind or fallback.document_kind
        analysis = AnalysisResult(
            document_kind=chosen_kind,
            search_queries=_dedupe((request.prompt, *provider_analysis.search_queries, *fallback.search_queries)),
            regulatory_topics=_dedupe((*provider_analysis.regulatory_topics, *fallback.regulatory_topics)),
            summary=provider_analysis.summary or fallback.summary,
            ambiguities=_dedupe(provider_analysis.ambiguities),
        )

    if request.document_kind == DocumentKind.AUTO and _is_ambiguous(request.prompt):
        flags.add(ReviewFlag.AMBIGUOUS_REQUEST)

    return analysis, tuple(sorted(flags, key=lambda item: item.value))


def default_search_queries(document_kind: DocumentKind) -> tuple[str, ...]:
    if document_kind == DocumentKind.PRIVACY_POLICY:
        return PRIVACY_QUERY_SEEDS
    return TERMS_QUERY_SEEDS


def _fallback_analysis(request: DraftRequest) -> AnalysisResult:
    kind = request.document_kind if request.document_kind != DocumentKind.AUTO else _infer_document_kind(request)
    query_seeds = default_search_queries(kind)
    topic_queries = get_topic_profile(request.service_topic).retrieval_queries
    topics = PRIVACY_TOPICS if kind == DocumentKind.PRIVACY_POLICY else TERMS_TOPICS
    service_context = request.service_description or request.organization_name or "서비스"
    supplemental_query = f"{service_context} {request.prompt}"
    summary = (
        "개인정보 처리방침 초안을 위한 조문 분석 결과입니다."
        if kind == DocumentKind.PRIVACY_POLICY
        else "서비스 이용약관 초안을 위한 조문 분석 결과입니다."
    )
    return AnalysisResult(
        document_kind=kind,
        search_queries=_dedupe((request.prompt, supplemental_query, *query_seeds, *topic_queries, *request.constraints)),
        regulatory_topics=topics,
        summary=summary,
    )


def _infer_document_kind(request: DraftRequest) -> DocumentKind:
    corpus = " ".join(
        filter(
            None,
            [
                request.prompt,
                request.service_description,
                request.organization_name,
                " ".join(request.data_categories),
                " ".join(request.constraints),
            ],
        )
    )
    counts = Counter()
    for hint in PRIVACY_HINTS:
        if hint in corpus:
            counts[DocumentKind.PRIVACY_POLICY] += 1
    for hint in TERMS_HINTS:
        if hint in corpus:
            counts[DocumentKind.TERMS_OF_SERVICE] += 1
    if counts[DocumentKind.PRIVACY_POLICY] >= counts[DocumentKind.TERMS_OF_SERVICE] and counts[DocumentKind.PRIVACY_POLICY] > 0:
        return DocumentKind.PRIVACY_POLICY
    return DocumentKind.TERMS_OF_SERVICE


def _is_ambiguous(text: str) -> bool:
    privacy_hits = sum(1 for hint in PRIVACY_HINTS if hint in text)
    terms_hits = sum(1 for hint in TERMS_HINTS if hint in text)
    return privacy_hits == 0 and terms_hits == 0


def _dedupe(values) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)
