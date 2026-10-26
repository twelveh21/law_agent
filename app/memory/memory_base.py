"""Shared models, configuration, storage, and scoring helpers for memory types."""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.common.path import PROJECT_ROOT


MemoryTypeName = Literal["working", "episodic", "semantic", "perceptual"]


class MemoryConfig(BaseModel):
    """Settings shared by the memory manager and its four memory stores."""

    working_memory_capacity: int = Field(default=50, gt=0)
    working_memory_ttl: int = Field(default=60, gt=0, description="工作记忆 TTL，单位分钟")
    persistent_memory_capacity: int = Field(default=1000, gt=0)
    database_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv(
                "MEMORY_DATABASE_PATH", str(PROJECT_ROOT / "db" / "memory.db")
            )
        ).expanduser()
    )


class MemoryItem(BaseModel):
    """One normalized memory record, regardless of its storage type."""

    id: str
    user_id: str = "default_user"
    content: str
    memory_type: MemoryTypeName
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Set on a returned copy only; it is not persisted as part of the memory.
    score: float = Field(default=0.0, exclude=True)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        raise TypeError("timestamp 必须是 datetime 或 ISO 格式字符串")


class SQLiteMemoryStore:
    """Small local persistent store shared by episodic/semantic/perceptual memory."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_owner_type "
                    "ON memory_items(user_id, memory_type)"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, item: MemoryItem) -> str:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """INSERT OR REPLACE INTO memory_items
                   (id, user_id, memory_type, content, importance, timestamp, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.id,
                        item.user_id,
                        item.memory_type,
                        item.content,
                        item.importance,
                        item.timestamp.isoformat(),
                        json.dumps(item.metadata, ensure_ascii=False, default=str),
                    ),
                )
        return item.id

    def list(self, user_id: str, memory_type: str) -> list[MemoryItem]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM memory_items WHERE user_id=? AND memory_type=?",
                (user_id, memory_type),
            ).fetchall()
        return [
            MemoryItem(
                id=row["id"],
                user_id=row["user_id"],
                memory_type=row["memory_type"],
                content=row["content"],
                importance=row["importance"],
                timestamp=row["timestamp"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def delete_ids(self, user_id: str, memory_type: str, ids: list[str]) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    f"DELETE FROM memory_items WHERE user_id=? AND memory_type=? "
                    f"AND id IN ({placeholders})",
                    [user_id, memory_type, *ids],
                )
                return cursor.rowcount


_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Tokenize English words and Chinese character bigrams for a local baseline."""
    tokens: list[str] = []
    for segment in _TOKEN_PATTERN.findall(text.lower()):
        if "\u4e00" <= segment[0] <= "\u9fff":
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        else:
            tokens.append(segment)
    return tokens


def tfidf_scores(query: str, items: list[MemoryItem]) -> dict[str, float]:
    """Compute cosine TF-IDF similarities without requiring a model/API service."""
    query_terms = tokenize(query)
    if not query_terms or not items:
        return {}

    documents = [tokenize(item.content) for item in items]
    document_frequency: dict[str, int] = {}
    for terms in documents:
        for term in set(terms):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    document_count = len(documents)

    def vector(terms: list[str]) -> dict[str, float]:
        counts: dict[str, int] = {}
        for term in terms:
            counts[term] = counts.get(term, 0) + 1
        total = max(len(terms), 1)
        return {
            term: (count / total)
            * (math.log((document_count + 1) / (document_frequency.get(term, 0) + 1)) + 1)
            for term, count in counts.items()
        }

    query_vector = vector(query_terms)
    query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
    scores: dict[str, float] = {}
    for item, terms in zip(items, documents):
        doc_vector = vector(terms)
        doc_norm = math.sqrt(sum(value * value for value in doc_vector.values()))
        dot_product = sum(
            weight * doc_vector.get(term, 0.0)
            for term, weight in query_vector.items()
        )
        scores[item.id] = (
            dot_product / (query_norm * doc_norm)
            if query_norm and doc_norm
            else 0.0
        )
    return scores


def keyword_score(query: str, content: str) -> float:
    """Fraction of distinct query terms found in a memory's token set."""
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.0
    content_terms = set(tokenize(content))
    return len(query_terms & content_terms) / len(query_terms)


def recency_score(timestamp: datetime, now: datetime | None = None) -> float:
    """Exponential time-nearness score, with a small non-zero floor."""
    current_time = now or datetime.now()
    age_hours = max((current_time - timestamp).total_seconds() / 3600, 0.0)
    return max(0.1, math.exp(-0.1 * age_hours / 24))


def importance_weight(importance: float) -> float:
    """Map importance in [0, 1] to a modest multiplier in [0.8, 1.2]."""
    return 0.8 + (importance * 0.4)


def cutoff_time(max_age_days: int) -> datetime:
    if max_age_days < 0:
        raise ValueError("max_age_days 不能小于 0")
    return datetime.now() - timedelta(days=max_age_days)
