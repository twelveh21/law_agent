import unittest
from unittest.mock import patch

from app.rag.ingestion import indexing


class _FakeEmbedder:
    def embed_documents(self, texts):
        return [[float(index + 1), 0.5] for index, _ in enumerate(texts)]


class _FakeStore:
    def __init__(self):
        self.batches = []

    def upsert_points(self, points):
        self.batches.append(points)


class IndexChunksTests(unittest.TestCase):
    @patch("app.rag.ingestion.indexing.get_dimension", return_value=2)
    @patch("app.rag.ingestion.indexing.get_text_embedder", return_value=_FakeEmbedder())
    def test_index_chunks_builds_qdrant_points_and_writes_in_batches(
        self, _get_embedder, _get_dimension
    ):
        store = _FakeStore()
        chunks = [
            {
                "content": "第一条 这是第一段法律文本。",
                "heading_path": "第一章",
                "start": 0,
                "end": 15,
                "source": "公司法.pdf",
            },
            {
                "content": "第二条 这是第二段法律文本。",
                "heading_path": "第二章",
                "start": 16,
                "end": 31,
                "source": "公司法.pdf",
            },
            {
                "content": "第三条 这是第三段法律文本。",
                "heading_path": "第三章",
                "start": 32,
                "end": 47,
                "source": "公司法.pdf",
            },
        ]

        indexing.index_chunks(
            store=store,
            chunks=chunks,
            batch_size=2,
            rag_namespace="company_law",
        )

        self.assertEqual([len(batch) for batch in store.batches], [2, 1])
        first_point = store.batches[0][0]
        self.assertEqual(first_point["vector"], [1.0, 0.5])
        self.assertEqual(first_point["payload"]["content"], chunks[0]["content"])
        self.assertEqual(first_point["payload"]["metadata"]["source"], "公司法.pdf")
        self.assertEqual(first_point["payload"]["metadata"]["heading_path"], "第一章")
        self.assertEqual(first_point["payload"]["memory_type"], "rag_chunk")
        self.assertTrue(first_point["payload"]["is_rag_data"])
        self.assertEqual(first_point["payload"]["data_source"], "rag_pipeline")
        self.assertEqual(first_point["payload"]["rag_namespace"], "company_law")
        self.assertEqual(
            first_point["id"], first_point["payload"]["metadata"]["memory_id"]
        )

        # 相同资料再次导入时，稳定 ID 相同，Qdrant upsert 会更新同一条记录。
        indexing.index_chunks(
            store=store,
            chunks=chunks[:1],
            batch_size=2,
            rag_namespace="company_law",
        )
        self.assertEqual(store.batches[2][0]["id"], first_point["id"])


if __name__ == "__main__":
    unittest.main()
