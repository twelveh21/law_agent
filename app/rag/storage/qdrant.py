from typing import Any, Dict, List, Optional

from app.common.path import DATA_DIR
from ..embeddings import get_dimension


_PIPELINE_CACHE: Dict[tuple, Dict[str, Any]] = {}


class _QdrantStoreAdapter:
    """把 Qdrant 的查询结果转换成 search_vectors_expanded 需要的格式。"""

    def __init__(self, client: Any, collection_name: str) -> None:
        self.client = client
        self.collection_name = collection_name

    def upsert_points(self, points: List[Dict[str, Any]]) -> None:
        """将已经准备好的 point 批量写入当前 collection。"""
        if not points:
            return

        try:
            from qdrant_client import models
        except ImportError as exc:
            raise RuntimeError(
                "缺少 qdrant-client，请在项目虚拟环境中安装项目依赖"
            ) from exc

        qdrant_points = [
            models.PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point["payload"],
            )
            for point in points
        ]

        # wait=True：等 Qdrant 确认本批写入完成后再返回。
        self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points,
            wait=True,
        )

    def search_similar(
            self,
            query_vector: List[float],
            limit: int,
            score_threshold: Optional[float] = None,
            where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        from qdrant_client import models

        conditions = [
            models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in (where or {}).items()
        ]
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=models.Filter(must=conditions) if conditions else None,
            with_payload=True,
        )

        hits: List[Dict[str, Any]] = []
        for point in response.points:
            payload = point.payload or {}
            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {key: value for key, value in payload.items() if key != "content"}
            hits.append({
                "id": str(point.id),
                "content": payload.get("content", ""),
                "metadata": metadata,
                "score": float(point.score),
            })
        return hits


def create_rag_pipeline(
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        collection_name: str = "rag_knowledge_base",
        rag_namespace: str = "default",
        vector_size: Optional[int] = None,
) -> Dict[str, Any]:
    """创建 Qdrant 客户端并确保目标 collection 存在。

    没传 qdrant_url 时使用项目内的本地持久化数据库；传了 URL 时连接远程 Qdrant。
    这里只负责准备向量存储，不负责生成 embedding 或写入文档。
    """
    if vector_size is None:
        vector_size = get_dimension()
    if vector_size <= 0:
        raise ValueError("vector_size 必须大于 0")
    if not collection_name.strip():
        raise ValueError("collection_name 不能为空")
    if not rag_namespace.strip():
        raise ValueError("rag_namespace 不能为空")
    if qdrant_api_key and not qdrant_url:
        raise ValueError("使用 qdrant_api_key 时必须同时提供 qdrant_url")

    # 复用同一组配置对应的客户端；Qdrant 本地模式不应对同一路径重复开客户端。
    cache_key = (qdrant_url, qdrant_api_key, collection_name, rag_namespace, vector_size)
    if cache_key in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[cache_key]

    try:
        from qdrant_client import QdrantClient, models
    except ImportError as exc:
        raise RuntimeError(
            "缺少 qdrant-client，请在项目虚拟环境中安装项目依赖"
        ) from exc

    if qdrant_url:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    else:
        local_qdrant_path = DATA_DIR / "rag_qdrant"
        local_qdrant_path.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(local_qdrant_path))

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
    else:
        collection = client.get_collection(collection_name)
        vectors_config = collection.config.params.vectors
        existing_size = getattr(vectors_config, "size", None)
        if existing_size is not None and existing_size != vector_size:
            raise ValueError(
                f"collection '{collection_name}' 的向量维度是 {existing_size}，"
                f"当前配置要求 {vector_size}。请使用新 collection 名称，"
                "不要直接删除已有数据。"
            )

    pipeline = {
        "client": client,
        "store": _QdrantStoreAdapter(client, collection_name),
        "collection_name": collection_name,
        "rag_namespace": rag_namespace,
        "vector_size": vector_size,
        "distance": "cosine",
    }
    _PIPELINE_CACHE[cache_key] = pipeline
    return pipeline


def _create_default_vector_store(vector_size: Optional[int] = None) -> _QdrantStoreAdapter:
    """获取项目默认的本地 Qdrant 向量存储适配器。"""
    if vector_size is None:
        vector_size = get_dimension()
    pipeline = create_rag_pipeline(vector_size=vector_size)
    return pipeline["store"]
