from uuid import NAMESPACE_URL, uuid5
from typing import Any, Dict, List, Optional

from ..embeddings import get_dimension, get_text_embedder
from ..storage.qdrant import _create_default_vector_store
from .documents import _preprocess_markdown_for_embedding


def index_chunks(
        store:Any=None,
        chunks:Optional[List[Dict]]=None,
        cache_db:Optional[str]=None,
        batch_size:int=64,
        rag_namespace:str="default",
        source:Optional[str]=None,
)->None:
    """将文本块向量化，并分批 upsert 到 Qdrant。"""

    if not chunks:
        print("[RAG]No chunks to index")
        return
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")
    if not rag_namespace.strip():
        raise ValueError("rag_namespace 不能为空")

    # 使用统一嵌入模型
    embedder=get_text_embedder()
    dimension=get_dimension()
    if store is None:
        store=_create_default_vector_store(dimension)
        print(f"[RAG]Created default vector store with dimension {dimension}")

    # 预处理 Markdown
    processed_texts=[]
    for c in chunks:
        raw_content=c["content"]
        processed_content=_preprocess_markdown_for_embedding(raw_content)
        processed_texts.append(processed_content)

    print(f"[RAG]Embedding start:total_texts={len(processed_texts)}batch_size={batch_size}")

    # 批量编码
    vecs:List[List[float]]=[]
    for i in range(0,len(processed_texts),batch_size):
        part=processed_texts[i:i+batch_size]
        try:
            part_vecs=embedder.embed_documents(part)

            # 兼容 NumPy 数组等返回值；统一转成二维 Python 列表。
            if hasattr(part_vecs,"tolist"):
                part_vecs=part_vecs.tolist()
            if not isinstance(part_vecs,list):
                part_vecs=list(part_vecs)
            if part_vecs and isinstance(part_vecs[0], (int, float)):
                part_vecs=[part_vecs]
            if len(part_vecs) != len(part):
                raise ValueError(f"本批有 {len(part)} 段文本，但模型返回 {len(part_vecs)} 个向量")

            # 处理向量格式并严格检查维度，避免补零/截断掩盖模型配置错误。
            for v in part_vecs:
                if hasattr(v,"tolist"):
                    v=v.tolist()
                v_norm=[float(x) for x in v]

                if len(v_norm) != dimension:
                    raise ValueError(f"向量维度异常：期望 {dimension}，实际 {len(v_norm)}")
                vecs.append(v_norm)

        except Exception as e:
            print(f"[WARNING] Batch {i} encoding failed: {e}")
            raise

        print(f"[RAG]Embedding progress:{min(i+batch_size,len(processed_texts))}/{len(processed_texts)}")

    if len(vecs) != len(chunks):
        raise ValueError(f"文本块数量为 {len(chunks)}，向量数量为 {len(vecs)}，无法一一对应")

    if not hasattr(store, "upsert_points"):
        raise TypeError("store 必须提供 upsert_points(points) 方法")

    # 每个文本块、它的向量和元数据组成一个 Qdrant point。
    points: List[Dict[str, Any]] = []
    for chunk, vector in zip(chunks, vecs):
        content = chunk.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("每个 chunk 都必须包含非空字符串 content")

        chunk_source = str(chunk.get("source") or source or "").strip()
        if not chunk_source:
            raise ValueError(
                "chunk 缺少 source；请在分块时保存来源，或调用 index_chunks(..., source=文件路径)"
            )
        chunk_start = chunk.get("start", 0)

        # UUID5 根据固定内容生成稳定 UUID；同一来源、位置和正文重跑时 ID 不变。
        identity = "\0".join(
            (rag_namespace, chunk_source, str(chunk_start), content)
        )
        point_id = str(uuid5(NAMESPACE_URL, identity))

        metadata = {
            key: value
            for key, value in chunk.items()
            if key not in {"content", "source"}
        }
        metadata["source"] = chunk_source
        metadata["memory_id"] = point_id

        points.append(
            {
                "id": point_id,
                "vector": vector,
                "payload": {
                    "content": content,
                    "metadata": metadata,
                    # 下面几个字段与 retrieval/search.py 中的过滤条件对应。
                    "memory_type": "rag_chunk",
                    "is_rag_data": True,
                    "data_source": "rag_pipeline",
                    "rag_namespace": rag_namespace,
                },
            }
        )

    # 分批写入，避免一次性把大量 point 发给 Qdrant。
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        store.upsert_points(batch)
        print(f"[RAG]Qdrant upsert progress:{min(i + batch_size, len(points))}/{len(points)}")
