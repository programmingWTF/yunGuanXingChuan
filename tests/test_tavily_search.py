"""
云观星传 - Tavily 搜索服务单元测试
覆盖客户端初始化、REST 调用解析、议题多查询去重、上下文格式化与单例（Mock HTTP，不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def service():
    """创建带 mock httpx 客户端的 Tavily 服务实例"""
    from src.search.tavily_search import TavilySearchService
    svc = TavilySearchService(api_key="tvly-test")
    svc._http_client = MagicMock()
    return svc


class TestClientInit:
    """httpx 客户端延迟初始化测试"""

    def test_no_api_key_returns_none(self):
        """未配置 api_key 时应返回 None 并降级"""
        from src.search.tavily_search import TavilySearchService
        svc = TavilySearchService(api_key=None)
        svc.api_key = None
        assert svc._get_http_client() is None

    def test_lazy_init_with_key(self):
        """有 key 时应创建客户端并缓存"""
        from src.search.tavily_search import TavilySearchService
        svc = TavilySearchService(api_key="k")
        svc._http_client = None
        with patch('httpx.Client') as MockClient:
            MockClient.return_value = MagicMock()
            client = svc._get_http_client()
            assert client is MockClient.return_value
            assert svc._get_http_client() is client
            MockClient.assert_called_once()


class TestSearch:
    """REST API 调用测试"""

    def test_no_client_returns_empty(self):
        """无客户端应返回空列表"""
        from src.search.tavily_search import TavilySearchService
        svc = TavilySearchService(api_key="k")
        with patch.object(svc, '_get_http_client', return_value=None):
            assert svc.search("query") == []

    def test_search_parses_results(self, service):
        """应解析 Tavily 响应为 SearchSource 列表"""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "results": [
                {"url": "https://a.com", "title": "A", "content": "内容A", "score": 0.92},
                {"url": "https://b.com", "title": "B", "content": "内容B", "score": 0.55},
            ]
        }
        service._http_client.post.return_value = resp
        results = service.search("嫦娥六号", max_results=2, search_depth="advanced")
        assert len(results) == 2
        assert results[0].url == "https://a.com"
        assert results[0].score == 0.92
        assert results[0].source == "TavilySearch"
        # 请求体字段校验
        payload = service._http_client.post.call_args.kwargs["json"]
        assert payload["query"] == "嫦娥六号"
        assert payload["max_results"] == 2
        assert payload["search_depth"] == "advanced"
        assert payload["api_key"] == "tvly-test"

    def test_search_missing_fields_default(self, service):
        """响应缺字段时应使用默认值不崩溃"""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"results": [{"url": "https://a.com"}]}
        service._http_client.post.return_value = resp
        results = service.search("q")
        assert len(results) == 1
        assert results[0].title == ""
        assert results[0].score == 0.0

    def test_search_error_returns_empty(self, service):
        """网络/解析异常应返回空列表而非抛出"""
        service._http_client.post.side_effect = ConnectionError("timeout")
        assert service.search("q") == []

    def test_search_http_error_returns_empty(self, service):
        """HTTP 错误状态（raise_for_status 抛出）应返回空列表"""
        resp = MagicMock()
        resp.raise_for_status.side_effect = RuntimeError("401 unauthorized")
        service._http_client.post.return_value = resp
        assert service.search("q") == []


class TestSearchForTopic:
    """议题多角度搜索测试"""

    def test_dedup_by_url(self, service):
        """相同 URL 的来源应去重"""
        from src.search.tavily_search import SearchSource
        batch = [
            SearchSource(url="https://same.com/1", title="A"),
            SearchSource(url="https://same.com/1", title="A-dup"),
            SearchSource(url="https://new.com/2", title="B"),
        ]
        with patch.object(service, 'search', side_effect=[batch[:2], batch[2:], []]):
            merged = service.search_for_topic("嫦娥六号")
        urls = [s.url for s in merged]
        assert urls.count("https://same.com/1") == 1
        assert len(merged) == 2

    def test_empty_url_entries_dropped(self, service):
        """空 URL 的条目不应进入合并结果"""
        from src.search.tavily_search import SearchSource
        batch = [
            SearchSource(url="", title="无链接"),
            SearchSource(url="https://x.com", title="有链接"),
        ]
        with patch.object(service, 'search', side_effect=[batch, [], []]):
            merged = service.search_for_topic("议题")
        assert len(merged) == 1
        assert merged[0].url == "https://x.com"


class TestFormatSearchContext:
    """搜索上下文格式化测试（tavily 模块内实现）"""

    def test_empty_returns_empty(self, service):
        """空列表应返回空字符串"""
        assert service.format_search_context([]) == ""

    def test_formats_title_url_content(self, service):
        """应包含标题、来源 URL 与摘要"""
        from src.search.tavily_search import SearchSource
        s = SearchSource(url="https://a.com", title="标题A", content="摘要内容", source="TavilySearch")
        text = service.format_search_context([s])
        assert "标题A" in text
        assert "https://a.com" in text
        assert "摘要内容" in text
        assert "[TavilySearch]" in text

    def test_limits_to_12_sources(self, service):
        """超过 12 条时应截断"""
        from src.search.tavily_search import SearchSource
        sources = [SearchSource(url=f"https://x.com/{i}", title=f"T{i}") for i in range(20)]
        text = service.format_search_context(sources)
        assert "[12]" in text
        assert "[13]" not in text


class TestSingleton:
    """全局单例测试"""

    def test_get_search_service_singleton(self):
        """get_search_service 应返回同一实例"""
        import src.search.tavily_search as mod
        prev = mod._search_service
        try:
            mod._search_service = None
            s1 = mod.get_search_service()
            s2 = mod.get_search_service()
            assert s1 is s2
        finally:
            mod._search_service = prev
