"""Adapters that expose existing legal-search logic through the Tool interface."""

from typing import Any

from .tool_base import Tool, ToolParameter


class LawTools(Tool):
    """Expose an existing legal search callable as a framework Tool."""

    def __init__(self, search_function: Any) -> None:
        super().__init__(
            name="search_law",
            description="根据问题搜索相关法律条文",
        )
        self.search_function = search_function

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="用户提出的法律问题",
                required=True,
            )
        ]

    def run(self, parameters: dict[str, Any]) -> str:
        if not isinstance(parameters, dict):
            raise TypeError("search_law 的参数必须是字典")

        query = parameters.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("参数 'query' 必须是非空字符串")

        # LangChain 的 @tool 对象使用 invoke；普通 Python 函数直接调用。
        invoke = getattr(self.search_function, "invoke", None)
        if callable(invoke):
            result = invoke({"query": query})
        elif callable(self.search_function):
            result = self.search_function(query)
        else:
            raise TypeError("search_function 必须是可调用对象，或提供 invoke() 方法")

        return result if isinstance(result, str) else str(result)
