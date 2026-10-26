"""Helpers for building traceable, article-aware legal RAG chunks."""

import hashlib
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Keep the new article-aware index isolated from the legacy default collection.
LAW_COLLECTION_NAME = "law_articles_v1"

_ARTICLE_HEADER = re.compile(
    r"(?m)^[ \t\u3000]*(第[零〇一二两三四五六七八九十百千万0-9]+条"
    r"(?:之[零〇一二两三四五六七八九十0-9]+)?)(?=[^\r\n]|$)"
)


def split_legal_documents(
    documents: list[Document], *, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[Document]:
    """Split source documents at article boundaries and retain citation metadata."""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        add_start_index=True,
    )
    chunks: list[Document] = []

    for source_document in documents:
        text = source_document.page_content.strip()
        if not text:
            continue

        source = str(source_document.metadata.get("source", ""))
        source_name = Path(source).name if source else "未知来源"
        matches = list(_ARTICLE_HEADER.finditer(text))

        if not matches:
            metadata = {
                **source_document.metadata,
                "source_name": source_name,
                "article": "未识别",
            }
            chunks.extend(
                splitter.split_documents(
                    [Document(page_content=text, metadata=metadata)]
                )
            )
            continue

        # Ignore front matter / table of contents before the first actual article.
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            article_text = text[match.start() : end].strip()
            if not article_text:
                continue

            metadata = {
                **source_document.metadata,
                "source_name": source_name,
                "article": match.group(1),
            }
            article_document = Document(page_content=article_text, metadata=metadata)
            chunks.extend(splitter.split_documents([article_document]))

    return chunks


def make_chunk_ids(chunks: list[Document]) -> list[str]:
    """Create repeatable IDs so rerunning an incremental build won't duplicate chunks."""
    ids = []
    for index, document in enumerate(chunks):
        identity = "\0".join(
            (
                str(document.metadata.get("source", "")),
                str(document.metadata.get("article", "")),
                str(index),
                document.page_content,
            )
        )
        ids.append(hashlib.sha256(identity.encode("utf-8")).hexdigest())
    return ids
