"""Backward-compatible imports for the RAG components.

Implementations live in focused modules under app.rag. Prefer importing from
those modules directly in new code.
"""

from app.agent.law import model

from .agent_tool import RAGTool
from .embeddings import (
    _DEFAULT_EMBEDDING_MODEL,
    _EMBEDDING_DIMENSIONS,
    embed_query,
    get_dimension,
    get_text_embedder,
)
from .ingestion.chunking import (
    _approx_token_len,
    _chunk_paragraphs,
    _is_cjk,
    _split_paragraphs_with_headings,
)
from .ingestion.documents import (
    _convert_to_markdown,
    _enhanced_pdf_processing,
    _fallback_text_reader,
    _get_markdown_instance,
    _preprocess_markdown_for_embedding,
)
from .ingestion.indexing import index_chunks
from .retrieval.search import _prompt_hyde, _prompt_mqe, search_vectors_expanded
from .storage.qdrant import (
    _PIPELINE_CACHE,
    _QdrantStoreAdapter,
    _create_default_vector_store,
    create_rag_pipeline,
)
