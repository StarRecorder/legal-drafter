from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


class DocumentKind(StrEnum):
    AUTO = "AUTO"
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    PRIVACY_POLICY = "PRIVACY_POLICY"


class SupportLevel(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"


class AuthorityKind(StrEnum):
    LAW = "LAW"
    ENFORCEMENT_DECREE = "ENFORCEMENT_DECREE"
    ENFORCEMENT_RULE = "ENFORCEMENT_RULE"


class ServiceTopic(StrEnum):
    GENERAL = "GENERAL"
    ECOMMERCE = "ECOMMERCE"
    PLATFORM = "PLATFORM"
    LOCATION_BASED = "LOCATION_BASED"
    FINTECH = "FINTECH"
    HEALTHCARE = "HEALTHCARE"


class ReviewFlag(StrEnum):
    STALE_INDEX = "STALE_INDEX"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    LOW_SUPPORT = "LOW_SUPPORT"
    AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
    NO_AUTHORITIES_FOUND = "NO_AUTHORITIES_FOUND"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"


class GenerationMode(StrEnum):
    HYBRID = "hybrid"


class ReviewPolicy(StrEnum):
    STANDARD = "standard"
    PROCEDURAL_STRICT = "procedural_strict"


class FieldKind(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    DATE = "date"
    NUMBER = "number"
    SELECT = "select"
    LIST = "list"
    GROUP = "group"


class SectionKind(StrEnum):
    TEMPLATE = "template"
    COMPUTED = "computed"
    LLM = "llm"


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


def _tupled(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


@dataclass(slots=True, frozen=True)
class Citation:
    authority_id: str
    authority_name: str
    authority_kind: AuthorityKind
    article_number: str
    article_title: str | None
    excerpt: str
    effective_date: str | None = None
    detail_url: str | None = None

    @property
    def reference(self) -> str:
        title = f" {self.article_title}" if self.article_title else ""
        return f"{self.authority_name} {self.article_number}{title}".strip()


@dataclass(slots=True)
class Provision:
    heading: str
    body: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    support_level: SupportLevel = SupportLevel.WEAK
    review_note: str | None = None


@dataclass(slots=True, frozen=True)
class FieldOption:
    value: str
    label: str


@dataclass(slots=True)
class FieldSpec:
    id: str
    label: str
    kind: FieldKind
    required: bool = False
    help_text: str | None = None
    placeholder: str | None = None
    options: tuple[FieldOption, ...] = field(default_factory=tuple)
    fields: tuple["FieldSpec", ...] = field(default_factory=tuple)
    repeatable: bool = False

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        if not self.id:
            raise ValueError("field spec id must not be empty")
        if not isinstance(self.kind, FieldKind):
            self.kind = FieldKind(self.kind)
        self.options = tuple(
            option if isinstance(option, FieldOption) else FieldOption(**option)
            for option in self.options
        )
        self.fields = tuple(
            child if isinstance(child, FieldSpec) else FieldSpec(**child)
            for child in self.fields
        )


@dataclass(slots=True)
class SectionSpec:
    id: str
    heading: str
    kind: SectionKind
    body_template: str | None = None
    instruction: str | None = None
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    review_note: str | None = None

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.heading = self.heading.strip()
        if not self.id:
            raise ValueError("section spec id must not be empty")
        if not self.heading:
            raise ValueError("section spec heading must not be empty")
        if not isinstance(self.kind, SectionKind):
            self.kind = SectionKind(self.kind)
        self.required_fields = _tupled(self.required_fields)


@dataclass(slots=True)
class CategorySpec:
    id: str
    parent_category: str
    label: str
    generation_mode: GenerationMode
    review_policy: ReviewPolicy
    seed_authority_keywords: tuple[str, ...] = field(default_factory=tuple)
    field_schema: tuple[FieldSpec, ...] = field(default_factory=tuple)
    section_schema: tuple[SectionSpec, ...] = field(default_factory=tuple)
    render_profile: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.parent_category = self.parent_category.strip()
        self.label = self.label.strip()
        if not self.id or not self.parent_category or not self.label:
            raise ValueError("category spec identifiers must not be empty")
        if not isinstance(self.generation_mode, GenerationMode):
            self.generation_mode = GenerationMode(self.generation_mode)
        if not isinstance(self.review_policy, ReviewPolicy):
            self.review_policy = ReviewPolicy(self.review_policy)
        self.seed_authority_keywords = _tupled(self.seed_authority_keywords)
        self.field_schema = tuple(
            field_spec if isinstance(field_spec, FieldSpec) else FieldSpec(**field_spec)
            for field_spec in self.field_schema
        )
        self.section_schema = tuple(
            section if isinstance(section, SectionSpec) else SectionSpec(**section)
            for section in self.section_schema
        )
        self.render_profile = {str(key): str(value) for key, value in self.render_profile.items()}


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR

    def __post_init__(self) -> None:
        self.path = self.path.strip()
        self.message = self.message.strip()
        if not self.path:
            raise ValueError("validation issue path must not be empty")
        if not self.message:
            raise ValueError("validation issue message must not be empty")
        if not isinstance(self.severity, ValidationSeverity):
            self.severity = ValidationSeverity(self.severity)


@dataclass(slots=True)
class DocumentSection:
    heading: str
    body: str
    kind: SectionKind
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    review_note: str | None = None


@dataclass(slots=True, frozen=True)
class LawSearchHit:
    authority_id: str
    authority_name: str
    authority_kind: AuthorityKind
    article_id: str
    article_number: str
    article_title: str | None
    excerpt: str
    effective_date: str | None
    detail_url: str | None
    score: float
    matched_seed: bool = False

    @property
    def citation(self) -> Citation:
        return Citation(
            authority_id=self.authority_id,
            authority_name=self.authority_name,
            authority_kind=self.authority_kind,
            article_number=self.article_number,
            article_title=self.article_title,
            excerpt=self.excerpt,
            effective_date=self.effective_date,
            detail_url=self.detail_url,
        )


@dataclass(slots=True)
class LawSearchQuery:
    index_path: Path | str
    category_id: str | None = None
    text: str | None = None
    top_k: int = 20
    effective_only: bool = True

    def __post_init__(self) -> None:
        self.index_path = Path(self.index_path)
        self.category_id = self.category_id.strip() if self.category_id else None
        self.text = " ".join(str(self.text or "").split()) or None
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")


@dataclass(slots=True)
class DocumentRequest:
    category_id: str
    field_values: dict[str, Any]
    selected_law_ids: tuple[str, ...] = field(default_factory=tuple)
    selected_article_ids: tuple[str, ...] = field(default_factory=tuple)
    freeform_facts: str | None = None
    constraints: tuple[str, ...] = field(default_factory=tuple)
    tone: str | None = None

    def __post_init__(self) -> None:
        self.category_id = self.category_id.strip()
        if not self.category_id:
            raise ValueError("category_id must not be empty")
        if not isinstance(self.field_values, dict):
            raise ValueError("field_values must be a mapping")
        self.field_values = {str(key): value for key, value in self.field_values.items()}
        self.selected_law_ids = _tupled(self.selected_law_ids)
        self.selected_article_ids = _tupled(self.selected_article_ids)
        self.freeform_facts = " ".join(str(self.freeform_facts or "").split()) or None
        self.constraints = _tupled(self.constraints)
        self.tone = (self.tone or "formal").strip()


@dataclass(slots=True)
class RenderOptions:
    artifact_root: Path | str | None = None
    artifact_token: str | None = None
    artifact_base_url: str | None = None

    def __post_init__(self) -> None:
        if self.artifact_root is not None:
            self.artifact_root = Path(self.artifact_root)
        self.artifact_token = self.artifact_token.strip() if self.artifact_token else None
        self.artifact_base_url = self.artifact_base_url.rstrip("/") if self.artifact_base_url else None


@dataclass(slots=True)
class RenderedArtifact:
    name: str
    kind: str
    path: Path | str
    content_type: str
    url: str | None = None

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.name = self.name.strip()
        self.kind = self.kind.strip()
        self.content_type = self.content_type.strip()


@dataclass(slots=True)
class DocumentResult:
    title: str
    category_id: str
    parent_category: str
    category_label: str
    summary: str
    sections: tuple[DocumentSection, ...]
    citations: tuple[Citation, ...]
    review_required: bool
    review_flags: tuple[ReviewFlag, ...]
    validation_issues: tuple[ValidationIssue, ...]
    generated_at: datetime
    rendered_artifacts: tuple[RenderedArtifact, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(slots=True)
class DraftRequest:
    prompt: str
    document_kind: DocumentKind = DocumentKind.AUTO
    service_topic: ServiceTopic | None = None
    organization_name: str | None = None
    service_description: str | None = None
    data_categories: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    tone: str | None = None

    def __post_init__(self) -> None:
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("prompt must not be empty")
        if self.service_topic is not None and not isinstance(self.service_topic, ServiceTopic):
            self.service_topic = ServiceTopic(self.service_topic)
        self.data_categories = _tupled(self.data_categories)
        self.constraints = _tupled(self.constraints)
        self.tone = (self.tone or "formal").strip()


@dataclass(slots=True)
class GenerationOptions:
    index_path: Path | str = Path("law_index.sqlite3")
    top_k: int = 30
    citations_per_provision: int = 3
    freshness_days: int = 7
    artifact_root: Path | str | None = None

    def __post_init__(self) -> None:
        self.index_path = Path(self.index_path)
        if self.artifact_root is not None:
            self.artifact_root = Path(self.artifact_root)
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.citations_per_provision <= 0:
            raise ValueError("citations_per_provision must be positive")
        if self.freshness_days <= 0:
            raise ValueError("freshness_days must be positive")


@dataclass(slots=True)
class DraftResult:
    title: str
    document_kind: DocumentKind
    service_topic: ServiceTopic | None
    summary: str
    provisions: tuple[Provision, ...]
    citations: tuple[Citation, ...]
    confidence: float
    review_required: bool
    review_flags: tuple[ReviewFlag, ...]
    generated_at: datetime
    index_snapshot_at: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return _serialize(asdict(self))


@dataclass(slots=True)
class SourceConfig:
    index_path: Path | str
    oc: str | None = None
    service_topic: ServiceTopic | None = None
    base_url: str = "https://www.law.go.kr"
    list_target: str = "eflaw"
    body_target: str = "law"
    page_size: int = 100
    request_timeout: float = 30.0
    max_pages: int | None = None
    search_query: str | None = None

    def __post_init__(self) -> None:
        resolved_oc = self.oc or _load_env_value("LAW_API_OC")
        if not resolved_oc or not resolved_oc.strip():
            raise ValueError("oc must not be empty")
        self.oc = resolved_oc.strip()
        if self.service_topic is not None and not isinstance(self.service_topic, ServiceTopic):
            self.service_topic = ServiceTopic(self.service_topic)
        self.index_path = Path(self.index_path)
        if self.page_size <= 0:
            raise ValueError("page_size must be positive")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be positive")


@dataclass(slots=True)
class RetrievalQuery:
    text: str
    index_path: Path | str
    document_kind: DocumentKind | None = None
    service_topic: ServiceTopic | None = None
    section_heading: str | None = None
    authority_keywords: tuple[str, ...] = field(default_factory=tuple)
    search_queries: tuple[str, ...] = field(default_factory=tuple)
    top_k: int = 10
    effective_only: bool = True

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("text must not be empty")
        self.index_path = Path(self.index_path)
        if self.service_topic is not None and not isinstance(self.service_topic, ServiceTopic):
            self.service_topic = ServiceTopic(self.service_topic)
        self.section_heading = self.section_heading.strip() if self.section_heading else None
        self.authority_keywords = _tupled(self.authority_keywords)
        self.search_queries = _tupled(self.search_queries)
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")


@dataclass(slots=True, frozen=True)
class AuthorityHit:
    authority_id: str
    authority_name: str
    authority_kind: AuthorityKind
    article_id: str
    article_number: str
    article_title: str | None
    excerpt: str
    effective_date: str | None
    score: float
    citation: Citation


@dataclass(slots=True)
class IndexStats:
    authority_count: int
    article_count: int
    snapshot_at: datetime | None


@dataclass(slots=True)
class AnalysisResult:
    document_kind: DocumentKind
    search_queries: tuple[str, ...]
    regulatory_topics: tuple[str, ...]
    summary: str
    ambiguities: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class ProviderAnalysis:
    document_kind: DocumentKind | None = None
    search_queries: tuple[str, ...] = field(default_factory=tuple)
    regulatory_topics: tuple[str, ...] = field(default_factory=tuple)
    summary: str | None = None
    ambiguities: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.search_queries = _tupled(self.search_queries)
        self.regulatory_topics = _tupled(self.regulatory_topics)
        self.ambiguities = _tupled(self.ambiguities)


def _serialize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _serialize(inner) for key, inner in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialize(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(inner) for inner in value]
    return value


def _load_env_value(key: str) -> str | None:
    direct = os.getenv(key)
    if direct and direct.strip():
        return direct.strip()

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != key:
            continue
        cleaned = value.strip().strip('"').strip("'")
        if cleaned:
            os.environ.setdefault(key, cleaned)
            return cleaned
    return None
