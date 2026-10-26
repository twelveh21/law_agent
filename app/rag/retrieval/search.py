from math import ceil
from typing import Any, Dict, List, Optional

from ..embeddings import embed_query
from ..storage.qdrant import _create_default_vector_store


def _get_expansion_model() -> Any:
    """仅在启用 MQE/HyDE 时加载法律 Agent 的大模型。"""
    from app.agent.law import model

    return model


def _prompt_mqe(query: str, n: int) -> List[str]:
    """让大模型把一个问题改写成多个意思相近的检索问题。"""
    try:
        prompt = [
            {
                "role": "system",
                "content": "你是检索查询扩展助手。生成语义等价或互补的多样化查询。使用中文，简短，避免标点",
            },
            {
                "role": "user",
                "content": f"原始查询：{query}\n请给出{n}个不同表述的查询，每行一个",
            },
        ]
        response = _get_expansion_model().invoke(prompt)
        text = response.content if isinstance(response.content, str) else ""
        lines = [
            line.strip().lstrip("-*•0123456789.、 \t")
            for line in text.splitlines()
        ]
        return [line for line in lines if line][:n]
    except Exception:
        # 查询扩展不可用时仍然可以用原始问题检索，不中断基础 RAG。
        return []


def _prompt_hyde(query: str) -> Optional[str]:
    """让大模型生成一段假设性答案文本，作为额外的检索查询。"""
    try:
        prompt = [
            {
                "role": "system",
                "content": "根据用户问题，写一段可能的答案性文字用于向量检索，不要分析过程。",
            },
            {
                "role": "user",
                "content": f"{query}\n请直接写一段客观、包含关键术语的中文段落",
            },
        ]
        response = _get_expansion_model().invoke(prompt)
        text = response.content if isinstance(response.content, str) else ""
        return text.strip() or None
    except Exception:
        return None


def search_vectors_expanded(
    store: Any = None,
    query: str = "",
    top_k: int = 8,
    rag_namespace: Optional[str] = "default",
    only_rag_data: bool = True,
    score_threshold: Optional[float] = None,
    enable_mqe: bool = False,
    mqe_expansions: int = 2,
    enable_hyde: bool = False,
    candidate_pool_multiplier: int = 4,
) -> List[Dict[str, Any]]:
    """把问题转为向量，在 Qdrant 中检索并合并最相关的文本块。"""
    if not isinstance(query, str) or not query.strip():
        return []
    query = query.strip()
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0")
    if candidate_pool_multiplier <= 0:
        raise ValueError("candidate_pool_multiplier 必须大于 0")
    if mqe_expansions < 0:
        raise ValueError("mqe_expansions 不能小于 0")

    # 未传入存储对象时，使用与默认入库流程相同的本地 Qdrant collection。
    if store is None:
        store = _create_default_vector_store()
    if not callable(getattr(store, "search_similar", None)):
        raise TypeError("store 必须提供 search_similar(...) 方法")

    # 基础查询始终保留；MQE/HyDE 只是可选地增加查询表达方式。
    expansions = [query]
    if enable_mqe and mqe_expansions > 0:
        expansions.extend(_prompt_mqe(query, mqe_expansions))
    if enable_hyde:
        hyde_text = _prompt_hyde(query)
        if hyde_text:
            expansions.append(hyde_text)

    # 去掉空内容和重复查询，避免重复调用 embedding 与 Qdrant。
    unique_expansions: List[str] = []
    for expansion in expansions:
        if expansion and expansion not in unique_expansions:
            unique_expansions.append(expansion)

    # 每个查询取一部分候选，之后合并排序；至少为每个查询取 1 条。
    candidate_pool = max(top_k * candidate_pool_multiplier, 20)
    per_query_limit = max(1, ceil(candidate_pool / len(unique_expansions)))

    # 这些字段必须与 indexing.py 写入 payload 时的字段和值保持一致。
    where: Dict[str, Any] = {"memory_type": "rag_chunk"}
    if only_rag_data:
        where["is_rag_data"] = True
        where["data_source"] = "rag_pipeline"
    if rag_namespace:
        where["rag_namespace"] = rag_namespace

    # 对每种查询表述分别做 embedding 和向量检索。
    # 一个 point 可能被多种表述找到，因此按稳定 memory_id 去重并保留最高分。
    results_by_id: Dict[str, Dict[str, Any]] = {}
    for expanded_query in unique_expansions:
        query_vector = embed_query(expanded_query)
        hits = store.search_similar(
            query_vector=query_vector,
            limit=per_query_limit,
            score_threshold=score_threshold,
            where=where,
        )

        for hit in hits:
            metadata = hit.get("metadata") or {}
            point_id = str(metadata.get("memory_id", hit.get("id", "")))
            score = float(hit.get("score", 0.0))
            previous = results_by_id.get(point_id)
            if previous is None or score > float(previous.get("score", 0.0)):
                results_by_id[point_id] = hit

    # 分数从高到低排序，只把 top_k 个文本块交给后续 Agent。
    merged_results = list(results_by_id.values())
    merged_results.sort(key=lambda hit: float(hit.get("score", 0.0)), reverse=True)
    return merged_results[:top_k]
