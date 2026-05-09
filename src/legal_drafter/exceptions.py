from __future__ import annotations


class LegalDrafterError(Exception):
    """Base exception for the library."""


class IndexNotFoundError(LegalDrafterError):
    """Raised when no local authority index is available."""


class IndexRefreshError(LegalDrafterError):
    """Raised when the local index cannot be refreshed."""


class ProviderError(LegalDrafterError):
    """Raised when an LLM provider call fails."""


class SourceFetchError(LegalDrafterError):
    """Raised when the upstream legal source cannot be fetched or parsed."""


class CategorySpecError(LegalDrafterError):
    """Raised when a category specification is invalid or missing."""


class RenderError(LegalDrafterError):
    """Raised when a document artifact cannot be rendered."""
