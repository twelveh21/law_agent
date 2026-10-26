"""High-level entry points that connect document ingestion and retrieval."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ingestion.chunking import _chunk_paragraphs, _split_paragraphs_with_headings
from .ingestion.documents import _convert_to_markdown
from .ingestion.indexing import index_chunks
from .retrieval.search import search_vectors_expanded
from .storage.qdrant import create_rag_pipeline


def _get_configured_pipeline(
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    collection_name: Optional[str] = None,
    rag_namespace: Optional[str] = None,
) -> tuple[Dict[str, Any], str]:
    """读取统一的 Qdrant 配置，确保入库与检索连接同一个 collection。"""
    configured_url = qdrant_url or os.getenv("QDRANT_URL") or None
    configured_api_key = qdrant_api_key or os.getenv("QDRANT_API_KEY") or None
    configured_collection = (
        collection_name
        or os.getenv("QDRANT_COLLECTION_NAME")
        or "rag_knowledge_base"
    )
    configured_namespace = (
        rag_namespace or os.getenv("RAG_NAMESPACE") or "default"
    )

    pipeline = create_rag_pipeline(
        qdrant_url=configured_url,
        qdrant_api_key=configured_api_key,
        collection_name=configured_collection,
        rag_namespace=configured_namespace,
    )
    return pipeline, configured_namespace


def ingest_document(
    path: str,
    *,
    store: Any = None,
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    collection_name: Optional[str] = None,
    rag_namespace: Optional[str] = None,
    chunk_tokens: int = 500,
    overlap_tokens: int = 50,
    batch_size: int = 64,
) -> Dict[str, Any]:
    """读取单个文件、解析分块并将文本块写入 Qdrant。"""
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"待入库文件不存在: {file_path}")

    markdown_text = _convert_to_markdown(str(file_path))
    if not markdown_text.strip():
        raise ValueError(f"文件没有提取到可入库的文字: {file_path}")

    paragraphs = _split_paragraphs_with_headings(markdown_text)
    chunks = _chunk_paragraphs(
        paragraphs,
        chunk_tokens=chunk_tokens,
        overlap_tokens=overlap_tokens,
    )
    if not chunks:
        raise ValueError(f"文件切分后没有可入库的文本块: {file_path}")

    # chunker 只负责正文和位置；这里补齐可追溯的文件来源。
    for chunk in chunks:
        chunk["source"] = str(file_path)
        chunk["source_name"] = file_path.name

    if store is None:
        configured_pipeline, namespace = _get_configured_pipeline(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            collection_name=collection_name,
            rag_namespace=rag_namespace,
        )
        target_store = configured_pipeline["store"]
    else:
        configured_pipeline = {
            "collection_name": collection_name
            or os.getenv("QDRANT_COLLECTION_NAME")
            or "rag_knowledge_base"
        }
        namespace = rag_namespace or os.getenv("RAG_NAMESPACE") or "default"
        target_store = store

    index_chunks(
        store=target_store,
        chunks=chunks,
        batch_size=batch_size,
        rag_namespace=namespace,
        source=str(file_path),
    )
    return {
        "source": str(file_path),
        "source_name": file_path.name,
        "chunk_count": len(chunks),
        "collection_name": configured_pipeline["collection_name"],
        "rag_namespace": namespace,
    }


def retrieve_knowledge(
    query: str,
    *,
    store: Any = None,
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    collection_name: Optional[str] = None,
    rag_namespace: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """使用同一套 Qdrant 配置检索问题相关的文本块。"""
    if store is None:
        configured_pipeline, namespace = _get_configured_pipeline(
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            collection_name=collection_name,
            rag_namespace=rag_namespace,
        )
        target_store = configured_pipeline["store"]
    else:
        namespace = rag_namespace or os.getenv("RAG_NAMESPACE") or "default"
        target_store = store
    return search_vectors_expanded(
        store=target_store,
        query=query,
        top_k=top_k,
        rag_namespace=namespace,
    )
