from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from legal_drafter.exceptions import ProviderError
from legal_drafter.models import Citation, DocumentKind, DraftRequest, ProviderAnalysis

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI Responses API backed provider."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        temperature: float = 0.2,
        timeout: float | None = 30.0,
    ) -> None:
        resolved_api_key = api_key or _load_api_key_from_environment()
        if not resolved_api_key or not resolved_api_key.strip():
            raise ValueError("api_key must not be empty")
        if not model.strip():
            raise ValueError("model must not be empty")
        self.api_key = resolved_api_key.strip()
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.timeout = timeout
        self._client = self._build_client()

    def analyze_request(
        self,
        request: DraftRequest,
        fallback_kind: DocumentKind,
    ) -> ProviderAnalysis:
        schema = {
            "type": "object",
            "properties": {
                "document_kind": {
                    "type": "string",
                    "enum": [
                        DocumentKind.TERMS_OF_SERVICE.value,
                        DocumentKind.PRIVACY_POLICY.value,
                    ],
                },
                "search_queries": {"type": "array", "items": {"type": "string"}},
                "regulatory_topics": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
                "ambiguities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["document_kind", "search_queries", "regulatory_topics", "summary", "ambiguities"],
            "additionalProperties": False,
        }
        prompt = {
            "prompt": request.prompt,
            "fallback_kind": fallback_kind.value,
            "service_topic": request.service_topic.value if request.service_topic is not None else None,
            "organization_name": request.organization_name,
            "service_description": request.service_description,
            "data_categories": list(request.data_categories),
            "constraints": list(request.constraints),
            "tone": request.tone,
        }
        payload = self._structured_response(
            instructions=(
                "당신은 대한민국 법령 기반 규정 초안 생성을 위한 분석기입니다. "
                "반드시 JSON 스키마에 맞게만 응답하고, 문서 유형은 TERMS_OF_SERVICE 또는 PRIVACY_POLICY 중 하나로 결정하십시오."
            ),
            input_text=json.dumps(prompt, ensure_ascii=False),
            schema_name="draft_request_analysis",
            schema=schema,
            max_output_tokens=800,
        )
        try:
            kind = DocumentKind(payload["document_kind"])
        except Exception as exc:
            raise ProviderError("provider returned an invalid document kind") from exc
        return ProviderAnalysis(
            document_kind=kind,
            search_queries=tuple(payload["search_queries"]),
            regulatory_topics=tuple(payload["regulatory_topics"]),
            summary=payload["summary"],
            ambiguities=tuple(payload["ambiguities"]),
        )

    def draft_provision(
        self,
        request: DraftRequest,
        document_kind: DocumentKind,
        heading: str,
        instruction: str,
        citations: tuple[Citation, ...],
        regulatory_topics: tuple[str, ...],
    ) -> str:
        prompt = {
            "document_kind": document_kind.value,
            "service_topic": request.service_topic.value if request.service_topic is not None else None,
            "heading": heading,
            "instruction": instruction,
            "organization_name": request.organization_name,
            "service_description": request.service_description,
            "prompt": request.prompt,
            "data_categories": list(request.data_categories),
            "constraints": list(request.constraints),
            "tone": request.tone,
            "regulatory_topics": list(regulatory_topics),
            "citations": [
                {"reference": citation.reference, "excerpt": citation.excerpt}
                for citation in citations
            ],
        }
        response = self._text_response(
            instructions=(
                "당신은 대한민국 법령에 맞는 초안 작성기입니다. "
                "주어진 근거 조문을 벗어나지 말고 한국어의 정중한 법률 문체로만 조항 본문을 작성하십시오. "
                "조항 제목은 반복하지 말고 본문만 2~4문장으로 작성하십시오. "
                "마크다운 문법, 목록 기호, 불릿, 굵게 표시, 설명조 표현, 상담 안내 문구는 절대 사용하지 마십시오. "
                "문장은 공시문 또는 계약 조항처럼 '~합니다', '~정합니다', '~할 수 있습니다' 계열로 마무리하십시오. "
                "'수집 항목', '이용 목적' 같은 소제목 라벨을 따로 줄바꿈해 쓰지 말고, 완전한 문장으로 이어서 작성하십시오."
            ),
            input_text=json.dumps(prompt, ensure_ascii=False),
            max_output_tokens=900,
        )
        if not response:
            raise ProviderError("provider returned an empty provision")
        return response

    def draft_document_section(
        self,
        *,
        category_id: str,
        category_label: str,
        heading: str,
        instruction: str,
        field_values: dict[str, object],
        freeform_facts: str | None,
        citations: tuple[Citation, ...],
        constraints: tuple[str, ...],
        tone: str,
    ) -> str:
        prompt = {
            "category_id": category_id,
            "category_label": category_label,
            "heading": heading,
            "instruction": instruction,
            "field_values": field_values,
            "freeform_facts": freeform_facts,
            "constraints": list(constraints),
            "tone": tone,
            "citations": [
                {"reference": citation.reference, "excerpt": citation.excerpt}
                for citation in citations
            ],
        }
        response = self._text_response(
            instructions=(
                "당신은 대한민국 법률 문서 초안 작성기입니다. "
                "반드시 주어진 사실관계와 선택된 법령 발췌만 근거로 사용하십시오. "
                "문서 유형에 맞는 정중한 법률 문체로 한국어 본문만 2~5문장으로 작성하십시오. "
                "제목은 반복하지 말고, 사실이 비어 있으면 일반적이고 보수적인 문구로 한정하십시오. "
                "마크다운 문법, 목록 기호, 불릿, 굵게 표시, 해설조 문장, AI 안내 문구는 절대 사용하지 마십시오. "
                "문장은 조항형 선언 문체로 마무리하고, '본 문서는' 같은 메타 설명은 쓰지 마십시오. "
                "소제목형 라벨이나 체크리스트를 쓰지 말고, 모든 내용을 완전한 법률 문장으로 이어서 작성하십시오."
            ),
            input_text=json.dumps(prompt, ensure_ascii=False),
            max_output_tokens=1000,
        )
        if not response:
            raise ProviderError("provider returned an empty document section")
        return response

    def _build_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("OpenAIProvider requires the optional 'openai' package") from exc
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.timeout is not None:
            kwargs["timeout"] = self.timeout
        return OpenAI(**kwargs)

    def _structured_response(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        max_output_tokens: int,
    ) -> dict[str, Any]:
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=instructions,
                input=input_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                temperature=self.temperature,
                max_output_tokens=max_output_tokens,
            )
            output_text = getattr(response, "output_text", None)
            if not output_text:
                raise ProviderError("provider returned no structured output")
            return json.loads(output_text)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ProviderError("OpenAI structured request failed") from exc

    def _text_response(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        try:
            response = self._client.responses.create(
                model=self.model,
                instructions=instructions,
                input=input_text,
                text={"format": {"type": "text"}},
                temperature=self.temperature,
                max_output_tokens=max_output_tokens,
            )
            output_text = getattr(response, "output_text", None)
            if not output_text:
                raise ProviderError("provider returned no text output")
            return str(output_text).strip()
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ProviderError("OpenAI text request failed") from exc


def _load_api_key_from_environment() -> str | None:
    direct = os.getenv("OPENAI_API_KEY")
    if direct and direct.strip():
        return direct.strip()

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            os.environ.setdefault("OPENAI_API_KEY", cleaned)
            return cleaned
    return None
