"""
云观星传 - 经验池 SQLite 存储单元测试
验证经验记录、历史查询、相似度计算、趋势统计（使用临时数据库，不依赖 LLM）
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def store(tmp_path):
    """创建使用临时数据库的 ExperienceStore"""
    from src.knowledge.experience_store import ExperienceStore
    db_path = str(tmp_path / "test_experience.db")
    return ExperienceStore(db_path=db_path)


class TestLogExperience:
    """经验记录测试"""

    def test_log_and_retrieve(self, store):
        """记录经验后应能通过 topic 查回"""
        record_id = store.log_experience(
            topic="嫦娥六号",
            round_num=1,
            scores={"factual_accuracy": 80, "strategic_actionability": 75,
                    "audience_fit": 70, "cultural_sensitivity": 85,
                    "narrative_fluency": 90},
            feedback=[{"suggestion": "增加数据引用"}],
            passed=False,
            weak_dims=["audience_fit"],
        )
        assert record_id > 0

        history = store.get_topic_history("嫦娥六号")
        assert len(history) == 1
        assert history[0]["topic"] == "嫦娥六号"
        assert history[0]["round_num"] == 1
        assert history[0]["passed"] is False

    def test_multiple_records_same_topic(self, store):
        """同一议题多条记录应按时间排序"""
        store.log_experience("天问一号", 1, {"factual_accuracy": 60}, [], False)
        store.log_experience("天问一号", 2, {"factual_accuracy": 75}, [], False)
        store.log_experience("天问一号", 3, {"factual_accuracy": 85}, [], True)

        history = store.get_topic_history("天问一号")
        assert len(history) == 3
        # 轮次递增
        assert history[0]["round_num"] == 1
        assert history[2]["round_num"] == 3

    def test_empty_topic_returns_empty(self, store):
        """不存在的议题返回空列表"""
        history = store.get_topic_history("不存在的议题")
        assert history == []

    def test_scores_stored_as_json(self, store):
        """评分应以 JSON 格式存储"""
        scores = {"factual_accuracy": 88, "strategic_actionability": 72,
                  "audience_fit": 65, "cultural_sensitivity": 90,
                  "narrative_fluency": 78}
        store.log_experience("测试", 1, scores, [], False)

        history = store.get_topic_history("测试")
        assert history[0]["scores"] == scores


class TestCosineSimilarity:
    """余弦相似度计算"""

    def test_identical_vectors(self):
        """相同向量相似度为 1"""
        from src.knowledge.experience_store import ExperienceStore
        result = ExperienceStore._cosine_similarity([1, 2, 3], [1, 2, 3])
        assert abs(result - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        """正交向量相似度为 0"""
        from src.knowledge.experience_store import ExperienceStore
        result = ExperienceStore._cosine_similarity([1, 0], [0, 1])
        assert abs(result) < 1e-6

    def test_opposite_vectors(self):
        """反向向量相似度为 -1"""
        from src.knowledge.experience_store import ExperienceStore
        result = ExperienceStore._cosine_similarity([1, 0], [-1, 0])
        assert abs(result - (-1.0)) < 1e-6

    def test_empty_vectors(self):
        """空向量返回 0"""
        from src.knowledge.experience_store import ExperienceStore
        assert ExperienceStore._cosine_similarity([], []) == 0.0

    def test_different_length_vectors(self):
        """不同长度向量返回 0"""
        from src.knowledge.experience_store import ExperienceStore
        assert ExperienceStore._cosine_similarity([1, 2], [1, 2, 3]) == 0.0

    def test_zero_vector(self):
        """零向量返回 0"""
        from src.knowledge.experience_store import ExperienceStore
        assert ExperienceStore._cosine_similarity([0, 0], [1, 1]) == 0.0


class TestFallbackSimilarity:
    """字符串回退相似度"""

    def test_similar_topics_found(self, store):
        """有相似议题时应返回匹配结果"""
        store.log_experience("嫦娥六号月背采样", 1, {"factual_accuracy": 80}, [], False)
        store.log_experience("嫦娥五号月球采样", 1, {"factual_accuracy": 75}, [], False)
        store.log_experience("火星探测天问一号", 1, {"factual_accuracy": 70}, [], False)

        import sqlite3
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        results = store._fallback_similarity("嫦娥六号", 3, conn)
        conn.close()

        assert len(results) > 0
        # "嫦娥六号月背采样" 与 "嫦娥六号" 字符重叠最多
        assert results[0]["topic"] == "嫦娥六号月背采样"

    def test_no_stored_topics(self, store):
        """无历史数据时返回空"""
        import sqlite3
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        results = store._fallback_similarity("任何议题", 3, conn)
        conn.close()
        assert results == []


class TestFindSimilarTopics:
    """相似议题查找（无 embedding 时回退到字符串匹配）"""

    def test_fallback_when_no_embeddings(self, store):
        """无 embedding 数据时应使用字符串匹配"""
        store.log_experience("嫦娥六号", 1, {"factual_accuracy": 80}, [], False)
        store.log_experience("嫦娥五号", 1, {"factual_accuracy": 75}, [], False)

        results = store.find_similar_topics("嫦娥六号返回器", top_k=2)
        assert len(results) > 0
        assert all("topic" in r and "similarity" in r for r in results)


class TestImprovementTrend:
    """全局改进趋势统计"""

    def test_empty_db_returns_zeros(self, store):
        """空数据库应返回零值统计"""
        trend = store.get_improvement_trend()
        assert trend["total_runs"] == 0
        assert trend["topics_count"] == 0

    def test_trend_with_data(self, store):
        """有数据时应返回正确统计"""
        store.log_experience("议题A", 1, {"factual_accuracy": 60, "strategic_actionability": 60,
                                          "audience_fit": 60, "cultural_sensitivity": 60,
                                          "narrative_fluency": 60}, [], False)
        store.log_experience("议题A", 2, {"factual_accuracy": 80, "strategic_actionability": 80,
                                          "audience_fit": 80, "cultural_sensitivity": 80,
                                          "narrative_fluency": 80}, [], True)
        store.log_experience("议题B", 1, {"factual_accuracy": 70, "strategic_actionability": 70,
                                          "audience_fit": 70, "cultural_sensitivity": 70,
                                          "narrative_fluency": 70}, [], False)

        trend = store.get_improvement_trend()
        assert trend["total_runs"] == 3
        assert trend["topics_count"] == 2


# ══════════════════════════════════════════════════════════════
# 以下为补充测试：历史查询 / embedding 向量相似 / 弱点统计 / 单例
# ══════════════════════════════════════════════════════════════
import json


class TestGetTopicHistory:
    """议题历史查询测试"""

    def test_sorted_and_parsed(self, store):
        store.log_experience("嫦娥六号", 1, {"factual_accuracy": 80}, [], passed=False,
                             weak_dims=["factual_accuracy"])
        store.log_experience("嫦娥六号", 2, {"factual_accuracy": 90}, [], passed=True,
                             weak_dims=[])
        history = store.get_topic_history("嫦娥六号")
        assert len(history) == 2
        # 时间升序：round 1 在前
        assert history[0]["round_num"] == 1
        assert history[1]["passed"] is True
        # JSON 字段被解析
        assert history[0]["scores"]["factual_accuracy"] == 80

    def test_other_topic_not_included(self, store):
        store.log_experience("天问三号", 1, {}, [], passed=False, weak_dims=[])
        assert store.get_topic_history("嫦娥六号") == []


class TestEmbeddingSimilarity:
    """embedding 向量相似查找测试"""

    def _seed(self, store, topic, vec):
        store.store_topic_embedding(topic, vec)
        store.log_experience(topic, 1, {"factual_accuracy": 75}, [], passed=True, weak_dims=[])

    def test_vector_based_find(self, store):
        """有 embedding 时应按余弦相似度排序"""
        self._seed(store, "嫦娥六号", [1.0, 0.0, 0.0])
        self._seed(store, "长征五号", [0.0, 1.0, 0.0])
        with patch.object(store, '_get_or_compute_embedding', return_value=[0.9, 0.1, 0.0]):
            similar = store.find_similar_topics("月背采样", top_k=2)
        assert similar[0]["topic"] == "嫦娥六号"  # 与 [1,0,0] 更近
        assert similar[0]["similarity"] > 0.9
        assert similar[1]["topic"] == "长征五号"

    def test_self_topic_excluded(self, store):
        self._seed(store, "嫦娥六号", [1.0, 0.0])
        with patch.object(store, '_get_or_compute_embedding', return_value=[1.0, 0.0]):
            similar = store.find_similar_topics("嫦娥六号")
        assert all(s["topic"] != "嫦娥六号" for s in similar)

    def test_no_query_embedding_falls_back(self, store):
        self._seed(store, "嫦娥六号", [1.0, 0.0])
        with patch.object(store, '_get_or_compute_embedding', return_value=None):
            similar = store.find_similar_topics("嫦娥六号")
        assert isinstance(similar, list)

    def test_best_score_attached(self, store):
        self._seed(store, "天问三号", [1.0, 0.0])
        store.log_experience("天问三号", 2, {"factual_accuracy": 95}, [], passed=True, weak_dims=[])
        with patch.object(store, '_get_or_compute_embedding', return_value=[0.8, 0.2]):
            similar = store.find_similar_topics("嫦娥六号", top_k=1)
        # best_score = 加权总分 = 95×0.3（事实准确度权重）
        assert similar[0]["best_score"] == 28.5


class TestGetOrComputeEmbedding:
    """embedding 获取/计算测试"""

    def test_cached_returns_stored(self, store):
        store.store_topic_embedding("嫦娥六号", [0.5, 0.5])
        assert store._get_or_compute_embedding("嫦娥六号") == [0.5, 0.5]

    def test_compute_and_cache(self, store):
        """未缓存时应调用 LLM 计算并入库"""
        with patch('src.llm_client.get_llm_client') as mock_get:
            mock_get.return_value.get_embedding.return_value = [0.1, 0.9]
            emb = store._get_or_compute_embedding("新议题")
        assert emb == [0.1, 0.9]
        # 已入库：二次查询命中缓存
        assert store._get_or_compute_embedding("新议题") == [0.1, 0.9]

    def test_llm_failure_returns_none(self, store):
        with patch('src.llm_client.get_llm_client',
                   side_effect=RuntimeError("LLM down")):
            assert store._get_or_compute_embedding("议题") is None

    def test_embedding_none_returns_none(self, store):
        mock_client = MagicMock()
        mock_client.get_embedding.return_value = None
        with patch('src.llm_client.get_llm_client', return_value=mock_client):
            assert store._get_or_compute_embedding("议题") is None


class TestCommonWeaknesses:
    """弱点统计测试"""

    def test_aggregates_dims(self, store):
        store.log_experience("议题A", 1, {"factual_accuracy": 50, "narrative_fluency": 60},
                             [], passed=False, weak_dims=["factual_accuracy", "narrative_fluency"])
        store.log_experience("议题B", 1, {"factual_accuracy": 40}, [],
                             passed=False, weak_dims=["factual_accuracy"])
        weak = store.get_common_weaknesses()
        fa = next(w for w in weak if w["dimension"] == "factual_accuracy")
        assert fa["count"] == 2
        assert fa["avg_score"] == 45.0  # (50+40)/2
        # 按 count 降序：factual_accuracy 排最前
        assert weak[0]["dimension"] == "factual_accuracy"

    def test_limit(self, store):
        for i in range(5):
            store.log_experience(f"议题{i}", 1, {"factual_accuracy": 50}, [],
                                 passed=False, weak_dims=["factual_accuracy"])
        store.log_experience("议题X", 1, {"narrative_fluency": 40}, [],
                             passed=False, weak_dims=["narrative_fluency"])
        weak = store.get_common_weaknesses(limit=1)
        assert len(weak) == 1
        assert weak[0]["dimension"] == "factual_accuracy"

    def test_empty_returns_empty(self, store):
        assert store.get_common_weaknesses() == []


class TestRowToDict:
    """数据库行转换测试"""

    @staticmethod
    def _make_row(topic, scores, weak, feedback, passed):
        """经真实 sqlite 连接构造 Row（sqlite3.Row 不可直接实例化）"""
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT ? AS topic, ? AS scores_json, ? AS weak_dims_json,"
            " ? AS feedback_json, ? AS passed",
            (topic, scores, weak, feedback, passed),
        ).fetchone()
        conn.close()
        return row

    def test_json_fields_parsed(self):
        from src.knowledge.experience_store import ExperienceStore
        row = self._make_row("议题", '{"factual_accuracy": 80}', '["x"]', "[]", 1)
        d = ExperienceStore._row_to_dict(row)
        assert d["scores"] == {"factual_accuracy": 80}
        assert d["weak_dims"] == ["x"]
        assert d["passed"] is True

    def test_corrupt_json_defaults(self):
        from src.knowledge.experience_store import ExperienceStore
        row = self._make_row("议题", "{bad", '["x"]', "[]", 0)
        d = ExperienceStore._row_to_dict(row)
        assert d["scores"] == {}


class TestSingleton:
    """全局单例测试"""

    def test_get_experience_store_singleton(self):
        from src.knowledge import experience_store as es_mod
        prev = es_mod._store
        try:
            es_mod._store = None
            s1 = es_mod.get_experience_store()
            s2 = es_mod.get_experience_store()
            assert s1 is s2
        finally:
            es_mod._store = prev
