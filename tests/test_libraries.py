"""
云观星传 - 知识库四库化测试（Issue #49）
覆盖：四库定义 / 库名校验 / 种子文档读取 / 分库检索过滤 / ingest library 元数据 / API
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖（faiss 未装时兜底；httpx 为真包，starlette.testclient 需要真实实现）
for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

from src.knowledge.libraries import (
    LIBRARY_TYPES, VALID_LIBRARIES, LIBRARIES_DIR,
    is_valid_library, get_library_meta_list,
    get_library_documents, search_library, get_library_stats,
)
from src.knowledge import libraries as libs_mod


class TestLibraryDefinition:
    def test_four_libraries(self):
        """四库定义齐全（对齐《智能体.docx》知识库依赖）"""
        assert set(LIBRARY_TYPES.keys()) == {"journal_article", "theory", "top_journal_example", "method"}
        assert LIBRARY_TYPES["method"]["name"] == "方法库"
        assert LIBRARY_TYPES["top_journal_example"]["stages"] == [3, 4, 6, 7]

    def test_valid_library_check(self):
        assert is_valid_library("method") is True
        assert is_valid_library("../../etc") is False
        assert is_valid_library("") is False

    def test_meta_list(self):
        metas = get_library_meta_list()
        assert len(metas) == 4
        assert {m["key"] for m in metas} == VALID_LIBRARIES


class TestSeedDocuments:
    def test_seed_files_exist(self):
        """每个库都有种子文档"""
        for key in LIBRARY_TYPES:
            docs = get_library_documents(key)
            assert len(docs) >= 1, f"库 {key} 缺少种子文档"
            for d in docs:
                assert d["library"] == key
                assert d["type"] == "library"
                assert d["text"].strip()

    def test_method_library_has_content_analysis(self):
        """方法库应包含内容分析操作指南"""
        docs = get_library_documents("method")
        all_text = "\n".join(d["text"] for d in docs)
        assert "内容分析" in all_text
        assert "框架分析" in all_text

    def test_invalid_library_no_docs(self):
        assert get_library_documents("evil") == []


class TestSearchLibrary:
    def test_search_filters_by_library(self):
        """分库检索：只返回该库的命中（mock 候选池）"""
        vs = MagicMock()
        vs.search.return_value = [
            {"text": "内容分析操作步骤", "score": 0.9, "metadata": {"library": "method"}},
        ]
        with patch("src.knowledge.libraries.get_vector_store", return_value=vs):
            results = search_library("编码", "method", top_k=3)
            vs.search.assert_called_once_with("编码", top_k=3, library="method")
            assert results[0]["metadata"]["library"] == "method"

    def test_search_invalid_library_raises(self):
        with pytest.raises(ValueError, match="非法库名"):
            search_library("q", "evil")

    def test_stats_structure(self):
        with patch("src.knowledge.libraries.get_vector_store") as mock_get:
            vs = MagicMock()
            vs.documents = [
                {"metadata": {"library": "method"}},
                {"metadata": {"library": "method"}},
                {"metadata": {"library": "theory"}},
                {"metadata": {}},
            ]
            mock_get.return_value = vs
            stats = get_library_stats()
            assert len(stats) == 4
            by_key = {s["key"]: s for s in stats}
            assert by_key["method"]["chunk_count"] == 2
            assert by_key["theory"]["chunk_count"] == 1

    def test_build_index_with_library(self):
        """build_library_index 应给文档打 library 元数据并入索引"""
        vs = MagicMock()
        vs.documents = []
        with patch("src.knowledge.libraries.get_vector_store", return_value=vs), \
             patch("src.knowledge.libraries.get_library_documents") as mock_docs:
            mock_docs.return_value = [{"text": "方法文本", "library": "method", "source": "x.md", "title": "x"}]
            n = libs_mod.build_library_index("method")
            assert n == 1
            docs = vs.build_index.call_args[0][0]
            assert docs[-1]["library"] == "method"

    def test_build_index_invalid_library(self):
        with pytest.raises(ValueError, match="非法库名"):
            libs_mod.build_library_index("evil")


class TestIngestChunksLibrary:
    def test_ingest_chunks_with_library(self):
        """ingest_chunks 带 library 时写入库元数据且合并现有索引"""
        from src.knowledge.preprocessor import DocumentPreprocessor, DocumentChunk

        vs = MagicMock()
        vs.documents = [{"text": "旧块", "metadata": {"library": "theory", "source": "old", "title": "", "date": "", "type": ""}}]
        prep = DocumentPreprocessor()
        chunks = [DocumentChunk(text="新方法块", source="m.md", section="", date="", language="zh")]
        n = prep.ingest_chunks(chunks, vector_store=vs, library="method")
        assert n == 1
        docs = vs.build_index.call_args[0][0]
        # 合并保留旧块 + 新块带 library
        assert any(d["library"] == "theory" for d in docs)
        new_doc = [d for d in docs if d["library"] == "method"]
        assert len(new_doc) == 1
        assert new_doc[0]["type"] == "library"


class TestKnowledgeAPI:
    @pytest.fixture(autouse=True)
    def mock_vector_store(self):
        """CI 无 API key：mock 掉 get_vector_store，避免创建 LLM client 抛 Missing credentials"""
        vs = MagicMock()
        vs.documents = []
        vs.search.return_value = []
        with patch("src.knowledge.libraries.get_vector_store", return_value=vs):
            yield

    def test_libraries_endpoint(self):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            r = client.get("/api/knowledge/libraries")
            assert r.status_code == 200
            data = r.json()
            assert len(data["libraries"]) == 4
            assert len(data["stats"]) == 4

    def test_search_endpoint_validation(self):
        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            # 非法库名 → 400
            r = client.get("/api/knowledge/search", params={"library": "evil", "q": "x"})
            assert r.status_code == 400
            # 空关键词 → 400
            r = client.get("/api/knowledge/search", params={"library": "method", "q": ""})
            assert r.status_code == 400
