"""Legal retrieval followed by ContextBuilder evidence selection."""

from app.context import ContextBuilder, ContextConfig


def search_legal_knowledge_text(query: str, top_k: int = 5) -> str:
    """Retrieve chunks and return budgeted, traceable evidence text."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query 不能为空")
    if not 1 <= top_k <= 20:
        raise ValueError("top_k 必须在 1 到 20 之间")
    # Lazy import: discovering MCP tools does not open Qdrant or load embeddings.
    from app.rag.pipeline import retrieve_knowledge

    results = retrieve_knowledge(query.strip(), top_k=top_k)
    if not results:
        return "Qdrant 法律知识库中没有找到相关内容。"

    # A separate builder/budget is used for retrieved evidence. The middleware
    # still manages chat history + memory; it does not reparse MCP result text.
    builder = ContextBuilder(ContextConfig(
        max_tokens=3000,
        reserve_ratio=0.0,
        enable_compression=False,  # Keep chunks and their citations whole.
    ))
    return builder.build_evidence_context(query.strip(), results)
