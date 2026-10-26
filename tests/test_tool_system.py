import unittest

from app.tool.law_tools import LawTools
from app.tool.tool_base import ToolRegistry


class LawToolsTests(unittest.TestCase):
    def test_run_passes_query_to_existing_function(self):
        calls = []

        def fake_search_law(query: str) -> str:
            calls.append(query)
            return "《民法典》相关条文"

        tool = LawTools(search_function=fake_search_law)
        result = tool.run({"query": "合同违约责任"})

        self.assertEqual(calls, ["合同违约责任"])
        self.assertEqual(result, "《民法典》相关条文")

    def test_run_supports_langchain_tool_invoke_interface(self):
        class FakeLangChainTool:
            def __init__(self):
                self.received = None

            def invoke(self, payload):
                self.received = payload
                return "Tavily 搜索结果"

        existing_tool = FakeLangChainTool()
        tool = LawTools(search_function=existing_tool)

        result = tool.run({"query": "劳动合同试用期"})

        self.assertEqual(existing_tool.received, {"query": "劳动合同试用期"})
        self.assertEqual(result, "Tavily 搜索结果")

    def test_run_rejects_missing_or_blank_query(self):
        tool = LawTools(search_function=lambda query: query)

        for parameters in ({}, {"query": "   "}, {"query": 123}):
            with self.subTest(parameters=parameters):
                with self.assertRaises(ValueError):
                    tool.run(parameters)

    def test_parameter_description_generates_function_calling_schema(self):
        tool = LawTools(search_function=lambda query: query)

        schema = tool.to_openai_schema()

        self.assertEqual(schema["function"]["name"], "search_law")
        self.assertEqual(
            schema["function"]["parameters"]["properties"]["query"]["type"],
            "string",
        )
        self.assertEqual(schema["function"]["parameters"]["required"], ["query"])


class ToolRegistryTests(unittest.TestCase):
    def test_registry_finds_and_executes_tool(self):
        registry = ToolRegistry()
        tool = LawTools(search_function=lambda query: f"检索：{query}")
        registry.register(tool)

        self.assertEqual(registry.list_tools(), ["search_law"])
        self.assertEqual(
            registry.execute_tool("search_law", {"query": "劳动法"}),
            "检索：劳动法",
        )

    def test_registry_rejects_duplicate_and_unknown_tools(self):
        registry = ToolRegistry()
        registry.register(LawTools(search_function=lambda query: query))

        with self.assertRaises(ValueError):
            registry.register(LawTools(search_function=lambda query: query))
        with self.assertRaises(KeyError):
            registry.execute_tool("not_registered", {"query": "测试"})


if __name__ == "__main__":
    unittest.main()
