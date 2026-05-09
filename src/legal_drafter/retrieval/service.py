from __future__ import annotations

from datetime import date

from legal_drafter.index import SQLiteIndex, build_match_query
from legal_drafter.models import AuthorityHit, AuthorityKind, Citation, RetrievalQuery
from legal_drafter.topic_profiles import get_document_authority_keywords, get_topic_profile

AUTHORITY_WEIGHT = {
    AuthorityKind.LAW: 1.0,
    AuthorityKind.ENFORCEMENT_DECREE: 0.85,
    AuthorityKind.ENFORCEMENT_RULE: 0.75,
}


def retrieve_authority_hits(query: RetrievalQuery) -> list[AuthorityHit]:
    index = SQLiteIndex(query.index_path)
    query_texts = (query.text, *query.search_queries, *query.authority_keywords)
    candidate_limit = max(query.top_k * 5, query.top_k)
    match_query = build_match_query(query_texts)
    candidate_rows = index.fetch_search_candidates(
        match_query=match_query,
        limit=candidate_limit,
        effective_only=query.effective_only,
    )
    if query.authority_keywords:
        candidate_rows = _merge_candidate_rows(
            candidate_rows,
            index.fetch_authority_name_candidates(
                query.authority_keywords,
                limit=candidate_limit,
                effective_only=query.effective_only,
            ),
        )
    candidate_rows = _filter_candidate_rows(candidate_rows, query)
    hits: list[AuthorityHit] = []
    lowered_queries = " ".join(query_texts).lower()
    tokens = {token for token in lowered_queries.split() if token}
    authority_keywords = tuple(keyword.lower() for keyword in query.authority_keywords)

    for row in candidate_rows:
        authority_kind = AuthorityKind(row["authority_kind"])
        authority_name = row["authority_name"]
        article_title = row["article_title"]
        body = row["body"]
        excerpt = (row["excerpt"] or body[:160]).strip()
        citation = Citation(
            authority_id=row["authority_id"],
            authority_name=authority_name,
            authority_kind=authority_kind,
            article_number=row["article_number"],
            article_title=article_title,
            excerpt=excerpt,
            effective_date=row["effective_date"],
            detail_url=row["detail_url"],
        )
        title_haystack = " ".join(filter(None, [authority_name, article_title])).lower()
        body_haystack = body.lower()
        title_bonus = 0.2 if any(token in title_haystack for token in tokens) else 0.0
        body_bonus = 0.1 if any(token in body_haystack for token in tokens) else 0.0
        effective_bonus = 0.1 if _is_effective(row["effective_date"]) else 0.0
        authority_bonus = 0.35 if authority_keywords and any(keyword in authority_name.lower() for keyword in authority_keywords) else 0.0
        bm25_component = 1.0 / (1.0 + abs(float(row["bm25_score"])))
        score = bm25_component + AUTHORITY_WEIGHT[authority_kind] + title_bonus + body_bonus + effective_bonus + authority_bonus
        hits.append(
            AuthorityHit(
                authority_id=row["authority_id"],
                authority_name=authority_name,
                authority_kind=authority_kind,
                article_id=row["article_id"],
                article_number=row["article_number"],
                article_title=article_title,
                excerpt=excerpt,
                effective_date=row["effective_date"],
                score=score,
                citation=citation,
            )
        )

    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits[: query.top_k]


def _filter_candidate_rows(candidate_rows, query: RetrievalQuery):
    rows = list(candidate_rows)
    if query.service_topic is not None:
        rows = _filter_by_authority_keywords(rows, get_topic_profile(query.service_topic).authority_keywords)
    document_rows = _filter_by_authority_keywords(rows, get_document_authority_keywords(query.document_kind))
    if document_rows:
        rows = document_rows
    section_rows = _filter_by_authority_keywords(rows, query.authority_keywords)
    if section_rows:
        rows = section_rows
    return rows


def _merge_candidate_rows(*row_groups):
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


def _filter_by_authority_keywords(rows, keywords: tuple[str, ...]):
    if not keywords:
        return list(rows)
    lowered = tuple(keyword.lower() for keyword in keywords)
    return [
        row
        for row in rows
        if any(keyword in row["authority_name"].lower() for keyword in lowered)
    ]


def _is_effective(effective_date: str | None) -> bool:
    if not effective_date:
        return True
    try:
        return date.fromisoformat(effective_date) <= date.today()
    except ValueError:
        return False
