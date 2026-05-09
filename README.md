# legal-drafter

대한민국 법령, 시행령, 시행규칙을 로컬 SQLite FTS5 인덱스로 구축한 뒤, 카테고리 기반 한국어 법률 문서 초안과 인쇄형 산출물을 생성하는 Python 라이브러리입니다.

English summary: `legal-drafter` is a category-driven Korean legal document drafting library with a local law index, manual law selection, and HTML/PDF/PNG rendering.

## 핵심 기능

- `law.go.kr` Open API 기반의 로컬 법령 인덱스 구축
- `list_categories`, `get_category_spec`, `search_laws`, `generate_document`, `render_document` 공개 API 제공
- 레거시 호환용 `generate_draft`, `refresh_index`, `retrieve_authorities`, `render_markdown` 공개 API 유지
- `OllamaProvider` 기반 무료 로컬 생성 경로 제공
- `OpenAIProvider` 기반 대체 생성 경로 제공
- 카테고리/서브타입/동적 필드/수동 법령 선택 기반의 문서 생성 흐름 제공
- HTML 인쇄본, A4 PDF, 페이지별 PNG 미리보기 렌더링 제공
- 브라우저에서 바로 점검할 수 있는 스키마 기반 로컬 데모 페이지 제공

## 지원 범위

- 입력 언어: 한국어
- 문서 유형:
  - `개인정보처리방침`
  - `용역계약서`
  - `매매계약서`
  - `금전분쟁 합의서`
  - `대금지급 내용증명`
  - `지급명령 신청서`
  - `사기 고소장`
  - `근로계약서`
  - `차용증`
  - `위임장`
- 레거시 문서 유형: `서비스 이용약관`, `개인정보 처리방침`
- 법령 범위: 대한민국 `법률 + 시행령 + 시행규칙`
- 제외 범위: 판례, 행정규칙, 유권해석, 법률 자문 대체 용도

## 설치

PyPI 배포 전 단계이므로 저장소를 체크아웃한 뒤 설치하는 흐름을 전제로 합니다.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m playwright install chromium
```

선택 설치:

- OpenAI 어댑터까지 쓰려면 `.venv\Scripts\python.exe -m pip install -e .[openai]`
- 개발용 린트까지 쓰려면 `.venv\Scripts\python.exe -m pip install -e .[dev]`

## 환경 변수

루트의 `.env.example`를 참고해 `.env`를 구성합니다.

- `LAW_API_OC`: law.go.kr Open API의 `OC` 키
- `OLLAMA_HOST`: 기본값 `http://localhost:11434`
- `OPENAI_API_KEY`: `OpenAIProvider` 사용 시에만 필요

`SourceConfig`는 `oc`를 직접 넘기지 않으면 환경 변수 또는 `.env`의 `LAW_API_OC`를 읽습니다.

## 서비스 주제 선택지

- `GENERAL`
- `ECOMMERCE`
- `PLATFORM`
- `LOCATION_BASED`
- `FINTECH`
- `HEALTHCARE`

주제 선택지는 수집 대상 법령군과 검색 우선순위에 모두 반영됩니다.

## 1. 법령 인덱스 생성

```powershell
.venv\Scripts\legal-drafter-index.exe refresh --service-topic ECOMMERCE --rebuild
```

자주 쓰는 옵션:

- `--index-path`: SQLite 파일 경로 지정
- `--service-topic`: 주제별 수집/검색 필터 지정
- `--oc`: 환경 변수 대신 직접 `OC` 키 전달
- `--rebuild`: 기존 인덱스를 삭제하고 재생성

## 2. Ollama 준비

데모 페이지는 `Ollama` 전용입니다.

```powershell
ollama pull llama3.2
ollama serve
```

## 3. 로컬 데모 실행

```powershell
.venv\Scripts\legal-drafter-demo.exe --index-path law_index.sqlite3 --model llama3.2 --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000`을 열면 `examples/demo/index.html` 기반 데모 페이지가 표시됩니다.

데모 페이지 흐름:

- 상위 문서 카테고리 선택
- 서브타입 선택
- 스펙 기반 입력 필드 작성
- 카테고리별 법령 검색 및 수동 선택
- PDF/PNG 산출물 생성

## 4. 카테고리형 API 사용 예시

```python
from legal_drafter import (
    DocumentRequest,
    GenerationOptions,
    LawSearchQuery,
    OllamaProvider,
    generate_document,
    render_document,
    search_laws,
)

hits = search_laws(
    LawSearchQuery(
        index_path="law_index.sqlite3",
        category_id="privacy_policy/general",
        text="개인정보",
    )
)

result = generate_document(
    DocumentRequest(
        category_id="privacy_policy/general",
        field_values={
            "company_name": "예시회사",
            "service_name": "모바일 쇼핑 서비스",
            "contact_email": "privacy@example.com",
            "data_categories": ("이메일", "휴대전화번호", "주문정보"),
            "retention_policy": "관련 법령상 보존기간 동안 보관 후 파기",
        },
        selected_article_ids=(hits[0].article_id,),
        freeform_facts="쇼핑몰 회원가입 및 주문 처리",
    ),
    OllamaProvider(model="llama3.2"),
    GenerationOptions(index_path="law_index.sqlite3"),
)

rendered = render_document(result)
print(rendered.as_dict())
```

`render_document`는 기본적으로 임시 디렉터리에 `document.html`, `document.pdf`, `page-*.png`를 생성합니다.

## 5. 레거시 API 사용 예시

```python
from legal_drafter import (
    DocumentKind,
    DraftRequest,
    GenerationOptions,
    OllamaProvider,
    ServiceTopic,
    SourceConfig,
    generate_draft,
    refresh_index,
    render_markdown,
)

refresh_index(
    SourceConfig(
        index_path="law_index.sqlite3",
        service_topic=ServiceTopic.ECOMMERCE,
    ),
    rebuild=True,
)

result = generate_draft(
    DraftRequest(
        prompt="모바일 쇼핑 서비스 개인정보 처리방침 초안을 만들어줘",
        document_kind=DocumentKind.PRIVACY_POLICY,
        service_topic=ServiceTopic.ECOMMERCE,
        organization_name="예시회사",
        service_description="모바일 쇼핑 서비스",
        data_categories=("이메일", "휴대전화번호", "주문정보"),
    ),
    OllamaProvider(model="llama3.2"),
    GenerationOptions(index_path="law_index.sqlite3"),
)

print(result.as_dict())
print(render_markdown(result))
```

## 검색/생성 품질 기준

현재 검색 파이프라인은 다음 순서로 필터링합니다.

1. `service_topic` 기준 법령군 축소
2. `document_kind` 기준 법령군 축소
3. 섹션 제목 기준 법령군 축소
4. 그 안에서 BM25, 법위계, 제목 일치, 본문 일치, authority keyword bonus로 재정렬

예시 기준:

- `ECOMMERCE + PRIVACY_POLICY`는 `개인정보 보호법` 계열을 우선합니다.
- `ECOMMERCE + TERMS_OF_SERVICE`는 `전자상거래법`, `약관규제법`, `소비자기본법` 계열을 우선합니다.

## 테스트와 CI

로컬 테스트:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check src tests
```

GitHub Actions CI는 다음 조합으로 실행됩니다.

- Python 3.11
- Python 3.12
- `ruff check src tests`
- `python -m unittest discover -s tests -v`

CI에는 live `law.go.kr`, live `Ollama` 호출을 넣지 않았습니다. fixture와 mock 기반 테스트만 사용합니다.

## 수동 Smoke 절차

1. `.env`에 `LAW_API_OC`를 설정합니다.
2. `ollama pull llama3.2`와 `ollama serve`를 준비합니다.
3. `legal-drafter-index refresh --service-topic ECOMMERCE --rebuild`를 실행합니다.
4. `legal-drafter-demo --model llama3.2`를 실행합니다.
5. 브라우저에서 `ECOMMERCE + 개인정보 처리방침` 요청을 생성합니다.
6. citation 목록이 `개인정보 보호법` 또는 `전자상거래법` 계열 위주인지 확인합니다.

## 제한사항

- 생성 결과는 실무 초안이지 법률 자문이 아닙니다.
- 서비스의 실제 처리 방식, 위탁 구조, 제3자 제공 현황은 사용자 입력이 정확해야 합니다.
- 인덱스가 오래되었거나 근거가 약한 조항은 `review_required`와 `review_flags`에 반영됩니다.
- 데모 페이지는 인덱스 갱신 기능을 포함하지 않으며, 생성만 테스트합니다.

## 법적 면책

이 프로젝트의 출력물은 참고용 초안입니다. 실제 서비스에 게시하거나 신고, 계약, 고지 문서로 사용하기 전에는 반드시 사람 법률 전문가의 검토를 거쳐야 합니다.
