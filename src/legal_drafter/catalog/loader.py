from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from legal_drafter.exceptions import CategorySpecError
from legal_drafter.models import CategorySpec, FieldKind

SPEC_DIR = Path(__file__).with_name("specs")
PLACEHOLDER_PATTERN = re.compile(r"{([a-zA-Z0-9_]+)}")
BUILTIN_CONTEXT_KEYS = {
    "document_title",
    "freeform_facts",
    "selected_citation_references",
    "selected_law_names",
    "today",
}


def list_categories() -> tuple[CategorySpec, ...]:
    return _load_registry()


def get_category_spec(category_id: str) -> CategorySpec:
    for spec in _load_registry():
        if spec.id == category_id:
            return spec
    raise CategorySpecError(f"unknown category spec: {category_id}")


@lru_cache(maxsize=1)
def _load_registry() -> tuple[CategorySpec, ...]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise CategorySpecError("PyYAML is required to load category specs") from exc

    specs: list[CategorySpec] = []
    seen_ids: set[str] = set()
    for path in sorted(SPEC_DIR.rglob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise CategorySpecError(f"spec must be a mapping: {path}")
        spec = CategorySpec(**payload)
        if spec.id in seen_ids:
            raise CategorySpecError(f"duplicate category id: {spec.id}")
        seen_ids.add(spec.id)
        _validate_category_spec(spec, path)
        specs.append(spec)
    if not specs:
        raise CategorySpecError("no category specs found")
    return tuple(specs)


def _validate_category_spec(spec: CategorySpec, path: Path) -> None:
    if not spec.field_schema:
        raise CategorySpecError(f"{path}: field_schema must not be empty")
    if not spec.section_schema:
        raise CategorySpecError(f"{path}: section_schema must not be empty")
    if "document_title_template" not in spec.render_profile:
        raise CategorySpecError(f"{path}: render_profile.document_title_template is required")

    top_level_ids: set[str] = set()
    for field_spec in spec.field_schema:
        if field_spec.id in top_level_ids:
            raise CategorySpecError(f"{path}: duplicate field id {field_spec.id}")
        top_level_ids.add(field_spec.id)
        _validate_field_spec(spec, field_spec, path)

    valid_placeholders = top_level_ids | BUILTIN_CONTEXT_KEYS
    _validate_placeholders(spec.render_profile["document_title_template"], valid_placeholders, path)
    footer_notice = spec.render_profile.get("footer_notice")
    if footer_notice:
        _validate_placeholders(footer_notice, valid_placeholders, path)

    section_ids: set[str] = set()
    for section in spec.section_schema:
        if section.id in section_ids:
            raise CategorySpecError(f"{path}: duplicate section id {section.id}")
        section_ids.add(section.id)
        if section.kind.value in {"template", "computed"} and not section.body_template:
            raise CategorySpecError(f"{path}: section {section.id} requires body_template")
        if section.kind.value == "llm" and not section.instruction:
            raise CategorySpecError(f"{path}: section {section.id} requires instruction")
        if section.body_template:
            _validate_placeholders(section.body_template, valid_placeholders, path)
        for field_id in section.required_fields:
            if field_id not in valid_placeholders:
                raise CategorySpecError(f"{path}: section {section.id} references unknown field {field_id}")


def _validate_field_spec(spec: CategorySpec, field_spec, path: Path) -> None:
    if field_spec.kind == FieldKind.SELECT and not field_spec.options:
        raise CategorySpecError(f"{path}: select field {field_spec.id} requires options")
    if field_spec.kind == FieldKind.GROUP:
        if not field_spec.fields:
            raise CategorySpecError(f"{path}: group field {field_spec.id} requires nested fields")
        child_ids: set[str] = set()
        for child in field_spec.fields:
            if child.id in child_ids:
                raise CategorySpecError(f"{path}: duplicate child field {field_spec.id}.{child.id}")
            child_ids.add(child.id)


def _validate_placeholders(template: str, valid_keys: set[str], path: Path) -> None:
    for name in PLACEHOLDER_PATTERN.findall(template):
        if name not in valid_keys:
            raise CategorySpecError(f"{path}: unknown placeholder {{{name}}}")
