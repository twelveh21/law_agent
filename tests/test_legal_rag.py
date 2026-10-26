import unittest

from langchain_core.documents import Document

from app.common.legal_rag import make_chunk_ids, split_legal_documents


class SplitLegalDocumentsTests(unittest.TestCase):
    def test_splits_articles_and_keeps_citation_metadata(self):
        source = Document(
            page_content="目录内容\n\n第一条 本法用于规范公司行为。\n\n第二条 公司是企业法人。",
            metadata={"source": "D:/laws/公司法.txt"},
        )

        chunks = split_legal_documents([source], chunk_size=500, chunk_overlap=50)

        self.assertEqual([chunk.metadata["article"] for chunk in chunks], ["第一条", "第二条"])
        self.assertTrue(all(chunk.metadata["source_name"] == "公司法.txt" for chunk in chunks))
        self.assertTrue(all("目录内容" not in chunk.page_content for chunk in chunks))

    def test_long_article_chunks_keep_the_same_article_number(self):
        source = Document(
            page_content="第一条 " + "公司及股东的权利义务。" * 100,
            metadata={"source": "劳动法.txt"},
        )

        chunks = split_legal_documents([source], chunk_size=80, chunk_overlap=10)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.metadata["article"] == "第一条" for chunk in chunks))

    def test_recognizes_articles_without_spaces_and_supplementary_numbers(self):
        source = Document(
            page_content="第一条为了测试无空格条文。\n第六百八十七条之一新增条文。",
            metadata={"source": "测试法.txt"},
        )

        chunks = split_legal_documents([source])

        self.assertEqual(
            [chunk.metadata["article"] for chunk in chunks],
            ["第一条", "第六百八十七条之一"],
        )

    def test_documents_without_article_headers_are_still_indexed(self):
        source = Document(
            page_content="这是一份没有标准法条编号的材料。" * 10,
            metadata={"source": "说明.txt"},
        )

        chunks = split_legal_documents([source])

        self.assertTrue(chunks)
        self.assertTrue(all(chunk.metadata["article"] == "未识别" for chunk in chunks))

    def test_chunk_ids_are_stable(self):
        source = Document(
            page_content="第一条 本法用于测试。",
            metadata={"source": "测试法.txt"},
        )
        chunks = split_legal_documents([source])

        self.assertEqual(make_chunk_ids(chunks), make_chunk_ids(chunks))


if __name__ == "__main__":
    unittest.main()
