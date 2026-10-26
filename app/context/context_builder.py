"""Framework-independent context construction for the legal Agent project.

The builder uses the GSSC flow: Gather, Select, Structure, Compress.  It does
not call an LLM or a LangChain agent; callers pass retrieved evidence as packets
and decide how to place the returned string into their framework's messages.
"""

from dataclasses import dataclass, field
from datetime import datetime
import math
import re
from typing import Any, Optional


@dataclass
class ContextPacket:
    """One candidate piece of information that may enter the model context."""

    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    relevance_score: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("ContextPacket.content 必须是字符串")
        if self.token_count < 0:
            raise ValueError("token_count 不能小于 0")
        self.relevance_score = max(0.0, min(1.0, float(self.relevance_score)))
        if self.token_count == 0:
            self.token_count = ContextBuilder.count_tokens(self.content)


@dataclass
class ContextConfig:
    """ContextBuilder settings; max_tokens is an approximate token budget."""

    max_tokens: int = 3000
    reserve_ratio: float = 0.2
    min_relevance: float = 0.05
    enable_compression: bool = True
    recency_weight: float = 0.3
    relevance_weight: float = 0.7
    max_history_messages: int = 10

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError("max_tokens 必须大于 0")
        if not 0.0 <= self.reserve_ratio <= 1.0:
            raise ValueError("reserve_ratio 必须在 0 到 1 之间")
        if not 0.0 <= self.min_relevance <= 1.0:
            raise ValueError("min_relevance 必须在 0 到 1 之间")
        if abs(self.recency_weight + self.relevance_weight - 1.0) >= 1e-6:
            raise ValueError("recency_weight + relevance_weight 必须等于 1.0")
        if self.max_history_messages < 0:
            raise ValueError("max_history_messages 不能小于 0")


class ContextBuilder:
    """Gather, select, structure, and compress information for one LLM call."""

    def __init__(self, config: Optional[ContextConfig] = None) -> None:
        self.config = config or ContextConfig()

    def build(
        self,
        user_query: str,
        conversation_history: Optional[list[Any]] = None,
        system_instructions: Optional[str] = None,
        custom_packets: Optional[list[ContextPacket]] = None,
    ) -> str:
        """Return a single structured context string for the current user query."""
        if not isinstance(user_query, str) or not user_query.strip():
            raise ValueError("user_query 不能为空")

        packets = self._gather(
            user_query=user_query.strip(),
            conversation_history=conversation_history,
            system_instructions=system_instructions,
            custom_packets=custom_packets,
        )
        selected = self._select(packets, user_query)
        context = self._structure(selected, user_query.strip())
        if self.config.enable_compression:
            context = self._compress(context, self.config.max_tokens)
        return context

    @staticmethod
    def packets_from_notes(notes: list[dict[str, Any]]) -> list[ContextPacket]:
        """Convert NoteTool.search_notes() results into candidate context packets."""
        packets = []
        for note in notes:
            title = str(note.get("title", "未命名笔记"))
            body = str(note.get("content", ""))
            updated_at = note.get("updated_at")
            try:
                timestamp = datetime.fromisoformat(updated_at) if updated_at else datetime.now()
            except (TypeError, ValueError):
                timestamp = datetime.now()
            packets.append(ContextPacket(
                content=f"[项目笔记：{title}]\n{body}",
                timestamp=timestamp,
                relevance_score=0.75,
                metadata={
                    "type": "note",
                    "note_type": note.get("type", "general"),
                    "note_id": note.get("note_id", ""),
                },
            ))
        return packets

    def _gather(
        self,
        user_query: str,
        conversation_history: Optional[list[Any]],
        system_instructions: Optional[str],
        custom_packets: Optional[list[ContextPacket]],
    ) -> list[ContextPacket]:
        """Collect system rules, recent messages, and caller-supplied evidence."""
        packets: list[ContextPacket] = []
        if system_instructions and system_instructions.strip():
            packets.append(ContextPacket(
                content=system_instructions.strip(),
                relevance_score=1.0,
                metadata={"type": "system_instruction"},
            ))

        history = conversation_history or []
        if self.config.max_history_messages:
            history = history[-self.config.max_history_messages:]
        else:
            history = []
        for message in history:
            content = getattr(message, "content", None)
            role = getattr(message, "role", None)
            timestamp = getattr(message, "timestamp", datetime.now())
            if isinstance(message, dict):
                content = message.get("content", content)
                role = message.get("role", role)
                timestamp = message.get("timestamp", timestamp)
            if not isinstance(content, str) or not content.strip():
                continue
            if not isinstance(timestamp, datetime):
                timestamp = datetime.now()
            packets.append(ContextPacket(
                content=f"{role or 'message'}: {content.strip()}",
                timestamp=timestamp,
                relevance_score=0.6,
                metadata={"type": "conversation_history", "role": role or "unknown"},
            ))

        for packet in custom_packets or []:
            if not isinstance(packet, ContextPacket):
                raise TypeError("custom_packets 中的每一项都必须是 ContextPacket")
            packets.append(packet)
        return packets

    def _select(self, packets: list[ContextPacket], user_query: str) -> list[ContextPacket]:
        """Keep system rules first, then rank useful packets within the token budget."""
        system_packets = [p for p in packets if p.metadata.get("type") == "system_instruction"]
        candidates = [p for p in packets if p.metadata.get("type") != "system_instruction"]
        candidates.sort(key=lambda p: self._combined_score(p, user_query), reverse=True)

        selected = list(system_packets)
        system_tokens = sum(packet.token_count for packet in system_packets)
        budget = self.config.max_tokens
        # Keep at least reserve_ratio of the budget available for system rules.
        # If the actual rules are longer, their actual size takes precedence.
        non_system_budget = max(0, budget - max(system_tokens, int(budget * self.config.reserve_ratio)))
        selected_non_system_tokens = 0
        for packet in candidates:
            relevance = max(packet.relevance_score, self._calculate_relevance(packet.content, user_query))
            if relevance < self.config.min_relevance:
                continue
            if selected_non_system_tokens + packet.token_count <= non_system_budget:
                selected.append(packet)
                selected_non_system_tokens += packet.token_count
        return selected

    def _combined_score(self, packet: ContextPacket, user_query: str) -> float:
        relevance = max(packet.relevance_score, self._calculate_relevance(packet.content, user_query))
        age_hours = max(0.0, (datetime.now() - packet.timestamp).total_seconds() / 3600)
        recency = max(0.1, math.exp(-0.1 * age_hours / 24))
        return self.config.relevance_weight * relevance + self.config.recency_weight * recency

    @staticmethod
    def _calculate_relevance(content: str, query: str) -> float:
        """A small lexical-overlap baseline; replaceable by a retriever score."""
        tokenize = lambda text: set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower()))
        content_words = tokenize(content)
        query_words = tokenize(query)
        union = content_words | query_words
        return len(content_words & query_words) / len(union) if union else 0.0

    def _structure(self, packets: list[ContextPacket], user_query: str) -> str:
        """Arrange selected packets into stable sections the model can understand."""
        rules: list[str] = []
        evidence: list[str] = []
        history_and_memory: list[str] = []
        for packet in packets:
            packet_type = packet.metadata.get("type", "general")
            if packet_type == "system_instruction":
                rules.append(packet.content)
            elif packet_type in {"rag_result", "knowledge", "evidence"}:
                evidence.append(packet.content)
            else:
                history_and_memory.append(packet.content)

        sections = []
        if rules:
            sections.append("[角色与规则]\n" + "\n".join(rules))
        sections.append("[当前任务]\n" + user_query)
        if evidence:
            sections.append("[检索证据]\n" + "\n\n---\n\n".join(evidence))
        if history_and_memory:
            sections.append("[历史与相关信息]\n" + "\n".join(history_and_memory))
        sections.append("[回答要求]\n基于可用材料回答；区分事实、推断和仍需确认的信息。")
        return "\n\n".join(sections)

    def _compress(self, context: str, max_tokens: int) -> str:
        """Apply a deterministic truncation fallback when the estimated budget is exceeded."""
        if self.count_tokens(context) <= max_tokens:
            return context
        marker = "\n[上下文过长，后续内容已省略]"
        return self._truncate_text(context, max(1, max_tokens - self.count_tokens(marker))) + marker

    @staticmethod
    def _truncate_text(text: str, max_tokens: int) -> str:
        """Estimate a safe character limit and truncate the text."""
        if max_tokens <= 0:
            return ""
        estimated_tokens = ContextBuilder.count_tokens(text)
        if estimated_tokens == 0:
            return ""
        chars_per_token = len(text) / estimated_tokens
        return text[:max(1, int(max_tokens * chars_per_token))]

    @staticmethod
    def count_tokens(text: str) -> int:
        """Rough estimate only: Chinese characters plus 1.3 per whitespace word."""
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        other_words = len(re.findall(r"[^\s\u4e00-\u9fff]+", text))
        return chinese_chars + math.ceil(other_words * 1.3)
