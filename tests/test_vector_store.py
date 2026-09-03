"""
云观星传 - 向量存储单元测试
覆盖文本分块、索引构建（真实 FAISS + mock embedding）、语义检索、四库过滤、
断言校验分级与索引持久化（不依赖网络）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# faiss/numpy 在依赖中真实可用，无需 mock


@pytest.fixture
def store(tmp_path, monkeypatch):
    """创建隔离的向量存储（mock LLM embedding 客户端）"""
    from src.knowledge.vector_store import VectorStore
    with patch('src.knowledge.vector_store.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        s = VectorStore(dimension=8, index_path=tmp_path / "vectors.faiss")
        s.llm_client = mock_client
        yield s


def _vec(seed: float, dim: int = 8):
    """构造可复现的归一化向量"""
    import numpy as np
    v = np.full(dim, seed, dtype=np.float32)
    v[0] = 1.0
    n = np.linalg.norm(v)
    return (v / n).tolist()


class TestChunkText:
    """文本分块测试"""

    def test_short_text_single_chunk(self, store):
        chunks = store.chunk_text("嫦娥六号月球采样返回")
        assert len(chunks) == 1
        assert chunks[0]["text"] == "嫦娥六号月球采样返回"
        assert chunks[0]["chunk_id"] == 0

    def test_long_text_multiple_chunks_with_overlap(self, store):
        """长文本应分块且相邻块有重叠"""
        text = "月" * 1000
        chunks = store.chunk_text(text, chunk_size=400, overlap=50)
        assert len(chunks) >= 3
        # 重叠验证：第二块开头应与第一块结尾部分相同
        assert chunks[1]["text"][:50] == chunks[0]["text"][-50:]

    def test_metadata_attached(self, store):
        chunks = store.chunk_text("内容", metadata={"source": "test.json", "type": "science_fact"})
        assert chunks[0]["metadata"]["source"] == "test.json"
        assert chunks[0]["metadata"]["type"] == "science_fact"

    def test_whitespace_chunks_skipped(self, store):
        """纯空白块应被跳过"""
        text = "有效内容" + " " * 500 + "结尾内容"
        chunks = store.chunk_text(text, chunk_size=100, overlap=0)
        assert all(c["text"].strip() for c in chunks)

    def test_overlap_ge_chunk_size_no_infinite_loop(self, store):
        """overlap >= chunk_size 时参数保护应防止死循环"""
        chunks = store.chunk_text("x" * 300, chunk_size=100, overlap=200)
        assert len(chunks) >= 1  # 能正常返回即通过

    def test_empty_text(self, store):
        assert store.chunk_text("") == []


class TestBuildIndex:
    """索引构建测试（真实 FAISS）"""

    def test_build_with_documents(self, store):
        docs = [
            {"text": "嫦娥六号实现人类首次月球背面采样返回", "source": "science", "type": "science_fact"},
            {"text": "长征五号是大型运载火箭", "source": "science", "type": "science_fact"},
        ]
        store.llm_client.get_embeddings_batch.return_value = [_vec(0.1), _vec(0.5)]
        store.build_index(documents=docs)
        assert store.index is not None
        assert store.index.ntotal == 2
        assert len(store.documents) == 2
        # 索引已落盘
        assert store.index_path.exists()

    def test_dimension_autodetected(self, store):
        """实际 embedding 维度应覆盖初始设置"""
        docs = [{"text": "内容", "source": "s"}]
        store.llm_client.get_embeddings_batch.return_value = [_vec(0.1, dim=16)]
        store.build_index(documents=docs)
        assert store.dimension == 16

    def test_empty_documents_noop(self, store):
        store.build_index(documents=[])
        assert store.index is None

    def test_no_chunks_noop(self, store):
        """全空白文本分块后无有效块"""
        store.build_index(documents=[{"text": "   ", "source": "s"}])
        assert store.index is None


class TestEmbeddingsBatch:
    """批量向量化测试"""

    def test_batch_success(self, store):
        store.llm_client.get_embeddings_batch.return_value = [_vec(0.1), _vec(0.2)]
        embs = store._get_embeddings_batch(["a", "b"])
        assert len(embs) == 2

    def test_batch_failure_falls_back_per_item(self, store):
        """批量失败应逐条重试"""
        store.llm_client.get_embeddings_batch.side_effect = RuntimeError("batch fail")
        store.llm_client.get_embedding.return_value = _vec(0.3)
        embs = store._get_embeddings_batch(["a"])
        assert len(embs) == 1
        assert embs[0] is not None

    def test_all_fail_zero_vectors(self, store):
        """逐条也失败时降级为零向量"""
        store.llm_client.get_embeddings_batch.side_effect = RuntimeError("batch fail")
        store.llm_client.get_embedding.side_effect = RuntimeError("single fail")
        embs = store._get_embeddings_batch(["a", "b"])
        assert embs == [[0.0] * 8, [0.0] * 8]


class TestSearch:
    """语义检索测试"""

    def _build(self, store, libraries):
        docs = [
            {"text": f"文档{i}", "source": f"s{i}", "type": "t", "library": lib}
            for i, lib in enumerate(libraries)
        ]
        store.llm_client.get_embeddings_batch.return_value = [_vec(0.1 + i * 0.2) for i in range(len(docs))]
        store.build_index(documents=docs)
        # 重置调用记录，控制查询向量
        store.llm_client.get_embedding.reset_mock()

    def test_search_returns_topk(self, store):
        self._build(store, ["theory", "method", "theory"])
        store.llm_client.get_embedding.return_value = _vec(0.1)  # 与文档0最相似
        results = store.search("查询", top_k=2)
        assert 1 <= len(results) <= 2
        assert all("text" in r and "score" in r and "metadata" in r for r in results)
        # 最相似文档排第一
        assert results[0]["metadata"]["source"] == "s0"

    def test_search_library_filter(self, store):
        """library 过滤应只返回对应库的文档"""
        self._build(store, ["theory", "method", "theory"])
        store.llm_client.get_embedding.return_value = _vec(0.1)
        results = store.search("查询", top_k=5, library="method")
        assert len(results) == 1
        assert results[0]["metadata"]["library"] == "method"

    def test_search_empty_index_returns_empty(self, store):
        """空索引应返回空列表（自动构建失败后）"""
        with patch.object(store, '_load_index', return_value=False), \
             patch.object(store, 'build_index'):
            # build_index 被 mock 不做事，索引仍为空
            assert store.search("查询") == []

    def test_search_no_embedding_returns_empty(self, store):
        self._build(store, ["theory"])
        store.llm_client.get_embedding.return_value = []
        assert store.search("查询") == []


class TestVerifyClaim:
    """断言校验分级测试"""

    def _search_result(self, score, text="证据文本", source="src"):
        return [{"text": text, "score": score, "metadata": {"source": source}}]

    def test_supported(self, store):
        with patch.object(store, 'search', return_value=self._search_result(0.85)):
            r = store.verify_claim("嫦娥六号月背采样", threshold=0.6)
        assert r["status"] == "supported"
        assert r["confidence"] == 0.85
        assert r["evidence"] == "证据文本"

    def test_partial(self, store):
        """score 落在 [threshold*0.7, threshold) 应为 partial"""
        with patch.object(store, 'search', return_value=self._search_result(0.5)):
            r = store.verify_claim("断言", threshold=0.6)
        assert r["status"] == "partial"

    def test_unverified_low_score(self, store):
        with patch.object(store, 'search', return_value=self._search_result(0.1)):
            r = store.verify_claim("断言", threshold=0.6)
        assert r["status"] == "unverified"
        assert "相关度不足" in r["message"]

    def test_no_results(self, store):
        with patch.object(store, 'search', return_value=[]):
            r = store.verify_claim("断言")
        assert r["status"] == "unverified"
        assert r["confidence"] == 0.0
        assert r["evidence"] is None


class TestIndexPersistence:
    """索引持久化测试"""

    def test_save_and_load_roundtrip(self, store):
        docs = [{"text": "持久化测试文档", "source": "s", "type": "t"}]
        store.llm_client.get_embeddings_batch.return_value = [_vec(0.2)]
        store.build_index(documents=docs)
        assert store.index_path.exists()

        # 新实例从磁盘加载
        with patch('src.knowledge.vector_store.get_llm_client') as mock_get:
            mock_get.return_value = MagicMock()
            from src.knowledge.vector_store import VectorStore as VS
            loaded = VS(dimension=8, index_path=store.index_path)
            assert loaded._load_index() is True
            assert loaded.index is not None
            assert loaded.index.ntotal == 1
            assert len(loaded.documents) == 1

    def test_load_missing_index_false(self, store):
        assert store._load_index() is False


class TestLoadAllDocuments:
    """全量文档加载测试（仓库内置 data/）"""

    def test_loads_builtin_data(self, store):
        docs = store._load_all_documents()
        # 仓库内置科学/媒体/受众数据应被加载
        assert len(docs) > 0
        types = {d.get("type") for d in docs}
        assert "science_fact" in types
        assert "media_report" in types
