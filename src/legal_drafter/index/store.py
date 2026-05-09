from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal_drafter.exceptions import IndexNotFoundError
from legal_drafter.models import IndexStats

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS authority (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    authority_kind TEXT NOT NULL,
    promulgation_number TEXT,
    promulgation_date TEXT,
    effective_date TEXT,
    detail_url TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article (
    id TEXT PRIMARY KEY,
    authority_id TEXT NOT NULL REFERENCES authority(id) ON DELETE CASCADE,
    article_number TEXT NOT NULL,
    article_title TEXT,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS article_search USING fts5(
    authority_id UNINDEXED,
    article_id UNINDEXED,
    authority_name,
    title,
    body
);

CREATE TABLE IF NOT EXISTS index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SQLiteIndex:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    @contextmanager
    def connection(self) -> Iterable[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            conn.close()

    def initialize(self, rebuild: bool = False) -> None:
        if rebuild and self.db_path.exists():
            self.db_path.unlink()
        with self.connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def require_ready(self) -> None:
        if not self.db_path.exists():
            raise IndexNotFoundError(f"index not found at {self.db_path}")
        with self.connection() as conn:
            exists = conn.execute(
                "SELECT COUNT(*) AS count FROM sqlite_master WHERE type='table' AND name='article'"
            ).fetchone()["count"]
            if not exists:
                raise IndexNotFoundError(f"index schema missing at {self.db_path}")
            article_count = conn.execute("SELECT COUNT(*) AS count FROM article").fetchone()["count"]
            if article_count <= 0:
                raise IndexNotFoundError(f"index contains no articles at {self.db_path}")

    def replace_authority_articles(self, authority: Any, articles: Iterable[Any]) -> None:
        article_rows = list(articles)
        updated_at = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO authority (
                    id, name, authority_kind, promulgation_number, promulgation_date,
                    effective_date, detail_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    authority_kind = excluded.authority_kind,
                    promulgation_number = excluded.promulgation_number,
                    promulgation_date = excluded.promulgation_date,
                    effective_date = excluded.effective_date,
                    detail_url = excluded.detail_url,
                    updated_at = excluded.updated_at
                """,
                (
                    authority.authority_id,
                    authority.name,
                    authority.authority_kind.value,
                    authority.promulgation_number,
                    authority.promulgation_date,
                    authority.effective_date,
                    authority.detail_url,
                    updated_at,
                ),
            )
            conn.execute("DELETE FROM article_search WHERE authority_id = ?", (authority.authority_id,))
            conn.execute("DELETE FROM article WHERE authority_id = ?", (authority.authority_id,))
            for article in article_rows:
                conn.execute(
                    """
                    INSERT INTO article (id, authority_id, article_number, article_title, body, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.article_id,
                        authority.authority_id,
                        article.article_number,
                        article.article_title,
                        article.body,
                        updated_at,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO article_search (authority_id, article_id, authority_name, title, body)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        authority.authority_id,
                        article.article_id,
                        authority.name,
                        article.article_title or "",
                        article.body,
                    ),
                )
            conn.commit()

    def set_snapshot_at(self, snapshot_at: datetime) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO index_metadata (key, value)
                VALUES ('snapshot_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (snapshot_at.isoformat(),),
            )
            conn.commit()

    def get_stats(self) -> IndexStats:
        if not self.db_path.exists():
            return IndexStats(authority_count=0, article_count=0, snapshot_at=None)
        with self.connection() as conn:
            authority_count = conn.execute("SELECT COUNT(*) AS count FROM authority").fetchone()["count"]
            article_count = conn.execute("SELECT COUNT(*) AS count FROM article").fetchone()["count"]
            row = conn.execute(
                "SELECT value FROM index_metadata WHERE key = 'snapshot_at'"
            ).fetchone()
        snapshot_at = datetime.fromisoformat(row["value"]) if row else None
        return IndexStats(
            authority_count=authority_count,
            article_count=article_count,
            snapshot_at=snapshot_at,
        )

    def fetch_search_candidates(
        self,
        match_query: str,
        limit: int,
        effective_only: bool,
    ) -> list[sqlite3.Row]:
        self.require_ready()
        sql = """
        SELECT
            a.id AS authority_id,
            a.name AS authority_name,
            a.authority_kind AS authority_kind,
            a.effective_date AS effective_date,
            a.detail_url AS detail_url,
            ar.id AS article_id,
            ar.article_number AS article_number,
            ar.article_title AS article_title,
            ar.body AS body,
            snippet(article_search, 4, '', '', ' ... ', 18) AS excerpt,
            bm25(article_search) AS bm25_score
        FROM article_search
        JOIN article ar ON ar.id = article_search.article_id
        JOIN authority a ON a.id = ar.authority_id
        WHERE article_search MATCH ?
        """
        parameters: list[Any] = [match_query]
        if effective_only:
            sql += " AND (a.effective_date IS NULL OR a.effective_date <= ?)"
            parameters.append(datetime.now(UTC).date().isoformat())
        sql += " ORDER BY bm25(article_search) ASC LIMIT ?"
        parameters.append(limit)
        with self.connection() as conn:
            rows = conn.execute(sql, tuple(parameters)).fetchall()
        return rows

    def fetch_authority_name_candidates(
        self,
        authority_keywords: Iterable[str],
        limit: int,
        effective_only: bool,
    ) -> list[sqlite3.Row]:
        keywords = tuple(keyword.strip() for keyword in authority_keywords if keyword and keyword.strip())
        if not keywords:
            return []
        self.require_ready()
        clauses = " OR ".join("a.name LIKE ?" for _ in keywords)
        sql = f"""
        SELECT
            a.id AS authority_id,
            a.name AS authority_name,
            a.authority_kind AS authority_kind,
            a.effective_date AS effective_date,
            a.detail_url AS detail_url,
            ar.id AS article_id,
            ar.article_number AS article_number,
            ar.article_title AS article_title,
            ar.body AS body,
            substr(ar.body, 1, 180) AS excerpt,
            0.0 AS bm25_score
        FROM authority a
        JOIN article ar ON ar.authority_id = a.id
        WHERE ({clauses})
        """
        parameters: list[Any] = [f"%{keyword}%" for keyword in keywords]
        if effective_only:
            sql += " AND (a.effective_date IS NULL OR a.effective_date <= ?)"
            parameters.append(datetime.now(UTC).date().isoformat())
        sql += " ORDER BY a.name ASC, ar.article_number ASC LIMIT ?"
        parameters.append(limit)
        with self.connection() as conn:
            rows = conn.execute(sql, tuple(parameters)).fetchall()
        return rows

    def fetch_articles_by_ids(self, article_ids: Iterable[str]) -> list[sqlite3.Row]:
        identifiers = tuple(str(article_id).strip() for article_id in article_ids if str(article_id).strip())
        if not identifiers:
            return []
        self.require_ready()
        placeholders = ", ".join("?" for _ in identifiers)
        sql = f"""
        SELECT
            a.id AS authority_id,
            a.name AS authority_name,
            a.authority_kind AS authority_kind,
            a.effective_date AS effective_date,
            a.detail_url AS detail_url,
            ar.id AS article_id,
            ar.article_number AS article_number,
            ar.article_title AS article_title,
            ar.body AS body,
            substr(ar.body, 1, 180) AS excerpt,
            0.0 AS bm25_score
        FROM article ar
        JOIN authority a ON a.id = ar.authority_id
        WHERE ar.id IN ({placeholders})
        ORDER BY a.name ASC, ar.article_number ASC
        """
        with self.connection() as conn:
            return conn.execute(sql, identifiers).fetchall()

    def fetch_articles_by_authority_ids(
        self,
        authority_ids: Iterable[str],
        *,
        limit_per_authority: int = 3,
    ) -> list[sqlite3.Row]:
        identifiers = tuple(str(authority_id).strip() for authority_id in authority_ids if str(authority_id).strip())
        if not identifiers:
            return []
        self.require_ready()
        rows: list[sqlite3.Row] = []
        sql = """
        SELECT
            a.id AS authority_id,
            a.name AS authority_name,
            a.authority_kind AS authority_kind,
            a.effective_date AS effective_date,
            a.detail_url AS detail_url,
            ar.id AS article_id,
            ar.article_number AS article_number,
            ar.article_title AS article_title,
            ar.body AS body,
            substr(ar.body, 1, 180) AS excerpt,
            0.0 AS bm25_score
        FROM article ar
        JOIN authority a ON a.id = ar.authority_id
        WHERE ar.authority_id = ?
        ORDER BY ar.article_number ASC
        LIMIT ?
        """
        with self.connection() as conn:
            for authority_id in identifiers:
                rows.extend(conn.execute(sql, (authority_id, limit_per_authority)).fetchall())
        return rows


def build_match_query(query_texts: Iterable[str]) -> str:
    phrases: list[str] = []
    seen: set[str] = set()
    for text in query_texts:
        cleaned = " ".join(text.replace('"', " ").split())
        if not cleaned:
            continue
        parts = [part for part in cleaned.split() if part]
        candidates = parts if parts else [cleaned]
        if len(parts) > 1:
            candidates.append(cleaned)
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            phrases.append(f'"{candidate}"')
    if not phrases:
        raise ValueError("at least one search query is required")
    return " OR ".join(phrases)
