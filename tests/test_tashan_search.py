"""
云观星传 - 他山世界搜索服务测试

覆盖不依赖网络的纯逻辑：查询词扩展、结果结构判断、无 token 降级、单例。
（联网部分由 _safe_call 统一降级，不在此测试真实 HTTP）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch

from src.search.tashan_search import (
    TashanSearchService,
    _has_results,
    get_tashan_search_service,
)


class TestExpandQueries:
    def test_chinese_lunar_topic_adds_variant(self):
        queries = TashanSearchService.expand_queries("嫦娥六号")
        assert queries[0] == "嫦娥六号"
        assert "月球探测 国际合作" in queries

    def test_space_topic_adds_commercial_variant(self):
        queries = TashanSearchService.expand_queries("商业火箭发射")
        assert queries[0] == "商业火箭发射"
        assert "商业航天 国际报道" in queries

    def test_extra_queries_appended(self):
        queries = TashanSearchService.expand_queries("嫦娥六号", extra_queries=["月球背面", "月球背面"])
        # 去重
        assert queries.count("月球背面") == 1
        assert "月球背面" in queries

    def test_dedup_and_limit_4(self):
        queries = TashanSearchService.expand_queries(
            "嫦娥六号", extra_queries=["月球背面", "国际月球科研站", "中法航天合作", "月壤研究"]
        )
        assert len(queries) <= 4
        assert len(queries) == len(set(queries))

    def test_empty_extra_ignored(self):
        queries = TashanSearchService.expand_queries("嫦娥六号", extra_queries=["", "  "])
        assert len(queries) >= 1


class TestHasResults:
    def test_none_and_non_dict(self):
        assert _has_results(None) is False
        assert _has_results([]) is False
        assert _has_results("text") is False

    def test_empty_dict(self):
        assert _has_results({}) is False

    def test_with_data(self):
        assert _has_results({"list": [1]}) is True
        assert _has_results({"signals": {"a": 1}}) is True
        assert _has_results({"papers": ["p"]}) is True
        assert _has_results({"data": []}) is False  # 空列表不算有数据


class TestSearchForTopicDegrade:
    def test_without_token_skips_aminer(self):
        """无 token：不调用 _search_aminer；其余子模块失败时整体降级为空结果"""
        svc = TashanSearchService(token="")
        with patch.object(svc, "_search_world_weave", return_value=[]), \
             patch.object(svc, "_search_literature_recent", return_value=[]), \
             patch.object(svc, "_search_world_signals", return_value=[]), \
             patch.object(svc, "_search_source_feed", return_value=[]), \
             patch.object(svc, "_search_aminer", side_effect=AssertionError("无 token 不应调用 AMiner")) as m_aminer:
            results = svc.search_for_topic("嫦娥六号")
            m_aminer.assert_not_called()
            assert results == []

    def test_safe_call_catches_exceptions(self):
        """_safe_call 捕获子模块异常并降级为空列表"""
        def boom(*_a, **_k):
            raise RuntimeError("network down")
        assert TashanSearchService._safe_call(boom, "x") == []


class TestSingleton:
    def test_get_service_returns_instance(self):
        svc = get_tashan_search_service()
        assert isinstance(svc, TashanSearchService)
        svc2 = get_tashan_search_service()
        assert svc is svc2
