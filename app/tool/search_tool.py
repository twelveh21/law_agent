import os
from typing import Optional

from scripts.regsetup import description

from .tool_base import Tool


class SearchTool(Tool):
    """智能混合搜索工具"""
    def __init__(self,backend:str="hybrid",tavily_key:Optional[str]=None,
                 serapi_key:Optional[str]=None):
        super().__init(
            name="search",
            description="一个智能网页搜索引擎"
        )
        self.backend = backend
        self.tavily_key = tavily_key or os.getenv("TAVILY_API_KEY")
        self.serapi_key = serapi_key or os.getenv("SERAPI_API_KEY")
        self.available_backends=[]
        self._setup_backends()

    def _search_hybrid(self,query:str)->str:
        """后端选择逻辑"""
        if "tavily" in self.available_backends:
            try:
                return self._search_tavily(query)
            except Exception as e:
                print(e)

                if "serapi" in self.available_backends:
                    print("切换到serpapi搜索")
                    return self._search_serapi(query)

        elif "serapi" in self.available_backends:
            try:
                return self._search_serapi(query)
            except Exception as e:
                print(e)

        return "无可用搜索源"

    def _search_tavily(self,query:str)->str:
        response = self.tavily_client.search(
            query=query,
            search_depth="basic",
            include_answer=True,
            max_results=3
        )

        result = f"tavily搜索结果：{response.get('answer','未找到直接答案')}\n\n"

        for i,item in enumerate(response.get('results',[])[:3],1):
            result += f"[{i}] {item.get('title', '')}\n"
            result += f"    {item.get('content', '')[:200]}...\n"
            result += f"    来源: {item.get('url', '')}\n\n"

        return result