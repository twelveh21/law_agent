"""Index local legal text files into the same Qdrant collection used by MCP."""

import argparse
from pathlib import Path

from langchain_core.documents import Document

from app.common.legal_rag import split_legal_documents
from app.rag.ingestion.indexing import index_chunks
from app.rag.pipeline import _get_configured_pipeline
from app.rag.storage.qdrant import close_cached_pipelines


def ingest_legal_files(paths: list[Path], batch_size: int = 16) -> None:
    """Keep article metadata and reuse existing embedding/upsert code."""
    # Validate inputs before opening the database or sending embedding requests.
    sources = [path.expanduser().resolve() for path in paths]
    for source in sources:
        if not source.is_file() or source.suffix.lower() != ".txt":
            raise ValueError(f"需要现有的 TXT 法律资料：{source}")
    try:
        pipeline, namespace = _get_configured_pipeline()
        for source in sources:
            document = Document(
                page_content=source.read_text(encoding="utf-8-sig"),
                metadata={"source": str(source)},
            )
            documents = split_legal_documents([document])
            chunks = [
                {
                    **item.metadata,
                    "content": item.page_content,
                    "start": item.metadata.get("start_index", 0),
                }
                for item in documents
            ]
            if not chunks:
                raise ValueError(f"文件没有可入库的内容：{source.name}")
            print(f"[RAG] {source.name}: {len(chunks)} article chunks")
            index_chunks(
                store=pipeline["store"], chunks=chunks,
                batch_size=batch_size, rag_namespace=namespace,
                source=str(source),
            )
        info = pipeline["client"].get_collection(pipeline["collection_name"])
        print(f"[RAG] collection={pipeline['collection_name']} points={info.points_count}")
    finally:
        close_cached_pipelines()


def main() -> None:
    parser = argparse.ArgumentParser(description="将 TXT 法律资料按法条分块并存入 Qdrant")
    parser.add_argument("files", type=Path, nargs="+", help="需要入库的 TXT 文件")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size 必须大于 0")
    ingest_legal_files(args.files, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
