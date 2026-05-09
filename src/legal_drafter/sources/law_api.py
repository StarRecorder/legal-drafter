from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from legal_drafter.exceptions import IndexRefreshError, SourceFetchError
from legal_drafter.index import SQLiteIndex
from legal_drafter.models import AuthorityKind, IndexStats, SourceConfig
from legal_drafter.topic_profiles import get_topic_profile


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    authority_id: str
    name: str
    authority_kind: AuthorityKind
    promulgation_number: str | None
    promulgation_date: str | None
    effective_date: str | None
    detail_url: str | None


@dataclass(frozen=True, slots=True)
class ArticleRecord:
    article_id: str
    article_number: str
    article_title: str | None
    body: str


class LawApiClient:
    def __init__(self, config: SourceConfig):
        self.config = config

    def list_authorities(self) -> list[AuthorityRecord]:
        results: list[AuthorityRecord] = []
        seen: set[str] = set()
        for source_query in _resolve_source_queries(self.config):
            page = 1
            while True:
                if self.config.max_pages is not None and page > self.config.max_pages:
                    break
                xml_text = self._get_xml(
                    "/DRF/lawSearch.do",
                    {
                        "OC": self.config.oc,
                        "target": self.config.list_target,
                        "type": "XML",
                        "display": self.config.page_size,
                        "page": page,
                        **({"query": source_query} if source_query else {}),
                    },
                )
                page_records = parse_law_list_xml(xml_text)
                if not page_records:
                    break
                for record in page_records:
                    if record.authority_id in seen:
                        continue
                    seen.add(record.authority_id)
                    results.append(record)
                if len(page_records) < self.config.page_size:
                    break
                page += 1
        return results

    def fetch_articles(self, authority: AuthorityRecord) -> list[ArticleRecord]:
        xml_text = self._get_xml(
            "/DRF/lawService.do",
            {
                "OC": self.config.oc,
                "target": self.config.body_target,
                "ID": authority.authority_id,
                "type": "XML",
            },
        )
        return parse_law_body_xml(xml_text, authority)

    def _get_xml(self, path: str, params: dict[str, object]) -> str:
        url = f"{self.config.base_url.rstrip('/')}{path}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "legal-drafter/0.1"})
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover
            raise SourceFetchError(f"failed to fetch legal source: {url}") from exc


def refresh_index_from_source(config: SourceConfig, rebuild: bool = False) -> IndexStats:
    client = LawApiClient(config)
    index = SQLiteIndex(config.index_path)
    index.initialize(rebuild=rebuild)
    try:
        authorities = client.list_authorities()
        for authority in authorities:
            articles = client.fetch_articles(authority)
            if not articles:
                continue
            index.replace_authority_articles(authority, articles)
        index.set_snapshot_at(datetime.now(UTC))
        return index.get_stats()
    except SourceFetchError as exc:
        raise IndexRefreshError(str(exc)) from exc


def parse_law_list_xml(xml_text: str) -> list[AuthorityRecord]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceFetchError("failed to parse law list XML") from exc

    results: list[AuthorityRecord] = []
    seen: set[str] = set()
    for node in root.iter():
        authority_id = _find_child_text(node, "법령ID")
        name = _find_child_text(node, "법령명한글")
        kind_text = _first_non_empty(node, "법종구분", "법령구분명")
        authority_kind = _map_authority_kind(kind_text)
        if not authority_id or not name or authority_kind is None or authority_id in seen:
            continue
        seen.add(authority_id)
        results.append(
            AuthorityRecord(
                authority_id=authority_id,
                name=name,
                authority_kind=authority_kind,
                promulgation_number=_find_child_text(node, "공포번호"),
                promulgation_date=_normalize_date(_find_child_text(node, "공포일자")),
                effective_date=_normalize_date(_find_child_text(node, "시행일자")),
                detail_url=_find_child_text(node, "법령상세링크"),
            )
        )
    return results


def parse_law_body_xml(xml_text: str, authority: AuthorityRecord) -> list[ArticleRecord]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SourceFetchError("failed to parse law body XML") from exc

    articles: list[ArticleRecord] = []
    seen: set[str] = set()
    for node in root.iter():
        raw_number = _first_non_empty(node, "조문번호", "조번호")
        if not raw_number:
            continue
        article_number = _normalize_article_number(raw_number)
        article_title = _first_non_empty(node, "조문제목", "조제목")
        body_chunks = _extract_body_chunks(node)
        body = "\n".join(body_chunks).strip()
        if not body:
            body = _collapse_text(node)
        if not body:
            continue
        article_id = f"{authority.authority_id}:{article_number}"
        if article_id in seen:
            continue
        seen.add(article_id)
        articles.append(
            ArticleRecord(
                article_id=article_id,
                article_number=article_number,
                article_title=article_title,
                body=body,
            )
        )
    return articles


def _extract_body_chunks(node: ET.Element) -> list[str]:
    chunks: list[str] = []
    for tag in ("조문내용", "항내용", "호내용", "목내용"):
        for child in node.findall(f".//{tag}"):
            text = _collapse_text(child)
            if text and text not in chunks:
                chunks.append(text)
    return chunks


def _collapse_text(node: ET.Element) -> str:
    text = " ".join(part.strip() for part in node.itertext() if part and part.strip())
    return " ".join(text.split())


def _find_child_text(node: ET.Element, tag: str) -> str | None:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text or None


def _first_non_empty(node: ET.Element, *tags: str) -> str | None:
    for tag in tags:
        value = _find_child_text(node, tag)
        if value:
            return value
    return None


def _map_authority_kind(value: str | None) -> AuthorityKind | None:
    if value is None:
        return None
    if value == "법률":
        return AuthorityKind.LAW
    if value == "대통령령":
        return AuthorityKind.ENFORCEMENT_DECREE
    if value in {"총리령", "부령"}:
        return AuthorityKind.ENFORCEMENT_RULE
    return None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().replace(".", "").replace("-", "")
    if len(cleaned) != 8 or not cleaned.isdigit():
        return value.strip()
    return f"{cleaned[0:4]}-{cleaned[4:6]}-{cleaned[6:8]}"


def _normalize_article_number(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("제") and cleaned.endswith("조"):
        return cleaned
    digits = "".join(char for char in cleaned if char.isdigit())
    if digits:
        return f"제{digits}조"
    return cleaned


def _resolve_source_queries(config: SourceConfig) -> tuple[str, ...]:
    if config.search_query:
        return (config.search_query,)
    return get_topic_profile(config.service_topic).source_queries
