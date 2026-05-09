# Changelog

## 0.1.0

- GitHub 공개 준비를 위한 패키지 메타데이터, MIT 라이선스, CI, 기여 가이드 추가
- 대한민국 법령, 시행령, 시행규칙 기반 SQLite FTS5 인덱스 구축 및 검색 API 제공
- `generate_draft`, `refresh_index`, `retrieve_authorities`, `render_markdown` 공개 API 제공
- `service_topic + document_kind + section heading` 기반 법령 우선순위 필터 추가
- `OpenAIProvider`와 `OllamaProvider`를 포함한 provider-agnostic 생성 인터페이스 제공
- `legal-drafter-index`, `legal-drafter-demo` CLI 및 브라우저용 로컬 데모 페이지 추가
- unit test, 회귀 테스트, HTTP 데모 서버 테스트를 포함한 기본 검증 체계 구성
