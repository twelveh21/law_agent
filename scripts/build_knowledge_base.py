import argparse

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import DashScopeEmbeddings

from app.common.legal_rag import (
    LAW_COLLECTION_NAME,
    make_chunk_ids,
    split_legal_documents,
)
from app.common.path import CHROMA_DIR, DATA_DIR


def build_knowledge_base(*, rebuild: bool = False) -> None:
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"知识库原始文件目录不存在: {DATA_DIR}")

    txt_files = sorted(DATA_DIR.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"目录中没有找到 txt 文件: {DATA_DIR}")

    source_documents = []
    for file_path in txt_files:
        print(f"正在加载: {file_path.name}")
        source_documents.extend(TextLoader(str(file_path), encoding="utf-8").load())

    if not source_documents:
        raise ValueError("没有从 txt 文件中读取到文档")

    chunks = split_legal_documents(source_documents)
    if not chunks:
        raise ValueError("没有生成可用于向量化的文本块")

    print(f"读取 {len(source_documents)} 个文档，切分为 {len(chunks)} 个法条文本块")
    print(f"目标索引: {LAW_COLLECTION_NAME}")

    embeddings = DashScopeEmbeddings()
    vectorstore = Chroma(
        persist_directory=str(CHROMA_DIR),
        collection_name=LAW_COLLECTION_NAME,
        embedding_function=embeddings,
    )

    if rebuild:
        # 只清理新版法条索引；旧的默认 collection 不会被删除。
        vectorstore.delete_collection()
        vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            collection_name=LAW_COLLECTION_NAME,
            embedding_function=embeddings,
        )

    vectorstore.add_documents(documents=chunks, ids=make_chunk_ids(chunks))
    print(f"知识库已更新: {CHROMA_DIR} / {LAW_COLLECTION_NAME}")


def main() -> None:
    parser = argparse.ArgumentParser(description="构建法条级法律向量知识库")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="重建新版法条索引（仅删除 law_articles_v1 collection）",
    )
    args = parser.parse_args()
    build_knowledge_base(rebuild=args.rebuild)


if __name__ == "__main__":
    main()
