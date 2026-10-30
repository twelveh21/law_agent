"""Concrete legal-search and web-reading tools for the legal agent."""

import os

import requests as http_requests
from bs4 import BeautifulSoup
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.tools import tool

from app.common.legal_rag import LAW_COLLECTION_NAME
from app.common.path import CHROMA_DIR
from app.rag.service import search_legal_knowledge_text


# This client is shared by the local knowledge search tool.
vectorstore = Chroma(
    persist_directory=str(CHROMA_DIR),
    # 本地默认使用新索引；Render 可切换到已包含法律切片的 legacy collection。
    collection_name=os.getenv("CHROMA_COLLECTION_NAME", LAW_COLLECTION_NAME),
    embedding_function=DashScopeEmbeddings(),
)


@tool
def search_local_knowledge(query: str) -> str:
    """Search the local legal knowledge base for relevant law articles."""
    docs = vectorstore.similarity_search(query, k=3)
    if not docs:
        return "未在本地知识库中找到相关内容。"

    results = []
    for rank, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source_name") or os.path.basename(
            doc.metadata.get("source", "未知来源")
        )
        article = doc.metadata.get("article", "未标注条款")
        results.append(
            f"[检索结果 {rank}] 来源：{source} {article}\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(results)


@tool
def search_qdrant_knowledge(query: str) -> str:
    """Search the Qdrant RAG collection and return law text with source metadata."""
    try:
        return search_legal_knowledge_text(query, top_k=5)
    except Exception:
        return "Qdrant 法律知识库检索失败，请检查数据库和向量模型配置。"


@tool
def web_crawler(url: str, requirement: str = "") -> str:
    """Fetch a web page and return its readable text, optionally with an extraction goal."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
        }
        response = http_requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        lines = [
            line.strip()
            for line in soup.get_text(separator="\n", strip=True).split("\n")
            if line.strip()
        ]
        text = "\n".join(lines)
        if len(text) > 8000:
            text = text[:8000] + "\n...（内容过长，已截断）"

        result = f"爬取网址: {url}\n"
        if requirement:
            result += f"提取要求: {requirement}\n"
        return result + f"\n爬取内容:\n{text}"
    except Exception as exc:
        return f"爬取失败: {exc}"
