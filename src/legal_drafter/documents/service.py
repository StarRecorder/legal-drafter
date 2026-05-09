from __future__ import annotations

from datetime import UTC, datetime
from string import Formatter
from typing import Any

from legal_drafter.catalog import get_category_spec
from legal_drafter.exceptions import ProviderError
from legal_drafter.index import SQLiteIndex
from legal_drafter.models import (
    AuthorityKind,
    CategorySpec,
    Citation,
    DocumentRequest,
    DocumentResult,
    DocumentSection,
    FieldKind,
    FieldSpec,
    GenerationOptions,
    ReviewFlag,
    SectionKind,
    ValidationIssue,
    ValidationSeverity,
)
from legal_drafter.providers import LLMProvider
from legal_drafter.text_style import normalize_legal_text


def generate_document(
    request: DocumentRequest,
    provider: LLMProvider | None,
    options: GenerationOptions | None = None,
) -> DocumentResult:
    resolved_options = options or GenerationOptions()
    spec = get_category_spec(request.category_id)
    validation_issues = _validate_request(spec, request.field_values)
    citations = _resolve_selected_citations(request, resolved_options)
    context = _build_context(spec, request, citations)
    flags: set[ReviewFlag] = set()
    if not citations:
        flags.add(ReviewFlag.NO_AUTHORITIES_FOUND)
    if any(issue.severity == ValidationSeverity.ERROR for issue in validation_issues):
        flags.add(ReviewFlag.MISSING_REQUIRED_FIELDS)

    sections: list[DocumentSection] = []
    section_citations = citations[: resolved_options.citations_per_provision] or citations
    for section in spec.section_schema:
        review_note = _build_section_review_note(section, validation_issues)
        body = _render_section(
            provider=provider,
            request=request,
            spec=spec,
            section=section,
            context=context,
            citations=section_citations,
            flags=flags,
        )
        sections.append(
            DocumentSection(
                heading=section.heading,
                body=body,
                kind=section.kind,
                citations=section_citations,
                review_note=review_note,
            )
        )

    title = _safe_format(spec.render_profile["document_title_template"], context, blank="문서")
    summary = (
        f"{spec.label} 초안입니다. {len(sections)}개 섹션과 {len(citations)}개 인용 근거를 포함하며, "
        f"{len(validation_issues)}개의 검토 포인트가 표시되었습니다."
    )
    return DocumentResult(
        title=title,
        category_id=spec.id,
        parent_category=spec.parent_category,
        category_label=spec.label,
        summary=summary,
        sections=tuple(sections),
        citations=citations,
        review_required=True,
        review_flags=tuple(sorted(flags, key=lambda item: item.value)),
        validation_issues=tuple(validation_issues),
        generated_at=datetime.now(UTC),
    )


def _validate_request(spec: CategorySpec, field_values: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field_spec in spec.field_schema:
        value = field_values.get(field_spec.id)
        issues.extend(_validate_field(field_spec, value, field_spec.id))
    return issues


def _validate_field(field_spec: FieldSpec, value: Any, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if field_spec.kind == FieldKind.GROUP:
        entries = value if isinstance(value, list) else []
        if field_spec.required and not entries:
            issues.append(ValidationIssue(path=path, message=f"{field_spec.label} 항목이 필요합니다."))
            return issues
        if value is not None and not isinstance(value, list):
            issues.append(ValidationIssue(path=path, message=f"{field_spec.label}은(는) 배열 형식이어야 합니다."))
            return issues
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                issues.append(
                    ValidationIssue(
                        path=f"{path}[{index}]",
                        message=f"{field_spec.label}의 각 항목은 객체 형식이어야 합니다.",
                    )
                )
                continue
            for child in field_spec.fields:
                issues.extend(_validate_field(child, entry.get(child.id), f"{path}[{index}].{child.id}"))
        return issues

    if field_spec.kind == FieldKind.LIST:
        if field_spec.required and not _coerce_list(value):
            issues.append(ValidationIssue(path=path, message=f"{field_spec.label}을(를) 입력해야 합니다."))
        elif value is not None and not isinstance(value, (list, tuple, str)):
            issues.append(ValidationIssue(path=path, message=f"{field_spec.label}은(는) 문자열 또는 배열이어야 합니다."))
        return issues

    if field_spec.kind == FieldKind.SELECT and value:
        valid_values = {option.value for option in field_spec.options}
        if str(value) not in valid_values:
            issues.append(ValidationIssue(path=path, message=f"{field_spec.label} 값이 유효하지 않습니다."))

    if field_spec.required and not _has_value(value):
        issues.append(ValidationIssue(path=path, message=f"{field_spec.label}은(는) 필수 입력값입니다."))
    return issues


def _resolve_selected_citations(request: DocumentRequest, options: GenerationOptions) -> tuple[Citation, ...]:
    index = SQLiteIndex(options.index_path)
    rows = index.fetch_articles_by_ids(request.selected_article_ids)
    if request.selected_law_ids:
        rows = _merge_rows(
            rows,
            index.fetch_articles_by_authority_ids(
                request.selected_law_ids,
                limit_per_authority=max(1, options.citations_per_provision),
            ),
        )
    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        citation = Citation(
            authority_id=row["authority_id"],
            authority_name=row["authority_name"],
            authority_kind=AuthorityKind(row["authority_kind"]),
            article_number=row["article_number"],
            article_title=row["article_title"],
            excerpt=(row["excerpt"] or row["body"][:180]).strip(),
            effective_date=row["effective_date"],
            detail_url=row["detail_url"],
        )
        key = (citation.authority_id, citation.article_number)
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)
    return tuple(citations)


def _merge_rows(*row_groups):
    merged = []
    seen: set[str] = set()
    for rows in row_groups:
        for row in rows:
            article_id = row["article_id"]
            if article_id in seen:
                continue
            seen.add(article_id)
            merged.append(row)
    return merged


def _build_context(spec: CategorySpec, request: DocumentRequest, citations: tuple[Citation, ...]) -> dict[str, str]:
    context: dict[str, str] = {"today": datetime.now().date().isoformat()}
    for field_spec in spec.field_schema:
        context[field_spec.id] = _format_field_value(field_spec, request.field_values.get(field_spec.id))
    context["freeform_facts"] = request.freeform_facts or ""
    context["selected_law_names"] = ", ".join(_dedupe(citation.authority_name for citation in citations))
    context["selected_citation_references"] = ", ".join(citation.reference for citation in citations)
    context["document_title"] = context.get("contract_title") or spec.label
    return context


def _format_field_value(field_spec: FieldSpec, value: Any) -> str:
    if value is None:
        return ""
    if field_spec.kind == FieldKind.GROUP:
        entries = value if isinstance(value, list) else []
        rendered_entries: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            parts = [
                f"{child.label}: {str(entry.get(child.id, '')).strip()}"
                for child in field_spec.fields
                if str(entry.get(child.id, "")).strip()
            ]
            if parts:
                rendered_entries.append(", ".join(parts))
        return " / ".join(rendered_entries)
    if field_spec.kind == FieldKind.LIST:
        return ", ".join(_coerce_list(value))
    return str(value).strip()


def _render_section(
    *,
    provider: LLMProvider | None,
    request: DocumentRequest,
    spec: CategorySpec,
    section,
    context: dict[str, str],
    citations: tuple[Citation, ...],
    flags: set[ReviewFlag],
) -> str:
    if section.kind in {SectionKind.TEMPLATE, SectionKind.COMPUTED}:
        return normalize_legal_text(_safe_format(section.body_template or "", context), heading=section.heading)
    if provider is None:
        flags.add(ReviewFlag.PROVIDER_ERROR)
        return normalize_legal_text(
            _fallback_section_text(spec.label, section.heading, section.instruction or "", citations),
            heading=section.heading,
        )
    try:
        drafted = provider.draft_document_section(
            category_id=request.category_id,
            category_label=spec.label,
            heading=section.heading,
            instruction=section.instruction or "",
            field_values=request.field_values,
            freeform_facts=request.freeform_facts,
            citations=citations,
            constraints=request.constraints,
            tone=request.tone or "formal",
        ).strip()
        return normalize_legal_text(drafted, heading=section.heading)
    except ProviderError:
        flags.add(ReviewFlag.PROVIDER_ERROR)
        return normalize_legal_text(
            _fallback_section_text(spec.label, section.heading, section.instruction or "", citations),
            heading=section.heading,
        )


def _fallback_section_text(category_label: str, heading: str, instruction: str, citations: tuple[Citation, ...]) -> str:
    citation_text = ", ".join(citation.reference for citation in citations[:2]) if citations else "선택된 법령 검토"
    return (
        f"{category_label}의 {heading}와 관련된 사항은 {instruction or '핵심 사실관계와 권리·의무 범위에 따라'} "
        f"{citation_text} 등 관계 법령의 범위에서 정합니다."
    ).strip()


def _build_section_review_note(section, issues: list[ValidationIssue]) -> str | None:
    relevant_paths = {issue.path.split("[", 1)[0].split(".", 1)[0] for issue in issues}
    missing = [field_id for field_id in section.required_fields if field_id in relevant_paths]
    notes: list[str] = []
    if missing:
        notes.append(f"필수 입력값 검토 필요: {', '.join(missing)}")
    if section.review_note:
        notes.append(section.review_note)
    return " ".join(notes) if notes else None


def _safe_format(template: str, context: dict[str, str], *, blank: str = "________") -> str:
    parts: list[str] = []
    for literal_text, field_name, format_spec, conversion in Formatter().parse(template):
        parts.append(literal_text)
        if field_name is None:
            continue
        value = context.get(field_name, "")
        parts.append(value if value else blank)
    return "".join(parts).strip()


def _coerce_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("\r", "\n").replace(",", "\n").split("\n")]
        return tuple(part for part in parts if part)
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def _dedupe(values):
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return tuple(result)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True
