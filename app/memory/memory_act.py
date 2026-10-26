"""Concrete memory types, their manager, and the Agent-facing memory tool."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.memory.memory_base import (
    MemoryConfig,
    MemoryItem,
    SQLiteMemoryStore,
    cutoff_time,
    importance_weight,
    keyword_score,
    recency_score,
    tfidf_scores,
)
from app.tool.tool_base import Tool, ToolParameter


class WorkingMemory:
    """Short-lived in-process memory with TTL and capacity management."""

    memory_type = "working"

    def __init__(self, config: MemoryConfig) -> None:
        self.max_capacity = config.working_memory_capacity
        self.max_age_minutes = config.working_memory_ttl
        self.memories: dict[str, MemoryItem] = {}

    def _expire_old_memories(self) -> None:
        cutoff = datetime.now() - timedelta(minutes=self.max_age_minutes)
        expired_ids = [
            memory_id
            for memory_id, item in self.memories.items()
            if item.timestamp < cutoff
        ]
        for memory_id in expired_ids:
            del self.memories[memory_id]

    def add(self, item: MemoryItem) -> str:
        self._expire_old_memories()
        if item.id not in self.memories and len(self.memories) >= self.max_capacity:
            lowest_priority = min(
                self.memories.values(),
                key=lambda memory: memory.importance * recency_score(memory.timestamp),
            )
            del self.memories[lowest_priority.id]
        self.memories[item.id] = item
        return item.id

    def retrieve(self, query: str, limit: int = 5, **_: Any) -> list[tuple[float, MemoryItem]]:
        self._expire_old_memories()
        items = list(self.memories.values())
        vector_scores = tfidf_scores(query, items)
        results: list[tuple[float, MemoryItem]] = []
        for item in items:
            vector_score = vector_scores.get(item.id, 0.0)
            words_score = keyword_score(query, item.content)
            relevance = (
                vector_score * 0.7 + words_score * 0.3
                if vector_score > 0
                else words_score
            )
            score = relevance * recency_score(item.timestamp) * importance_weight(item.importance)
            if score > 0:
                results.append((score, item.model_copy(update={"score": score})))
        results.sort(key=lambda result: result[0], reverse=True)
        return results[:limit]

    def delete_ids(self, ids: list[str]) -> int:
        deleted = 0
        for memory_id in ids:
            if memory_id in self.memories:
                del self.memories[memory_id]
                deleted += 1
        return deleted

    def list_items(self) -> list[MemoryItem]:
        self._expire_old_memories()
        return list(self.memories.values())


class PersistentMemory:
    """Shared SQLite CRUD implementation for persistent memory types."""

    memory_type = ""

    def __init__(self, config: MemoryConfig, store: SQLiteMemoryStore) -> None:
        self.config = config
        self.store = store

    def add(self, item: MemoryItem) -> str:
        return self.store.add(item)

    def list_items(self, user_id: str) -> list[MemoryItem]:
        return self.store.list(user_id, self.memory_type)

    def delete_ids(self, user_id: str, ids: list[str]) -> int:
        return self.store.delete_ids(user_id, self.memory_type, ids)


class EpisodicMemory(PersistentMemory):
    """Persistent event/experience memory, ranked by meaning, recency, importance."""

    memory_type = "episodic"

    def retrieve(
        self, query: str, limit: int, user_id: str, **_: Any
    ) -> list[tuple[float, MemoryItem]]:
        items = self.list_items(user_id)
        similarities = tfidf_scores(query, items)
        results = []
        for item in items:
            similarity = similarities.get(item.id, 0.0)
            if similarity <= 0:
                continue
            relevance = similarity * 0.8 + recency_score(item.timestamp) * 0.2
            score = relevance * importance_weight(item.importance)
            results.append((score, item.model_copy(update={"score": score})))
        results.sort(key=lambda result: result[0], reverse=True)
        return results[:limit]


class SemanticMemory(PersistentMemory):
    """Persistent facts/concepts with vector-like text and lightweight graph signals."""

    memory_type = "semantic"

    @staticmethod
    def _graph_score(query: str, item: MemoryItem) -> float:
        """Match query terms against entity/relation labels supplied in metadata.

        This is a local graph-search baseline, not a Neo4j knowledge graph. The
        metadata format is intentionally compatible with a future graph backend.
        """
        graph_labels: list[str] = []
        for key in ("entities", "relations"):
            labels = item.metadata.get(key, [])
            if isinstance(labels, str):
                labels = [labels]
            if isinstance(labels, list):
                graph_labels.extend(str(label) for label in labels)
        labels_text = " ".join(str(label) for label in graph_labels)
        return keyword_score(query, labels_text) if labels_text else 0.0

    def retrieve(
        self, query: str, limit: int, user_id: str, **_: Any
    ) -> list[tuple[float, MemoryItem]]:
        items = self.list_items(user_id)
        similarities = tfidf_scores(query, items)
        results = []
        for item in items:
            vector_score = similarities.get(item.id, 0.0)
            graph_score = self._graph_score(query, item)
            relevance = vector_score * 0.7 + graph_score * 0.3
            score = relevance * importance_weight(item.importance)
            if score > 0:
                results.append((score, item.model_copy(update={"score": score})))
        results.sort(key=lambda result: result[0], reverse=True)
        return results[:limit]


class PerceptualMemory(PersistentMemory):
    """Persistent records for text/image/audio metadata and their descriptions."""

    memory_type = "perceptual"

    def retrieve(
        self,
        query: str,
        limit: int,
        user_id: str,
        modality: str | None = None,
        **_: Any,
    ) -> list[tuple[float, MemoryItem]]:
        items = self.list_items(user_id)
        if modality:
            items = [item for item in items if item.metadata.get("modality") == modality]
        similarities = tfidf_scores(query, items)
        results = []
        for item in items:
            similarity = similarities.get(item.id, 0.0)
            if similarity <= 0:
                continue
            relevance = similarity * 0.8 + recency_score(item.timestamp) * 0.2
            score = relevance * importance_weight(item.importance)
            results.append((score, item.model_copy(update={"score": score})))
        results.sort(key=lambda result: result[0], reverse=True)
        return results[:limit]


class MemoryManager:
    """Route memory operations to enabled memory types and merge search results."""

    SUPPORTED_TYPES = {"working", "episodic", "semantic", "perceptual"}

    def __init__(
        self,
        config: MemoryConfig | None = None,
        user_id: str = "default_user",
        enable_working: bool = True,
        enable_episodic: bool = True,
        enable_semantic: bool = True,
        enable_perceptual: bool = True,
    ) -> None:
        self.config = config or MemoryConfig()
        self.user_id = user_id
        self.memory_types: dict[str, Any] = {}
        shared_store = SQLiteMemoryStore(self.config.database_path)
        if enable_working:
            self.memory_types["working"] = WorkingMemory(self.config)
        if enable_episodic:
            self.memory_types["episodic"] = EpisodicMemory(self.config, shared_store)
        if enable_semantic:
            self.memory_types["semantic"] = SemanticMemory(self.config, shared_store)
        if enable_perceptual:
            self.memory_types["perceptual"] = PerceptualMemory(self.config, shared_store)

    def add_memory(
        self,
        content: str,
        memory_type: str = "working",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        auto_classify: bool = False,
        **_: Any,
    ) -> str:
        del auto_classify  # Explicit type selection is more predictable for this project.
        if memory_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"不支持的记忆类型: {memory_type}")
        if memory_type not in self.memory_types:
            raise ValueError(f"记忆类型 {memory_type} 未启用")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content 不能为空")
        item = MemoryItem(
            id=uuid.uuid4().hex,
            user_id=self.user_id,
            content=content.strip(),
            memory_type=memory_type,
            importance=importance,
            timestamp=(metadata or {}).get("timestamp", datetime.now()),
            metadata=metadata or {},
        )
        return self.memory_types[memory_type].add(item)

    def retrieve_memories(
        self,
        query: str,
        limit: int = 5,
        memory_types: list[str] | None = None,
        min_importance: float = 0.1,
        **filters: Any,
    ) -> list[MemoryItem]:
        if not query or not query.strip():
            raise ValueError("query 不能为空")
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        if not 0 <= min_importance <= 1:
            raise ValueError("min_importance 必须在 0 到 1 之间")
        selected_types = memory_types or list(self.memory_types)
        unknown_types = set(selected_types) - self.SUPPORTED_TYPES
        if unknown_types:
            raise ValueError(f"不支持的记忆类型: {', '.join(sorted(unknown_types))}")

        scored: list[tuple[float, MemoryItem]] = []
        for memory_type in selected_types:
            memory_backend = self.memory_types.get(memory_type)
            if memory_backend is None:
                continue
            scored.extend(
                memory_backend.retrieve(
                    query=query,
                    limit=limit,
                    user_id=self.user_id,
                    **filters,
                )
            )
        scored = [
            (score, item)
            for score, item in scored
            if item.importance >= min_importance
        ]
        scored.sort(key=lambda result: result[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def get_summary(self) -> dict[str, Any]:
        counts = {
            memory_type: len(backend.list_items(self.user_id) if memory_type != "working" else backend.list_items())
            for memory_type, backend in self.memory_types.items()
        }
        return {"user_id": self.user_id, "total": sum(counts.values()), "by_type": counts}

    def clear_memories(self) -> int:
        """Delete all enabled memories owned by this manager's user_id."""
        deleted_total = 0
        for memory_type, backend in self.memory_types.items():
            # Persistent stores require the owner key; working memory is local to this instance.
            items = backend.list_items(self.user_id) if memory_type != "working" else backend.list_items()
            memory_ids = [item.id for item in items]
            if memory_type == "working":
                deleted_total += backend.delete_ids(memory_ids)
            else:
                deleted_total += backend.delete_ids(self.user_id, memory_ids)
        return deleted_total

    def forget_memories(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
        max_capacity: int | None = None,
    ) -> int:
        """Delete memories by importance, age, or capacity; return deleted count."""
        if strategy not in {"importance_based", "time_based", "capacity_based"}:
            raise ValueError("strategy 必须是 importance_based、time_based 或 capacity_based")
        if not 0 <= threshold <= 1:
            raise ValueError("threshold 必须在 0 到 1 之间")

        deleted_total = 0
        for memory_type, backend in self.memory_types.items():
            items = backend.list_items(self.user_id) if memory_type != "working" else backend.list_items()
            if strategy == "importance_based":
                delete_items = [item for item in items if item.importance < threshold]
            elif strategy == "time_based":
                cutoff = cutoff_time(max_age_days)
                delete_items = [item for item in items if item.timestamp < cutoff]
            else:
                capacity = max_capacity or (
                    self.config.working_memory_capacity
                    if memory_type == "working"
                    else self.config.persistent_memory_capacity
                )
                if capacity <= 0:
                    raise ValueError("max_capacity 必须大于 0")
                keep = sorted(
                    items,
                    key=lambda item: item.importance * recency_score(item.timestamp),
                    reverse=True,
                )[:capacity]
                keep_ids = {item.id for item in keep}
                delete_items = [item for item in items if item.id not in keep_ids]
            deleted_total += backend.delete_ids([item.id for item in delete_items]) if memory_type == "working" else backend.delete_ids(self.user_id, [item.id for item in delete_items])
        return deleted_total


class MemoryTool(Tool):
    """Agent-facing adapter exposing add/search/summary/forget memory actions."""

    def __init__(
        self,
        user_id: str = "default_user",
        memory_config: MemoryConfig | None = None,
        memory_types: list[str] | None = None,
        session_id: str | None = None,
    ) -> None:
        super().__init__(
            name="memory",
            description="添加、搜索、统计或清理当前用户的记忆",
        )
        self.memory_config = memory_config or MemoryConfig()
        self.memory_types = memory_types or ["working", "episodic", "semantic", "perceptual"]
        invalid_types = set(self.memory_types) - MemoryManager.SUPPORTED_TYPES
        if invalid_types:
            raise ValueError(f"不支持的记忆类型: {', '.join(sorted(invalid_types))}")
        self.current_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        enabled = set(self.memory_types)
        self.memory_manager = MemoryManager(
            config=self.memory_config,
            user_id=user_id,
            enable_working="working" in enabled,
            enable_episodic="episodic" in enabled,
            enable_semantic="semantic" in enabled,
            enable_perceptual="perceptual" in enabled,
        )

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="action", type="string", description="操作：add/search/summary/forget"),
            ToolParameter(name="content", type="string", description="要保存的记忆内容", required=False),
            ToolParameter(name="memory_type", type="string", description="working/episodic/semantic/perceptual", required=False, default="working"),
            ToolParameter(name="importance", type="number", description="记忆重要性，0 到 1", required=False, default=0.5),
            ToolParameter(name="query", type="string", description="搜索关键词或问题", required=False),
            ToolParameter(name="limit", type="integer", description="最多返回条数", required=False, default=5),
            ToolParameter(name="memory_types", type="array", description="限定检索记忆类型", required=False),
            ToolParameter(name="min_importance", type="number", description="最低重要性过滤值", required=False, default=0.1),
            ToolParameter(name="file_path", type="string", description="图片或音频等文件路径（感知记忆）", required=False),
            ToolParameter(name="modality", type="string", description="text/image/audio 等模态", required=False),
            ToolParameter(name="strategy", type="string", description="遗忘策略：importance_based/time_based/capacity_based", required=False, default="importance_based"),
            ToolParameter(name="threshold", type="number", description="重要性遗忘阈值", required=False, default=0.1),
            ToolParameter(name="max_age_days", type="integer", description="时间遗忘的天数阈值", required=False, default=30),
        ]

    def run(self, parameters: dict[str, Any]) -> str:
        if not isinstance(parameters, dict):
            raise TypeError("MemoryTool.run 的参数必须是字典")
        action = parameters.get("action")
        try:
            if action == "add":
                return self._add_memory(**parameters)
            if action == "search":
                return self._search_memory(**parameters)
            if action == "summary":
                summary = self.memory_manager.get_summary()
                lines = [f"记忆总数：{summary['total']}"]
                labels = {"working": "工作", "episodic": "情景", "semantic": "语义", "perceptual": "感知"}
                lines.extend(f"{labels.get(name, name)}记忆：{count} 条" for name, count in summary["by_type"].items())
                return "\n".join(lines)
            if action == "forget":
                return self._forget(**parameters)
            if action not in {"add", "search", "summary", "forget"}:
                return "操作无效。请使用 add、search、summary 或 forget。"
        except (TypeError, ValueError) as exc:
            return f"记忆操作失败：{exc}"
        except Exception as exc:
            return f"记忆操作失败：{type(exc).__name__}: {exc}"
        return "记忆操作失败：未知错误"

    def _add_memory(
        self,
        action: str | None = None,
        content: str = "",
        memory_type: str = "working",
        importance: float = 0.5,
        file_path: str | None = None,
        modality: str | None = None,
        **metadata: Any,
    ) -> str:
        del action  # run() passes the dispatch field through keyword arguments.
        if memory_type == "perceptual" and file_path:
            modality = modality or self._infer_modality(file_path)
            metadata.setdefault("raw_data", str(Path(file_path)))
        if memory_type == "perceptual" and not content.strip() and file_path:
            content = Path(file_path).name
        metadata.setdefault("session_id", self.current_session_id)
        metadata.setdefault("timestamp", datetime.now().isoformat())
        memory_id = self.memory_manager.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata={**metadata, **({"modality": modality} if modality else {})},
        )
        return f"记忆已添加，类型：{memory_type}，ID：{memory_id}"

    def _search_memory(
        self,
        query: str,
        limit: int = 5,
        memory_types: list[str] | None = None,
        memory_type: str | None = None,
        min_importance: float = 0.1,
        modality: str | None = None,
        **_: Any,
    ) -> str:
        if memory_type and not memory_types:
            memory_types = [memory_type]
        results = self.memory_manager.retrieve_memories(
            query=query,
            limit=limit,
            memory_types=memory_types,
            min_importance=min_importance,
            modality=modality,
        )
        if not results:
            return f"未找到与“{query}”相关的记忆。"
        labels = {"working": "工作", "episodic": "情景", "semantic": "语义", "perceptual": "感知"}
        lines = [f"找到 {len(results)} 条相关记忆："]
        for index, item in enumerate(results, start=1):
            preview = item.content[:120] + ("…" if len(item.content) > 120 else "")
            lines.append(
                f"{index}. [{labels.get(item.memory_type, item.memory_type)}记忆] "
                f"{preview}（相关分数：{item.score:.3f}，重要性：{item.importance:.2f}）"
            )
        return "\n".join(lines)

    def _forget(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
        max_capacity: int | None = None,
        **_: Any,
    ) -> str:
        count = self.memory_manager.forget_memories(
            strategy=strategy,
            threshold=threshold,
            max_age_days=max_age_days,
            max_capacity=max_capacity,
        )
        return f"已遗忘 {count} 条记忆（策略：{strategy}）。"

    @staticmethod
    def _infer_modality(file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
            return "image"
        if suffix in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            return "audio"
        return "text"
