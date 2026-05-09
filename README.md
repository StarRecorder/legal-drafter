# legal-drafter

대한민국 법령 인덱스와 문서 생성 API를 제공하는 백엔드 중심 Python 라이브러리입니다. 프런트엔드 자산은 포함하지 않으며, 서버는 JSON API와 문서 산출물 전달에만 집중합니다.

## 핵심 기능

- `law.go.kr` Open API 기반 로컬 법령 인덱스 구축
- 카테고리 기반 문서 생성 API
- 수동 법령 선택 기반 초안 생성
- HTML 기본 산출물 생성
- 선택적 PDF/PNG 렌더링
- 로컬 백엔드 API 서버 제공

## 설치

기본 설치:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

선택 설치:

- OpenAI 제공자까지 쓰려면 `python -m pip install -e .[openai]`
- PDF/PNG 렌더링까지 쓰려면 `python -m pip install -e .[render]`
- 개발 도구까지 쓰려면 `python -m pip install -e .[dev]`

브라우저 렌더링을 쓸 경우 한 번만 추가로 실행합니다.

```bash
python -m playwright install chromium
```

## 환경 변수

- `LAW_API_OC`: law.go.kr Open API 키
- `OLLAMA_HOST`: 기본값 `http://localhost:11434`
- `OPENAI_API_KEY`: `OpenAIProvider` 사용 시 필요
- `LEGAL_DRAFTER_HOME`: 기본 데이터 디렉터리 override
- `LEGAL_DRAFTER_INDEX_PATH`: 기본 인덱스 파일 경로 override
- `LEGAL_DRAFTER_ARTIFACT_ROOT`: 기본 산출물 디렉터리 override
- `LEGAL_DRAFTER_ENV_FILE`: 사용할 `.env` 파일 경로 override

라이브러리는 현재 작업 디렉터리뿐 아니라 상위 디렉터리까지 올라가며 `.env`를 찾습니다.

## 기본 저장 경로

- 인덱스 기본 경로: `get_default_index_path()`
- 산출물 기본 경로: `get_default_artifact_root()`

OS별 사용자 데이터 디렉터리를 기본값으로 사용하므로, 특정 프로젝트 루트에 묶이지 않습니다.

## 인덱스 생성

```bash
legal-drafter-index refresh --service-topic ECOMMERCE --rebuild
```

중요 옵션:

- `--index-path`: 인덱스 파일 경로
- `--service-topic`: 수집/검색 주제
- `--oc`: 환경 변수 대신 직접 API 키 지정
- `--rebuild`: 기존 인덱스를 삭제하고 재생성

## 백엔드 서버 실행

```bash
legal-drafter-server --host 127.0.0.1 --port 8000
```

호환용으로 `legal-drafter-demo` 엔트리포인트도 같은 서버를 실행합니다.

루트 `/`는 상태 JSON을 반환하고, 주요 엔드포인트는 아래와 같습니다.

- `GET /api/options`
- `GET /api/categories`
- `GET /api/categories/{id}`
- `GET /api/laws/search`
- `POST /api/generate`
- `POST /api/documents`
- `GET /api/artifacts/{token}/{name}`

## Python 사용 예시

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
        category_id="privacy_policy/general",
        text="개인정보",
        index_path="law_index.sqlite3",
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

`render_document()`는 항상 HTML을 생성합니다. `playwright`와 Chromium이 준비된 경우 PDF/PNG도 함께 생성합니다. 렌더링 의존성이 없으면 기본적으로 HTML만 반환하고, `RenderOptions(strict=True)`일 때만 에러로 처리합니다.

## 지원 문서 유형

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

레거시 호환:

- `서비스 이용약관`
- `개인정보 처리방침`

## 제한사항

- 출력물은 참고용 초안이며 법률 자문이 아닙니다.
- 실제 적용 전에는 반드시 사람 전문가 검토가 필요합니다.
- 판례, 행정규칙, 유권해석은 현재 기본 지원 범위가 아닙니다.
