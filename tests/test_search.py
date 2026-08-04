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
             patch('src.search.unified_search.QwenWebSearchService') as MockQwen, \
             patch('src.search.unified_search.get_tashan_search_service') as MockTashan:
            mock_tavily_instance = MagicMock()
            mock_qwen_instance = MockQwen.return_value
            mock_tashan_instance = MockTashan.return_value
            mock_get_tavily.return_value = mock_tavily_instance

            from src.search.unified_search import UnifiedSearchService
            svc = UnifiedSearchService()
            svc.tavily = mock_tavily_instance
            svc.qwen = mock_qwen_instance
            svc.tashan = mock_tashan_instance
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
        service.tashan.search_for_topic.return_value = []

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
        service.tashan.search_for_topic.return_value = []

        results = service.search_for_topic("议题")
        assert len(results) == 1
        assert results[0].source == "TavilySearch"

    def test_both_fail_returns_empty(self, service):
        """三个引擎都失败应返回空列表"""
        service.tavily.search_for_topic.side_effect = Exception("fail")
        service.qwen.search_for_topic.side_effect = Exception("fail")
        service.tashan.search_for_topic.side_effect = Exception("fail")

        results = service.search_for_topic("议题")
        assert results == []

    def test_qwen_alternative_field_names(self, service):
        """Qwen 返回不同字段名时应兼容"""
        service.tavily.search_for_topic.return_value = []
        service.tashan.search_for_topic.return_value = []
        service.qwen.search_for_topic.return_value = [
            {"link": "https://alt.com", "name": "替代标题", "description": "替代摘要"},
            {"url": "https://text.com", "title": "文本标题", "text": "text字段内容"},
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 2
        assert results[0].url == "https://alt.com"
        assert results[0].title == "替代标题"
        assert results[1].content == "text字段内容"

    # ---- 新增：他山第三引擎相关测试 ----

    def test_merges_three_engines(self, service):
        """应合并三个引擎的结果（Tavily + Qwen + 他山）"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://tavily.com/1", title="Tavily结果1", content="t1"),
        ]
        service.qwen.search_for_topic.return_value = [
            {"url": "https://qwen.com/1", "title": "Qwen结果1", "snippet": "q1"},
        ]
        service.tashan.search_for_topic.return_value = [
            SearchSource(url="https://tashan.com/1", title="他山结果1",
                         content="a1", source="TashanAminer"),
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 3
        sources = {r.source for r in results}
        assert "TavilySearch" in sources
        assert "QwenWebSearch" in sources
        assert "TashanAminer" in sources

    def test_tashan_deduplicates_with_tavily(self, service):
        """他山与 Tavily 相同 URL 应去重（Tavily 优先）"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://same.com", title="Tavily版", content="t"),
        ]
        service.qwen.search_for_topic.return_value = []
        service.tashan.search_for_topic.return_value = [
            SearchSource(url="https://same.com", title="他山版", content="a", source="TashanWorldWeave"),
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 1
        assert results[0].source == "TavilySearch"

    def test_tashan_failure_doesnt_break(self, service):
        """他山失败不影响 Tavily + Qwen 结果"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = [
            SearchSource(url="https://t.com", title="Tavily结果", content="t"),
        ]
        service.qwen.search_for_topic.return_value = [
            {"url": "https://q.com", "title": "Qwen结果", "snippet": "q"},
        ]
        service.tashan.search_for_topic.side_effect = Exception("他山不可达")

        results = service.search_for_topic("议题")
        assert len(results) == 2
        sources = {r.source for r in results}
        assert "TavilySearch" in sources and "QwenWebSearch" in sources

    def test_tashan_only_when_others_empty(self, service):
        """仅他山有结果时也应正常返回"""
        from src.search.tavily_search import SearchSource
        service.tavily.search_for_topic.return_value = []
        service.qwen.search_for_topic.return_value = []
        service.tashan.search_for_topic.return_value = [
            SearchSource(url="https://tashan.com/1", title="他山结果",
                         content="a", source="TashanSourceFeed"),
        ]

        results = service.search_for_topic("议题")
        assert len(results) == 1
        assert results[0].source == "TashanSourceFeed"


def _routed_get(aminer=None, source_feed=None, world_weave=None, literature=None, signals=None):
    """构造按 URL 分发响应的 httpx.get side_effect。

    每个参数传入对应接口的响应 dict；未提供者返回空结构。
    """
    def _side_effect(url, params=None, headers=None, **kwargs):
        if "aminer" in url:
            resp = aminer if aminer is not None else {"data": {"list": []}}
        elif "source-feed" in url:
            resp = source_feed if source_feed is not None else {"list": []}
        elif "literature" in url:
            resp = literature if literature is not None else {"list": []}
        elif "signals" in url:
            resp = signals if signals is not None else {"signals": []}
        else:
            resp = world_weave if world_weave is not None else {"signals": []}
        return MagicMock(status_code=200, json=lambda r=resp: r)
    return _side_effect


class TestTashanSearch:
    """TashanSearchService 第三引擎单元测试（mock 数据，不依赖真实网络）"""

    @pytest.fixture
    def service(self):
        """创建 mock 掉 httpx 客户端的 TashanSearchService"""
        from src.search.tashan_search import TashanSearchService
        svc = TashanSearchService()
        svc._http_client = MagicMock()
        return svc

    def test_aminer_parses_papers(self, service):
        """AMiner 论文结果应正确解析"""
        aminer_resp = {
            "data": {
                "list": [
                    {
                        "title": "A Survey on LLM Agents",
                        "url": "https://paper.com/1",
                        "authors": "张三, 李四",
                        "venue": "ACL 2026",
                        "year": "2026",
                        "abstract": "This paper surveys LLM agents.",
                    }
                ]
            }
        }
        service._http_client.get.side_effect = _routed_get(aminer=aminer_resp)
        service.token = "test"  # 配置 token 后启用 AMiner
        from src.search.tashan_search import SOURCE_AMINER
        results = service.search_for_topic("LLM")
        assert len(results) == 1
        r = results[0]
        assert r.source == SOURCE_AMINER
        assert r.title == "A Survey on LLM Agents"
        assert "张三" in r.content
        assert "ACL 2026" in r.content

    def test_source_feed_filters_by_keyword(self, service):
        """信源文章应按关键词过滤（浏览式发现）"""
        feed_resp = {
            "list": [
                {
                    "title": "LLM 智能体新进展",
                    "url": "https://feed.com/1",
                    "source_feed_name": "新智元",
                    "description": "报道了最新 LLM 研究",
                },
                {
                    "title": "无关文章标题",
                    "url": "https://feed.com/2",
                    "source_feed_name": "某信源",
                    "description": "与主题无关",
                },
            ]
        }
        service._http_client.get.side_effect = _routed_get(source_feed=feed_resp)
        from src.search.tashan_search import SOURCE_SOURCE_FEED
        results = service.search_for_topic("LLM")
        assert len(results) == 1
        assert results[0].source == SOURCE_SOURCE_FEED
        assert results[0].url == "https://feed.com/1"
        assert "新智元" in results[0].content

    def test_world_weave_parses_signals(self, service):
        """WorldWeave 信号应正确解析"""
        weave_resp = {
            "signals": [
                {
                    "title": "LLM 某科技信号",
                    "summary": "信号摘要内容",
                    "url": "https://signal.com/1",
                    "region_label": "科技",
                    "published_at": "2026-07-31T13:00:02.000Z",
                    "recall_score": 12.3,
                }
            ]
        }
        service._http_client.get.side_effect = _routed_get(world_weave=weave_resp)
        from src.search.tashan_search import SOURCE_WORLD_WEAVE
        results = service.search_for_topic("LLM")
        assert len(results) == 1
        r = results[0]
        assert r.source == SOURCE_WORLD_WEAVE
        assert "信号摘要内容" in r.content
        assert "科技" in r.content
        assert r.score == 12.3

    def test_all_three_sources_merged(self, service):
        """三路结果应合并，source 标注正确"""
        service._http_client.get.side_effect = _routed_get(
            aminer={"data": {"list": [{
                "title": "论文A", "url": "https://p.com/1",
                "abstract": "abs", "authors": "", "venue": "", "year": "",
            }]}},
            source_feed={"list": [{
                "title": "LLM 文章", "url": "https://f.com/1",
                "source_feed_name": "信源", "description": "desc",
            }]},
            world_weave={"signals": [{
                "title": "LLM 信号", "summary": "sum", "url": "https://s.com/1",
            }]},
        )
        service.token = "test"  # 配置 token 后启用 AMiner
        results = service.search_for_topic("LLM")
        sources = {r.source for r in results}
        assert len(results) == 3
        assert "TashanAminer" in sources
        assert "TashanSourceFeed" in sources
        assert "TashanWorldWeave" in sources

    def test_network_failure_returns_empty(self, service):
        """网络异常应降级返回空列表，不抛异常"""
        service._http_client.get.side_effect = Exception("Connection refused")
        results = service.search_for_topic("LLM")
        assert results == []

    def test_aminer_token_error_degrades(self, service):
        """AMiner Token Parse Error 应以空降级，不影响其他路"""
        aminers = MagicMock(status_code=200, json=lambda: {
            "detail": "{\"code\":40308,\"success\":false,\"msg\":\"Token Parse Error\"}"
        })
        feeds = MagicMock(status_code=200, json=lambda: {"list": [
            {"title": "LLM 文章", "url": "https://f.com/1",
             "source_feed_name": "信源", "description": "desc"}
        ]})
        weaves = MagicMock(status_code=200, json=lambda: {"signals": []})

        def _side_effect(url, params=None, headers=None, **kwargs):
            if "aminer" in url:
                return aminers
            if "source-feed" in url:
                return feeds
            return weaves

        service._http_client.get.side_effect = _side_effect
        results = service.search_for_topic("LLM")
        # AMiner 失败，但信源能正常返回
        assert len(results) == 1
        assert results[0].source == "TashanSourceFeed"
