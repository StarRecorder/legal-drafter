from __future__ import annotations

from dataclasses import dataclass

from legal_drafter.models import DocumentKind, ServiceTopic


@dataclass(frozen=True, slots=True)
class TopicProfile:
    source_queries: tuple[str, ...]
    authority_keywords: tuple[str, ...]
    retrieval_queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SectionProfile:
    retrieval_queries: tuple[str, ...]
    authority_keywords: tuple[str, ...]


DOCUMENT_KIND_AUTHORITY_KEYWORDS = {
    DocumentKind.PRIVACY_POLICY: (
        "개인정보 보호법",
        "개인정보 보호법 시행령",
        "개인정보 보호법 시행규칙",
        "정보통신망",
        "위치정보",
        "신용정보",
    ),
    DocumentKind.TERMS_OF_SERVICE: (
        "약관의 규제",
        "전자상거래",
        "소비자기본법",
        "소비자보호",
        "통신판매",
        "전기통신사업",
    ),
}


TOPIC_PROFILES = {
    ServiceTopic.GENERAL: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "전자상거래 등에서의 소비자보호에 관한 법률",
            "약관의 규제에 관한 법률",
            "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "전자상거래",
            "소비자보호",
            "약관의 규제",
            "정보통신망",
        ),
        retrieval_queries=(
            "개인정보 보호법",
            "전자상거래 소비자 보호",
            "약관의 규제에 관한 법률",
        ),
    ),
    ServiceTopic.ECOMMERCE: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "전자상거래 등에서의 소비자보호에 관한 법률",
            "약관의 규제에 관한 법률",
            "소비자기본법",
            "표시ㆍ광고의 공정화에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "전자상거래",
            "소비자보호",
            "약관의 규제",
            "소비자기본법",
            "표시ㆍ광고",
            "통신판매",
        ),
        retrieval_queries=(
            "전자상거래 소비자 보호",
            "통신판매 약관",
            "개인정보 처리방침 쇼핑몰",
        ),
    ),
    ServiceTopic.PLATFORM: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
            "전기통신사업법",
            "약관의 규제에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "정보통신망",
            "전기통신사업",
            "약관의 규제",
        ),
        retrieval_queries=(
            "온라인 플랫폼 이용약관",
            "정보통신망 개인정보",
            "플랫폼 회원 정책",
        ),
    ),
    ServiceTopic.LOCATION_BASED: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "위치정보의 보호 및 이용 등에 관한 법률",
            "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "위치정보",
            "정보통신망",
        ),
        retrieval_queries=(
            "위치정보 처리방침",
            "위치정보 이용약관",
            "위치정보 보호법",
        ),
    ),
    ServiceTopic.FINTECH: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "전자금융거래법",
            "신용정보의 이용 및 보호에 관한 법률",
            "약관의 규제에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "전자금융거래",
            "신용정보",
            "약관의 규제",
        ),
        retrieval_queries=(
            "전자금융 이용약관",
            "금융 개인정보 처리방침",
            "신용정보 보호",
        ),
    ),
    ServiceTopic.HEALTHCARE: TopicProfile(
        source_queries=(
            "개인정보 보호법",
            "의료법",
            "생명윤리 및 안전에 관한 법률",
            "약관의 규제에 관한 법률",
        ),
        authority_keywords=(
            "개인정보 보호",
            "의료법",
            "생명윤리",
            "약관의 규제",
        ),
        retrieval_queries=(
            "의료 서비스 개인정보 처리방침",
            "의료 서비스 이용약관",
            "민감정보 보호",
        ),
    ),
}


DEFAULT_SECTION_PROFILES = {
    DocumentKind.PRIVACY_POLICY: {
        "1. 개인정보의 수집 항목": SectionProfile(
            retrieval_queries=("개인정보 수집 이용", "동의", "수집 항목"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행규칙"),
        ),
        "2. 개인정보의 이용 목적": SectionProfile(
            retrieval_queries=("개인정보 이용 목적", "처리 목적"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행규칙"),
        ),
        "3. 개인정보의 보유 및 이용 기간": SectionProfile(
            retrieval_queries=("개인정보 보유 기간", "개인정보 파기", "보존"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행규칙"),
        ),
        "4. 개인정보 처리의 위탁": SectionProfile(
            retrieval_queries=("개인정보 처리 위탁", "수탁자 공개"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행령"),
        ),
        "5. 개인정보의 제3자 제공": SectionProfile(
            retrieval_queries=("개인정보 제3자 제공", "제공 요건"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행령"),
        ),
        "6. 정보주체의 권리": SectionProfile(
            retrieval_queries=("개인정보 열람 정정 삭제 처리정지", "정보주체 권리"),
            authority_keywords=("개인정보 보호법",),
        ),
        "7. 개인정보의 안전성 확보 조치": SectionProfile(
            retrieval_queries=("개인정보 안전성 확보 조치", "접근통제 암호화"),
            authority_keywords=("개인정보 보호법 시행령", "개인정보 보호법 시행규칙", "개인정보 보호법"),
        ),
        "8. 문의처 및 책임자": SectionProfile(
            retrieval_queries=("개인정보 보호책임자", "문의처"),
            authority_keywords=("개인정보 보호법", "개인정보 보호법 시행령"),
        ),
    },
    DocumentKind.TERMS_OF_SERVICE: {
        "제1조(목적)": SectionProfile(
            retrieval_queries=("약관 목적", "약관 작성 설명의무"),
            authority_keywords=("약관의 규제에 관한 법률",),
        ),
        "제2조(정의)": SectionProfile(
            retrieval_queries=("약관 정의", "회원 이용자 정의"),
            authority_keywords=("약관의 규제에 관한 법률", "전자상거래 등에서의 소비자보호에 관한 법률"),
        ),
        "제3조(서비스의 제공 및 변경)": SectionProfile(
            retrieval_queries=("재화 등의 공급", "서비스 제공 변경"),
            authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "소비자기본법"),
        ),
        "제4조(이용자의 의무)": SectionProfile(
            retrieval_queries=("이용자 의무", "금지행위"),
            authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "약관의 규제에 관한 법률"),
        ),
        "제5조(계약의 해지 및 이용제한)": SectionProfile(
            retrieval_queries=("청약철회", "계약 해지", "이용제한"),
            authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "약관의 규제에 관한 법률"),
        ),
        "제6조(면책)": SectionProfile(
            retrieval_queries=("면책조항", "손해배상 책임 제한"),
            authority_keywords=("약관의 규제에 관한 법률", "소비자기본법"),
        ),
        "제7조(분쟁 해결)": SectionProfile(
            retrieval_queries=("분쟁 해결", "소비자 불만 처리"),
            authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "소비자기본법"),
        ),
        "제8조(준거법 및 관할)": SectionProfile(
            retrieval_queries=("약관 해석", "관할"),
            authority_keywords=("약관의 규제에 관한 법률",),
        ),
    },
}


TOPIC_SECTION_OVERRIDES = {
    ServiceTopic.ECOMMERCE: {
        DocumentKind.PRIVACY_POLICY: {
            "3. 개인정보의 보유 및 이용 기간": SectionProfile(
                retrieval_queries=("거래기록 보존", "전자상거래 거래기록", "개인정보 보유 기간"),
                authority_keywords=("개인정보 보호법", "개인정보 보호법 시행규칙"),
            ),
        },
        DocumentKind.TERMS_OF_SERVICE: {
            "제3조(서비스의 제공 및 변경)": SectionProfile(
                retrieval_queries=("통신판매 재화 공급", "배송 고지", "서비스 제공 변경"),
                authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "소비자기본법"),
            ),
            "제5조(계약의 해지 및 이용제한)": SectionProfile(
                retrieval_queries=("청약철회", "환불", "계약 해지"),
                authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "약관의 규제에 관한 법률"),
            ),
            "제7조(분쟁 해결)": SectionProfile(
                retrieval_queries=("소비자 분쟁 해결", "민원 처리", "소비자 불만"),
                authority_keywords=("전자상거래 등에서의 소비자보호에 관한 법률", "소비자기본법"),
            ),
        },
    }
}


def get_topic_profile(service_topic: ServiceTopic | None) -> TopicProfile:
    if service_topic is None:
        return TOPIC_PROFILES[ServiceTopic.GENERAL]
    return TOPIC_PROFILES[service_topic]


def get_document_authority_keywords(document_kind: DocumentKind | None) -> tuple[str, ...]:
    if document_kind is None:
        return ()
    return DOCUMENT_KIND_AUTHORITY_KEYWORDS.get(document_kind, ())


def get_section_profile(
    service_topic: ServiceTopic | None,
    document_kind: DocumentKind,
    section_heading: str,
) -> SectionProfile:
    base = DEFAULT_SECTION_PROFILES.get(document_kind, {}).get(
        section_heading,
        SectionProfile(retrieval_queries=(), authority_keywords=()),
    )
    if service_topic is None:
        return base
    override = TOPIC_SECTION_OVERRIDES.get(service_topic, {}).get(document_kind, {}).get(section_heading)
    if override is None:
        return base
    return SectionProfile(
        retrieval_queries=_dedupe((*base.retrieval_queries, *override.retrieval_queries)),
        authority_keywords=_dedupe((*base.authority_keywords, *override.authority_keywords)),
    )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(value.split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)
