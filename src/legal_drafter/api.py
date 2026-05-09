from __future__ import annotations

from legal_drafter.catalog import get_category_spec as get_category_spec_entry, list_categories as list_category_entries
from legal_drafter.documents.service import generate_document as generate_category_document
from legal_drafter.generation.service import generate_draft_from_request
from legal_drafter.law_search import search_laws as search_laws_query
from legal_drafter.models import DraftRequest, DraftResult, GenerationOptions, IndexStats, RetrievalQuery, SourceConfig
from legal_drafter.models import CategorySpec, DocumentRequest, DocumentResult, LawSearchHit, LawSearchQuery, RenderOptions
from legal_drafter.providers import LLMProvider
from legal_drafter.renderers.document import render_document as render_document_result
from legal_drafter.renderers.markdown import render_markdown as render_markdown_result
from legal_drafter.retrieval.service import retrieve_authority_hits
from legal_drafter.sources.law_api import refresh_index_from_source


def generate_draft(
    request: DraftRequest,
    provider: LLMProvider,
    options: GenerationOptions | None = None,
) -> DraftResult:
    return generate_draft_from_request(request, provider, options or GenerationOptions())


def refresh_index(config: SourceConfig, rebuild: bool = False) -> IndexStats:
    return refresh_index_from_source(config, rebuild=rebuild)


def retrieve_authorities(query: RetrievalQuery):
    return retrieve_authority_hits(query)


def render_markdown(result: DraftResult) -> str:
    return render_markdown_result(result)


def list_categories() -> tuple[CategorySpec, ...]:
    return list_category_entries()


def get_category_spec(category_id: str) -> CategorySpec:
    return get_category_spec_entry(category_id)


def search_laws(query: LawSearchQuery) -> tuple[LawSearchHit, ...]:
    return search_laws_query(query)


def generate_document(
    request: DocumentRequest,
    provider: LLMProvider | None,
    options: GenerationOptions | None = None,
) -> DocumentResult:
    return generate_category_document(request, provider, options or GenerationOptions())


def render_document(result: DocumentResult, options: RenderOptions | None = None) -> DocumentResult:
    return render_document_result(result, options or RenderOptions())
