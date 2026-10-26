import os
from functools import lru_cache
from typing import Any, List


_DEFAULT_EMBEDDING_MODEL = "text-embedding-v1"


_EMBEDDING_DIMENSIONS = {
    "text-embedding-v1": 1536,
    "text-embedding-v2": 1536,
    "text-embedding-v3": 1024,
}


@lru_cache(maxsize=1)
def get_text_embedder() -> Any:
    """创建并缓存与法律 Agent 同属 DashScope 的文本向量模型。"""
    model_name = os.getenv("RAG_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL).strip()
    if model_name not in _EMBEDDING_DIMENSIONS:
        supported = ", ".join(_EMBEDDING_DIMENSIONS)
        raise ValueError(
            f"不支持的 RAG_EMBEDDING_MODEL: {model_name!r}。当前支持: {supported}"
        )

    try:
        from langchain_community.embeddings import DashScopeEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "创建 DashScope embedding 需要 langchain-community 和 dashscope 依赖"
        ) from exc

    # 该类从 DASHSCOPE_API_KEY 环境变量读取 API Key；与 law.py 的向量模型保持一致。
    return DashScopeEmbeddings(model=model_name)


def get_dimension() -> int:
    """返回当前配置的 DashScope embedding 模型输出维度。"""
    model_name = os.getenv("RAG_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL).strip()
    try:
        return _EMBEDDING_DIMENSIONS[model_name]
    except KeyError as exc:
        supported = ", ".join(_EMBEDDING_DIMENSIONS)
        raise ValueError(
            f"无法确定模型 {model_name!r} 的向量维度。当前支持: {supported}"
        ) from exc


def embed_query(query: str) -> List[float]:
    """使用与文档相同的 embedding 模型将用户查询转换为向量。"""
    if not query.strip():
        raise ValueError("query 不能为空")
    return get_text_embedder().embed_query(query)
