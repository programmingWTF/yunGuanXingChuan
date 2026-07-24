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
