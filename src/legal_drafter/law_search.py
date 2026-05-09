from __future__ import annotations

from legal_drafter.catalog import get_category_spec
from legal_drafter.index import SQLiteIndex, build_match_query
from legal_drafter.models import AuthorityKind, LawSearchHit, LawSearchQuery
from legal_drafter.retrieval.service import AUTHORITY_WEIGHT


def search_laws(query: LawSearchQuery) -> tuple[LawSearchHit, ...]:
    index = SQLiteIndex(query.index_path)
    spec = get_category_spec(query.category_id) if query.category_id else None
    seed_keywords = spec.seed_authority_keywords if spec is not None else ()
    query_texts = tuple(part for part in (query.text, *seed_keywords) if part)
    if not query_texts:
        raise ValueError("law search requires either text or category_id")

    match_query = build_match_query(query_texts)
    candidate_limit = max(query.top_k * 4, query.top_k)
    candidate_rows = index.fetch_search_candidates(
        match_query=match_query,
        limit=candidate_limit,
        effective_only=query.effective_only,
    )
    if seed_keywords:
        candidate_rows = _merge_rows(
            candidate_rows,
            index.fetch_authority_name_candidates(
                seed_keywords,
                limit=candidate_limit,
                effective_only=query.effective_only,
            ),
        )

    hits: list[LawSearchHit] = []
    lowered_text = (query.text or "").lower()
    text_tokens = {token for token in lowered_text.split() if token}
    lowered_seed_keywords = tuple(keyword.lower() for keyword in seed_keywords)
    for row in candidate_rows:
        authority_kind = AuthorityKind(row["authority_kind"])
        authority_name = row["authority_name"]
        article_title = row["article_title"] or ""
        body = row["body"]
        excerpt = (row["excerpt"] or body[:180]).strip()
        title_haystack = f"{authority_name} {article_title}".lower()
        body_haystack = body.lower()
        title_bonus = 0.25 if text_tokens and any(token in title_haystack for token in text_tokens) else 0.0
        body_bonus = 0.12 if text_tokens and any(token in body_haystack for token in text_tokens) else 0.0
        seed_bonus = 0.3 if lowered_seed_keywords and any(keyword in authority_name.lower() for keyword in lowered_seed_keywords) else 0.0
        bm25_component = 1.0 / (1.0 + abs(float(row["bm25_score"])))
        score = bm25_component + AUTHORITY_WEIGHT[authority_kind] + title_bonus + body_bonus + seed_bonus
        hits.append(
            LawSearchHit(
                authority_id=row["authority_id"],
                authority_name=authority_name,
                authority_kind=authority_kind,
                article_id=row["article_id"],
                article_number=row["article_number"],
                article_title=row["article_title"],
                excerpt=excerpt,
                effective_date=row["effective_date"],
                detail_url=row["detail_url"],
                score=score,
                matched_seed=seed_bonus > 0,
            )
        )

    hits.sort(key=lambda item: item.score, reverse=True)
    return tuple(hits[: query.top_k])


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
