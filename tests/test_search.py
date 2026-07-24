"""
云观星传 - 统一搜索服务单元测试
验证搜索结果合并、去重、格式化（Mock 搜索引擎，不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


class TestSearchSource:
    """SearchSource 数据类测试"""

    def test_to_dict_basic(self):
        """to_dict 应返回完整字段"""
        from src.search.tavily_search import SearchSource
        s = SearchSource(
            url="https://example.com",
            title="测试标题",
            content="测试内容",
            score=0.95,
            source="TavilySearch",
        )
        d = s.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "测试标题"
        assert d["content"] == "测试内容"
        assert d["score"] == 0.95
        assert d["source"] == "TavilySearch"

    def test_to_dict_truncates_long_content(self):
        """to_dict 应截断超过 300 字符的内容"""
        from src.search.tavily_search import SearchSource
        s = SearchSource(url="", title="", content="x" * 500)
        d = s.to_dict()
        assert len(d["content"]) == 300

    def test_to_dict_empty_content(self):
        """空内容应返回空字符串"""
        from src.search.tavily_search import SearchSource
        s = SearchSource(url="", title="", content="")
        d = s.to_dict()
        assert d["content"] == ""

    def test_default_source_is_tavily(self):
        """默认 source 应为 TavilySearch"""
        from src.search.tavily_search import SearchSource
        s = SearchSource(url="http://a.com", title="A")
        assert s.source == "TavilySearch"


class TestUnifiedSearchFormat:
    """UnifiedSearchService.format_search_context 格式化测试"""

    @pytest.fixture
    def service(self):
        """创建带 Mock 的 UnifiedSearchService"""
        with patch('src.search.unified_search.get_search_service') as mock_tavily, \
             patch('src.search.unified_search.QwenWebSearchService') as mock_qwen:
            mock_tavily.return_value = MagicMock()
            mock_qwen.return_value = MagicMock()
            from src.search.unified_search import UnifiedSearchService
            svc = UnifiedSearchService()
            return svc

    def test_empty_sources_returns_empty(self, service):
        """空列表应返回空字符串"""
        result = service.format_search_context([])
        assert result == ""

    def test_formats_sources_correctly(self, service):
        """应正确格式化搜索来源"""
        from src.search.tavily_search import SearchSource
        sources = [
            SearchSource(url="https://a.com", title="来源A",
                         content="内容A", source="TavilySearch"),
            SearchSource(url="https://b.com", title="来源B",
                         content="内容B", source="QwenWebSearch"),
        ]
        result = service.format_search_context(sources)
        assert "联网搜索内容" in result
        assert "[1]" in result
        assert "[2]" in result
        assert "来源A" in result
        assert "https://a.com" in result
        assert "[TavilySearch]" in result
        assert "[QwenWebSearch]" in result

    def test_limits_to_12_sources(self, service):
        """最多格式化 12 条来源"""
        from src.search.tavily_search import SearchSource
        sources = [
            SearchSource(url=f"https://{i}.com", title=f"来源{i}")
            for i in range(20)
        ]
        result = service.format_search_context(sources)
        assert "[12]" in result
        assert "[13]" not in result


class TestUnifiedSearchMerge:
    """UnifiedSearchService.search_for_topic 合并去重测试"""

    @pytest.fixture
    def service(self):
        """创建带 Mock 搜索引擎的 UnifiedSearchService"""
        with patch('src.search.unified_search.get_search_service') as mock_get_tavily, \
             patch('src.search.unified_search.QwenWebSearchService') as MockQwen:
            mock_tavily_instance = MagicMock()
            mock_qwen_instance = MockQwen.return_value
            mock_get_tavily.return_value = mock_tavily_instance

            from src.search.unified_search import UnifiedSearchService
            svc = UnifiedSearchService()
            svc.tavily = mock_tavily_instance
            svc.qwen = mock_qwen_instance
            return svc

    def test_merges_both_engines(self, service):
        """应合并两个引擎的结果"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://tavily.com/1", title="Tavily结果1", content="t1"),
        ]
        service.qwen.search_for_topic.return_value = [
            {"url": "https://qwen.com/1", "title": "Qwen结果1", "snippet": "q1"},
        ]

        results = service.search_for_topic("嫦娥六号")
        assert len(results) == 2
        sources = {r.source for r in results}
        assert "TavilySearch" in sources
        assert "QwenWebSearch" in sources

    def test_deduplicates_by_url(self, service):
        """相同 URL 应去重"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://same.com", title="Tavily版", content="t"),
        ]
        service.qwen.search_for_topic.return_value = [
            {"url": "https://same.com", "title": "Qwen版", "snippet": "q"},
        ]

        results = service.search_for_topic("议题")
        # 相同 URL 只保留一条（Tavily 优先）
        assert len(results) == 1
        assert results[0].source == "TavilySearch"

    def test_tavily_failure_doesnt_break(self, service):
        """Tavily 失败不影响 Qwen 结果"""
        service.tavily.search_for_topic.side_effect = Exception("API超时")
        service.qwen.search_for_topic.return_value = [
            {"url": "https://qwen.com/1", "title": "Qwen结果", "snippet": "q"},
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 1
        assert results[0].source == "QwenWebSearch"

    def test_qwen_failure_doesnt_break(self, service):
        """Qwen 失败不影响 Tavily 结果"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://t.com", title="Tavily结果", content="t"),
        ]
        service.qwen.search_for_topic.side_effect = Exception("MCP连接失败")

        results = service.search_for_topic("议题")
        assert len(results) == 1
        assert results[0].source == "TavilySearch"

    def test_both_fail_returns_empty(self, service):
        """两个引擎都失败应返回空列表"""
        service.tavily.search_for_topic.side_effect = Exception("fail")
        service.qwen.search_for_topic.side_effect = Exception("fail")

        results = service.search_for_topic("议题")
        assert results == []

    def test_qwen_alternative_field_names(self, service):
        """Qwen 返回不同字段名时应兼容"""
        service.tavily.search_for_topic.return_value = []
        service.qwen.search_for_topic.return_value = [
            {"link": "https://alt.com", "name": "替代标题", "description": "替代摘要"},
            {"url": "https://text.com", "title": "文本标题", "text": "text字段内容"},
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 2
        assert results[0].url == "https://alt.com"
        assert results[0].title == "替代标题"
        assert results[1].content == "text字段内容"
