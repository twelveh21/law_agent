import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.note_context.note_context import ProjectContextService
from app.simpletool import note_tools


class NoteLangChainToolTests(unittest.TestCase):
    def test_save_tool_creates_note_only_when_invoked(self):
        with TemporaryDirectory() as temp_dir:
            service = ProjectContextService(
                project_name="test_project",
                workspace=temp_dir,
            )
            with patch.object(note_tools, "_project_context", service):
                result = note_tools.save_project_note.invoke(
                    {
                        "title": "劳动合同待确认事项",
                        "content": "需要确认劳动者的入职日期。",
                        "note_type": "blocker",
                        "tags": ["劳动合同"],
                    }
                )

            self.assertIn("笔记已保存", result)
            self.assertEqual(
                service.note_tool.list_notes()[0]["title"],
                "劳动合同待确认事项",
            )

    def test_search_tool_uses_context_builder_for_matching_notes(self):
        with TemporaryDirectory() as temp_dir:
            service = ProjectContextService(
                project_name="test_project",
                workspace=temp_dir,
            )
            service.note_tool.create_note(
                title="劳动合同待确认事项",
                content="需要确认劳动者的入职日期。",
                note_type="blocker",
            )

            with patch.object(note_tools, "_project_context", service):
                result = note_tools.search_project_notes.invoke(
                    {"query": "劳动合同入职日期", "limit": 3}
                )

            self.assertIn("劳动合同待确认事项", result)
            self.assertIn("需要确认劳动者的入职日期", result)

    def test_search_tool_reports_no_matches(self):
        with TemporaryDirectory() as temp_dir:
            service = ProjectContextService(
                project_name="test_project",
                workspace=temp_dir,
            )
            with patch.object(note_tools, "_project_context", service):
                result = note_tools.search_project_notes.invoke(
                    {"query": "不存在的内容"}
                )

            self.assertIn("没有找到", result)


if __name__ == "__main__":
    unittest.main()
