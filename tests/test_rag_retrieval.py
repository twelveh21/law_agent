import importlib.util
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from app.rag.retrieval import search as retrieval
from app.rag.storage.qdrant import _QdrantStoreAdapter


class _FakeStore:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search_similar(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class SearchVectorsTests(unittest.TestCase):
    @patch("app.rag.retrieval.search._prompt_mqe", return_value=["合同违约责任"])
    @patch("app.rag.retrieval.search.embed_query", side_effect=[[0.1, 0.2], [0.3, 0.4]])
    def test_expanded_search_filters_merges_and_sorts_hits(
        self, _embed_query, _prompt_mqe
    ):
        store = _FakeStore(
            [
                [
                    {
                        "id": "point-a",
                        "content": "合同应当履行。",
                        "metadata": {"memory_id": "point-a", "source": "民法典.pdf"},
                        "score": 0.72,
                    },
                    {
                        "id": "point-b",
                        "content": "违约应承担责任。",
                        "metadata": {"memory_id": "point-b", "source": "民法典.pdf"},
                        "score": 0.81,
                    },
                ],
                [
                    {
                        "id": "point-a",
                        "content": "合同应当履行。",
                        "metadata": {"memory_id": "point-a", "source": "民法典.pdf"},
                        "score": 0.93,
                    }
                ],
            ]
        )

        results = retrieval.search_vectors_expanded(
            store=store,
            query="  合同  ",
            top_k=2,
            rag_namespace="civil_law",
            enable_mqe=True,
        )

        self.assertEqual([item["id"] for item in results], ["point-a", "point-b"])
        self.assertEqual(results[0]["score"], 0.93)
        self.assertEqual(len(store.calls), 2)
        self.assertEqual(store.calls[0]["query_vector"], [0.1, 0.2])
        self.assertEqual(
            store.calls[0]["where"],
            {
                "memory_type": "rag_chunk",
                "is_rag_data": True,
                "data_source": "rag_pipeline",
                "rag_namespace": "civil_law",
            },
        )

    def test_blank_query_returns_no_results_and_invalid_top_k_is_rejected(self):
        self.assertEqual(retrieval.search_vectors_expanded(query="  "), [])
        with self.assertRaisesRegex(ValueError, "top_k"):
            retrieval.search_vectors_expanded(query="合同", top_k=0)

    @unittest.skipUnless(importlib.util.find_spec("qdrant_client"), "qdrant-client 未安装")
    @patch("app.rag.retrieval.search.embed_query", return_value=[0.1, 0.2])
    def test_search_reads_payload_written_to_a_temporary_qdrant_collection(
        self, _embed_query
    ):
        from qdrant_client import QdrantClient, models

        with TemporaryDirectory() as temp_dir:
            client = QdrantClient(path=temp_dir)
            collection_name = "rag_retrieval_test"
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=2,
                    distance=models.Distance.COSINE,
                ),
            )
            store = _QdrantStoreAdapter(client, collection_name)
            point_id = str(uuid4())
            store.upsert_points(
                [
                    {
                        "id": point_id,
                        "vector": [0.1, 0.2],
                        "payload": {
                            "content": "合同当事人应当按照约定履行义务。",
                            "metadata": {
                                "source": "民法典.pdf",
                                "memory_id": point_id,
                            },
                            "memory_type": "rag_chunk",
                            "is_rag_data": True,
                            "data_source": "rag_pipeline",
                            "rag_namespace": "default",
                        },
                    }
                ]
            )

            results = retrieval.search_vectors_expanded(
                store=store,
                query="合同义务",
                rag_namespace="default",
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["id"], point_id)
            self.assertEqual(results[0]["content"], "合同当事人应当按照约定履行义务。")
            self.assertEqual(results[0]["metadata"]["source"], "民法典.pdf")
            client.close()


if __name__ == "__main__":
    unittest.main()
