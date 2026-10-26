import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.rag import pipeline


class RagPipelineTests(unittest.TestCase):
    def test_ingest_document_reads_chunks_adds_source_and_calls_indexer(self):
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "公司法.txt"
            source_path.write_text("占位文件内容", encoding="utf-8")

            fake_store = object()
            with (
                patch.object(
                    pipeline,
                    "_convert_to_markdown",
                    return_value="# 第一章\n\n第一条 公司应当依法经营。\n\n第二条 股东依法享有权利。",
                ),
                patch.object(pipeline, "index_chunks") as index_chunks,
            ):
                result = pipeline.ingest_document(
                    str(source_path),
                    store=fake_store,
                    rag_namespace="company_law",
                    chunk_tokens=10,
                    overlap_tokens=0,
                )

        self.assertEqual(result["source_name"], "公司法.txt")
        self.assertEqual(result["chunk_count"], 2)
        self.assertEqual(result["rag_namespace"], "company_law")
        index_chunks.assert_called_once()
        call_kwargs = index_chunks.call_args.kwargs
        self.assertIs(call_kwargs["store"], fake_store)
        self.assertEqual(call_kwargs["rag_namespace"], "company_law")
        self.assertEqual(call_kwargs["source"], str(source_path.resolve()))
        self.assertEqual(
            [chunk["source_name"] for chunk in call_kwargs["chunks"]],
            ["公司法.txt", "公司法.txt"],
        )
        self.assertTrue(all(chunk["source"] == str(source_path.resolve()) for chunk in call_kwargs["chunks"]))

    def test_retrieve_knowledge_uses_configured_store_and_namespace(self):
        fake_store = object()
        fake_pipeline = {"store": fake_store, "collection_name": "test_collection"}

        with (
            patch.object(
                pipeline,
                "_get_configured_pipeline",
                return_value=(fake_pipeline, "employment_law"),
            ),
            patch.object(
                pipeline,
                "search_vectors_expanded",
                return_value=[{"content": "相关法条"}],
            ) as search,
        ):
            results = pipeline.retrieve_knowledge("劳动合同解除", top_k=3)

        self.assertEqual(results, [{"content": "相关法条"}])
        search.assert_called_once_with(
            store=fake_store,
            query="劳动合同解除",
            top_k=3,
            rag_namespace="employment_law",
        )


if __name__ == "__main__":
    unittest.main()
