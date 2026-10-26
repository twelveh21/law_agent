import json
import unittest
from tempfile import TemporaryDirectory

from app.context import ContextBuilder, ContextConfig, ContextPacket
from app.note import NoteTool
from app.note_context.note_context import ProjectContextService


class NoteToolTests(unittest.TestCase):
    def test_note_lifecycle_and_search(self):
        with TemporaryDirectory() as temp_dir:
            notes = NoteTool(temp_dir)
            note_id = notes.create_note(
                "劳动合同结论", "未签劳动合同需要进一步核对入职时间。",
                note_type="conclusion", tags=["劳动法", "待核实"],
            )
            loaded = notes.read_note(note_id)
            self.assertEqual(loaded["metadata"]["type"], "conclusion")
            self.assertIn("入职时间", loaded["content"])

            matches = notes.search_notes("入职时间", note_type="conclusion", tags=["待核实"])
            self.assertEqual([item["note_id"] for item in matches], [note_id])

            notes.update_note(note_id, tags=[])
            self.assertEqual(notes.read_note(note_id)["metadata"]["tags"], [])
            self.assertEqual(notes.summary()["total_notes"], 1)

            # A new instance proves that note files and the JSON index persist.
            reloaded = NoteTool(temp_dir)
            self.assertEqual(len(reloaded.list_notes()), 1)
            self.assertEqual(json.loads(reloaded.run({"action": "summary"}))["total_notes"], 1)

            notes.delete_note(note_id)
            self.assertEqual(notes.list_notes(), [])


class ContextBuilderTests(unittest.TestCase):
    def test_build_structures_rules_evidence_and_recent_history(self):
        builder = ContextBuilder(ContextConfig(max_tokens=1000, max_history_messages=2))
        context = builder.build(
            user_query="劳动合同未签怎么办",
            system_instructions="你是谨慎的法律信息助手。",
            conversation_history=[
                {"role": "user", "content": "更早的旧记录"},
                {"role": "user", "content": "旧的无关问题"},
                {"role": "user", "content": "公司没有签合同"},
            ],
            custom_packets=[ContextPacket(
                content="证据：劳动合同法相关条文。",
                relevance_score=0.9,
                metadata={"type": "evidence", "source": "test"},
            )],
        )

        self.assertIn("[角色与规则]", context)
        self.assertIn("[当前任务]\n劳动合同未签怎么办", context)
        self.assertIn("[检索证据]", context)
        self.assertIn("劳动合同法相关条文", context)
        self.assertNotIn("更早的旧记录", context)
        self.assertIn("旧的无关问题", context)
        self.assertIn("公司没有签合同", context)

    def test_project_context_service_brings_relevant_note_into_context(self):
        with TemporaryDirectory() as temp_dir:
            service = ProjectContextService(
                project_name="legal_agent",
                workspace=temp_dir,
                context_config=ContextConfig(max_tokens=1000),
            )
            service.note_tool.create_note(
                "劳动合同待办", "还需要确认劳动者的入职日期。",
                note_type="blocker",
            )
            context = service.build_context(
                user_query="入职日期还没确认，下一步怎么办？",
                system_instructions="你是谨慎的法律信息助手。",
            )

        self.assertIn("劳动合同待办", context)
        self.assertIn("还需要确认劳动者的入职日期", context)

    def test_context_config_rejects_invalid_weight_sum(self):
        with self.assertRaisesRegex(ValueError, "relevance_weight"):
            ContextConfig(recency_weight=0.2, relevance_weight=0.2)


if __name__ == "__main__":
    unittest.main()
