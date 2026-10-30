from typing import Any, Dict, Optional

from app.agent.law import model
from app.tool.tool_base import Tool
from .storage.qdrant import create_rag_pipeline


class RAGTool(Tool):
    """
    rag工具
    提供完整rag功能：
    -添加多格式文档
    -智能检索与召回
    -llm增强问答
    -知识库管理"""

    def __init__(
            self,
            knowledge_base_path:str="./knowledge_base",
            qdrant_url:Optional[str]=None,
            qdrant_api_key:Optional[str]=None,
            collection_name:str="rag_knowledge_base",
            rag_namespace:str="default"
    ):
        super().__init__(name="rag", description="管理并检索 RAG 知识库")
        self.knowledge_base_path = knowledge_base_path
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.collection_name = collection_name
        self.rag_namespace = rag_namespace
        self._pipelines:Dict[str,Dict[str,Any]]={}
        # RAGTool 需要的是模型客户端，不是组装后的 LangChain Agent。
        self.llm = model

        default_pipeline=create_rag_pipeline(
            qdrant_url=self.qdrant_url,
            qdrant_api_key=self.qdrant_api_key,
            collection_name=collection_name,
            rag_namespace=rag_namespace
        )
        self._pipelines[self.rag_namespace]=default_pipeline
