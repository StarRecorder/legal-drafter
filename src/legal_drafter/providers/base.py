from __future__ import annotations

from abc import ABC, abstractmethod

from legal_drafter.exceptions import ProviderError
from legal_drafter.models import Citation, DocumentKind, DraftRequest, ProviderAnalysis


class LLMProvider(ABC):
    """Synchronous provider contract for analysis and section drafting."""

    @abstractmethod
    def analyze_request(
        self,
        request: DraftRequest,
        fallback_kind: DocumentKind,
    ) -> ProviderAnalysis:
        raise NotImplementedError

    @abstractmethod
    def draft_provision(
        self,
        request: DraftRequest,
        document_kind: DocumentKind,
        heading: str,
        instruction: str,
        citations: tuple[Citation, ...],
        regulatory_topics: tuple[str, ...],
    ) -> str:
        raise NotImplementedError

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
        raise ProviderError(f"{self.__class__.__name__} does not support category-driven document drafting")
