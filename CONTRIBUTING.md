# Contributing

## 개발 환경 준비

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[openai,dev]
```

`OpenAIProvider`를 직접 테스트하지 않는 경우에도 `openai` extra는 선택 사항입니다.

## 작업 원칙

- 공개 API 시그니처 `generate_draft`, `refresh_index`, `retrieve_authorities`, `render_markdown`는 호환성을 우선합니다.
- 검색 품질을 바꾸는 수정은 반드시 회귀 테스트를 함께 추가합니다.
- CI에서는 live `law.go.kr`, live `Ollama` 호출을 사용하지 않습니다. fixture와 mock 기반 테스트를 유지합니다.
- `.env`, `law_index.sqlite3`, 개인용 로그/산출물은 커밋하지 않습니다.

## 테스트

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 린트

```powershell
.venv\Scripts\python.exe -m ruff check src tests
```

## 인덱스 스모크 테스트

```powershell
.venv\Scripts\legal-drafter-index.exe refresh --service-topic ECOMMERCE --rebuild
```

## 로컬 데모

1. `.env` 또는 환경 변수에 `LAW_API_OC`를 설정합니다.
2. `ollama serve`와 `ollama pull llama3.2`를 준비합니다.
3. `.venv\Scripts\legal-drafter-index.exe refresh --service-topic ECOMMERCE --rebuild`
4. `.venv\Scripts\legal-drafter-demo.exe --model llama3.2`
5. 브라우저에서 `http://127.0.0.1:8000`을 열고 `ECOMMERCE + 개인정보 처리방침` 예시를 생성합니다.

## 기대 기준

- `ECOMMERCE + PRIVACY_POLICY` 생성 결과에서 비관련 `112/119` 계열 인용이 나오지 않아야 합니다.
- `ECOMMERCE + TERMS_OF_SERVICE` 생성 결과는 `전자상거래법`, `약관규제법`, `소비자기본법` 계열 인용을 우선해야 합니다.
