import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.memory import MemoryConfig, MemoryManager, MemoryTool
from app.tool.tool_base import ToolRegistry


class MemoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = MemoryConfig(
            working_memory_capacity=3,
            working_memory_ttl=60,
            persistent_memory_capacity=10,
            database_path=Path(self.temp_dir.name) / "memory.sqlite3",
        )
        self.manager = MemoryManager(config=self.config, user_id="test-user")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_and_search_working_memory(self):
        self.manager.add_memory("用户正在实现法律工具调用", "working", 0.8)
        self.manager.add_memory("用户在学习数据库索引", "working", 0.5)

        results = self.manager.retrieve_memories("法律工具调用", limit=2)

        self.assertEqual(len(results), 1)
        self.assertIn("法律工具调用", results[0].content)
        self.assertGreater(results[0].score, 0)

    def test_persistent_memories_survive_manager_recreation(self):
        memory_id = self.manager.add_memory(
            "昨天调试了合同违约责任检索", "episodic", 0.9,
            {"session_id": "session-1"},
        )

        reopened = MemoryManager(config=self.config, user_id="test-user")
        results = reopened.retrieve_memories("合同违约责任", memory_types=["episodic"])

        self.assertEqual(results[0].id, memory_id)
        self.assertEqual(results[0].metadata["session_id"], "session-1")

    def test_semantic_graph_metadata_can_contribute_to_retrieval(self):
        memory_id = self.manager.add_memory(
            "法律知识图谱中的一般规则", "semantic", 0.7,
            {"entities": ["合同违约"], "relations": ["适用法律"]},
        )

        results = self.manager.retrieve_memories("合同违约", memory_types=["semantic"])

        self.assertEqual(results[0].id, memory_id)
        self.assertGreater(results[0].score, 0)

    def test_perceptual_memory_filters_by_modality(self):
        self.manager.add_memory(
            "合同扫描件图片", "perceptual", 0.8,
            {"modality": "image", "raw_data": "合同.jpg"},
        )
        self.manager.add_memory(
            "合同讨论录音", "perceptual", 0.8,
            {"modality": "audio", "raw_data": "讨论.mp3"},
        )

        results = self.manager.retrieve_memories(
            "合同", memory_types=["perceptual"], modality="image"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata["modality"], "image")

    def test_importance_filter_and_forgetting_strategies(self):
        low_id = self.manager.add_memory("普通临时工作", "working", 0.1)
        self.manager.add_memory("重要项目目标", "working", 0.9)
        removed = self.manager.forget_memories(strategy="importance_based", threshold=0.5)

        self.assertEqual(removed, 1)
        remaining = self.manager.memory_types["working"].list_items()
        self.assertEqual(len(remaining), 1)
        self.assertNotEqual(remaining[0].id, low_id)

        old_id = self.manager.add_memory(
            "很久以前的合同记录", "episodic", 0.8,
            {"timestamp": (datetime.now() - timedelta(days=45)).isoformat()},
        )
        removed_by_age = self.manager.forget_memories(
            strategy="time_based", max_age_days=30
        )
        self.assertGreaterEqual(removed_by_age, 1)
        remaining_episodes = self.manager.memory_types["episodic"].list_items("test-user")
        self.assertNotIn(old_id, [item.id for item in remaining_episodes])

    def test_unknown_memory_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.add_memory("内容", "samantic", 0.5)


class MemoryToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        config = MemoryConfig(database_path=Path(self.temp_dir.name) / "memory.sqlite3")
        self.tool = MemoryTool(memory_config=config, user_id="tool-user")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tool_runs_through_existing_registry_interface(self):
        registry = ToolRegistry()
        registry.register(self.tool)

        added = registry.execute_tool(
            "memory",
            {"action": "add", "content": "用户正在学习法律 Agent 的记忆检索", "memory_type": "working"},
        )
        found = registry.execute_tool(
            "memory", {"action": "search", "query": "法律 Agent 记忆检索"}
        )
        summary = registry.execute_tool("memory", {"action": "summary"})

        self.assertIn("记忆已添加", added)
        self.assertIn("用户正在学习", found)
        self.assertIn("记忆总数：1", summary)

    def test_tool_schema_exposes_action_and_forget_operation(self):
        schema = self.tool.to_openai_schema()
        properties = schema["function"]["parameters"]["properties"]

        self.assertEqual(schema["function"]["name"], "memory")
        self.assertIn("action", properties)
        self.assertIn("strategy", properties)
        self.assertIn("memory_types", properties)

    def test_tool_forget_action_deletes_low_importance_records(self):
        self.tool.run({"action": "add", "content": "低重要性记忆", "importance": 0.1})

        result = self.tool.run(
            {"action": "forget", "strategy": "importance_based", "threshold": 0.5}
        )

        self.assertIn("已遗忘 1 条", result)


if __name__ == "__main__":
    unittest.main()
