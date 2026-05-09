from __future__ import annotations

from dataclasses import dataclass

from legal_drafter.models import DocumentKind


@dataclass(frozen=True, slots=True)
class TemplateSection:
    heading: str
    instruction: str
    keywords: tuple[str, ...]


TERMS_TEMPLATE = (
    TemplateSection("제1조(목적)", "서비스 제공 목적과 약관의 적용 범위를 명확히 규정한다.", ("목적", "서비스", "이용약관")),
    TemplateSection("제2조(정의)", "서비스, 회원, 이용자, 계정 등 핵심 용어를 정의한다.", ("정의", "회원", "이용자", "서비스")),
    TemplateSection("제3조(서비스의 제공 및 변경)", "서비스 제공, 변경, 중단 요건과 절차를 명확히 정한다.", ("서비스", "제공", "변경", "중단")),
    TemplateSection("제4조(이용자의 의무)", "법령 준수, 금지행위, 계정관리 의무를 규정한다.", ("이용자", "의무", "금지", "준수")),
    TemplateSection("제5조(계약의 해지 및 이용제한)", "탈퇴, 해지, 이용제한 사유와 절차를 규정한다.", ("해지", "탈퇴", "이용제한", "계약")),
    TemplateSection("제6조(면책)", "회사의 책임 제한 범위를 법령에 반하지 않게 규정한다.", ("면책", "책임", "손해배상")),
    TemplateSection("제7조(분쟁 해결)", "민원 처리와 분쟁 해결 절차를 정한다.", ("분쟁", "민원", "해결")),
    TemplateSection("제8조(준거법 및 관할)", "준거법과 관할 법원을 명시한다.", ("준거법", "관할", "재판")),
)

PRIVACY_TEMPLATE = (
    TemplateSection("1. 개인정보의 수집 항목", "수집하는 개인정보 항목을 서비스 맥락에 맞게 구체적으로 적는다.", ("수집", "개인정보", "항목")),
    TemplateSection("2. 개인정보의 이용 목적", "수집한 개인정보의 이용 목적을 명확히 적는다.", ("이용", "목적", "개인정보")),
    TemplateSection("3. 개인정보의 보유 및 이용 기간", "보유 기간과 파기 기준을 적는다.", ("보유", "기간", "파기")),
    TemplateSection("4. 개인정보 처리의 위탁", "위탁 현황 또는 위탁 가능성과 관리 기준을 적는다.", ("위탁", "처리")),
    TemplateSection("5. 개인정보의 제3자 제공", "제3자 제공 여부와 예외 기준을 적는다.", ("제3자", "제공")),
    TemplateSection("6. 정보주체의 권리", "열람, 정정, 삭제, 처리정지 권리를 적는다.", ("권리", "열람", "정정", "삭제")),
    TemplateSection("7. 개인정보의 안전성 확보 조치", "접근통제, 암호화, 보관 통제 등 조치를 적는다.", ("안전성", "보호조치", "암호화")),
    TemplateSection("8. 문의처 및 책임자", "연락창구와 책임부서를 적는다.", ("문의처", "책임자", "연락처")),
)


def get_template(document_kind: DocumentKind) -> tuple[TemplateSection, ...]:
    if document_kind == DocumentKind.PRIVACY_POLICY:
        return PRIVACY_TEMPLATE
    return TERMS_TEMPLATE
