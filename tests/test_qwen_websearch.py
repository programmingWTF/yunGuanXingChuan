"""
云观星传 - 百炼 WebSearch MCP 服务单元测试
覆盖请求头构造、SSE 解析、JSON-RPC 调用、结果解析与降级（Mock HTTP，不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖（conftest 已保证真实 httpx 先入 sys.modules，这里跳过覆盖）
for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def service():
    """创建带 mock httpx 客户端的服务实例"""
    from src.search.qwen_websearch import QwenWebSearchService
    svc = QwenWebSearchService(api_key="test-key", mcp_url="https://mcp.example.com/sse")
    svc._http_client = MagicMock()
    return svc


def _mock_response(status_ok=True, headers=None, json_data=None, text=""):
    """构造 mock httpx.Response"""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.headers = headers or {}
    resp.json.return_value = json_data
    resp.text = text
    return resp


class TestMakeHeaders:
    """请求头构造测试"""

    def test_basic_headers(self, service):
        """无会话时应包含 Authorization 与 Content-Type"""
        service._session_id = None
        headers = service._make_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert "Accept" in headers
        assert "Mcp-Session-Id" not in headers

    def test_headers_with_session(self, service):
        """有会话时应携带 Mcp-Session-Id"""
        service._session_id = "sess-abc-123"
        headers = service._make_headers()
        assert headers["Mcp-Session-Id"] == "sess-abc-123"


class TestParseSSEResponse:
    """SSE 响应解析测试"""

    def test_parse_valid_data_line(self, service):
        """应解析 data: 行中的 JSON-RPC result"""
        text = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
        parsed = service._parse_sse_response(text)
        assert parsed is not None
        assert parsed["result"] == {"ok": True}

    def test_parse_skips_lines_without_result(self, service):
        """无 result 字段的 data 行应被跳过"""
        text = 'data: {"jsonrpc":"2.0","id":1,"error":"x"}\ndata: {"result":{"ok":1}}\n'
        parsed = service._parse_sse_response(text)
        assert parsed["result"] == {"ok": 1}

    def test_parse_invalid_json_continues(self, service):
        """损坏 JSON 行应跳过，继续找后续有效行"""
        text = 'data: not-json\ndata: {"result":{"a":2}}'
        parsed = service._parse_sse_response(text)
        assert parsed["result"] == {"a": 2}

    def test_parse_empty_text(self, service):
        """空文本应返回 None"""
        assert service._parse_sse_response("") is None

    def test_parse_no_data_lines(self, service):
        """无 data: 前缀的文本应返回 None"""
        assert service._parse_sse_response("plain text\nanother line") is None


class TestClientInit:
    """httpx 客户端延迟初始化测试"""

    def test_no_api_key_returns_none(self):
        """未配置 api_key 时应返回 None 并降级"""
        from src.search.qwen_websearch import QwenWebSearchService
        svc = QwenWebSearchService(api_key=None, mcp_url="https://x")
        # api_key or DASHSCOPE_API_KEY：测试环境 settings 可能读到空串
        svc.api_key = None
        assert svc._get_http_client() is None

    def test_lazy_init_creates_client(self):
        """有 key 时应延迟创建 httpx 客户端并缓存"""
        from src.search.qwen_websearch import QwenWebSearchService
        svc = QwenWebSearchService(api_key="k", mcp_url="https://x")
        svc._http_client = None
        with patch('httpx.Client') as MockClient:
            MockClient.return_value = MagicMock()
            client = svc._get_http_client()
            assert client is MockClient.return_value
            # 二次调用复用缓存
            assert svc._get_http_client() is client
            MockClient.assert_called_once()


class TestJsonrpcCall:
    """JSON-RPC 2.0 调用测试"""

    def test_no_client_returns_none(self):
        """无 httpx 客户端时应返回 None"""
        from src.search.qwen_websearch import QwenWebSearchService
        svc = QwenWebSearchService(api_key="k", mcp_url="https://x")
        svc._http_client = None
        with patch.object(svc, '_get_http_client', return_value=None):
            assert svc._jsonrpc_call("tools/call") is None

    def test_json_response_parsed(self, service):
        """普通 JSON 响应应原样返回"""
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json"},
            json_data={"jsonrpc": "2.0", "id": 1, "result": {"data": "ok"}},
        )
        result = service._jsonrpc_call("tools/call", {"name": "bailian_web_search"})
        assert result["result"] == {"data": "ok"}
        # 请求体校验
        payload = service._http_client.post.call_args.kwargs["json"]
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "bailian_web_search"

    def test_sse_response_parsed(self, service):
        """text/event-stream 响应应走 SSE 解析"""
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "text/event-stream"},
            text='data: {"jsonrpc":"2.0","id":1,"result":{"pages":[]}}',
        )
        result = service._jsonrpc_call("tools/call")
        assert result["result"] == {"pages": []}

    def test_session_id_saved_from_response(self, service):
        """响应头中的 Mcp-Session-Id 应被保存供后续复用"""
        service._session_id = None
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json", "mcp-session-id": "new-sess"},
            json_data={"result": {}},
        )
        service._jsonrpc_call("initialize")
        assert service._session_id == "new-sess"

    def test_network_error_returns_none(self, service):
        """网络异常应降级返回 None 而非抛出"""
        service._http_client.post.side_effect = ConnectionError("boom")
        assert service._jsonrpc_call("tools/call") is None


class TestInitialize:
    """MCP 会话初始化测试"""

    def test_initialize_success(self, service):
        """初始化成功应返回 True 并发送 initialized 通知"""
        service._session_id = None
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json", "mcp-session-id": "s1"},
            json_data={"result": {"protocolVersion": "2024-11-05"}},
        )
        assert service._initialize() is True
        # 两次 post：initialize + notifications/initialized
        assert service._http_client.post.call_count == 2
        notify_payload = service._http_client.post.call_args.kwargs["json"]
        assert notify_payload["method"] == "notifications/initialized"

    def test_initialize_failure(self, service):
        """初始化无 result 应返回 False"""
        service._session_id = None
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json"},
            json_data={"error": "bad"},
        )
        assert service._initialize() is False

    def test_initialize_network_error_returns_false(self, service):
        """初始化网络异常应返回 False"""
        service._session_id = None
        service._http_client.post.side_effect = ConnectionError("no network")
        assert service._initialize() is False


class TestSearch:
    """search 主流程测试"""

    def test_no_client_returns_empty(self):
        """无客户端应返回空列表"""
        from src.search.qwen_websearch import QwenWebSearchService
        svc = QwenWebSearchService(api_key="k", mcp_url="https://x")
        with patch.object(svc, '_get_http_client', return_value=None):
            assert svc.search("嫦娥六号") == []

    def test_init_failure_returns_empty(self, service):
        """会话初始化失败应返回空列表"""
        service._session_id = None
        with patch.object(service, '_initialize', return_value=False):
            assert service.search("嫦娥六号") == []

    def test_search_parses_pages(self, service):
        """应从 content blocks 提取 JSON 并返回 pages"""
        service._session_id = "sess"
        tool_payload = {
            "result": {
                "content": [
                    {"type": "text", "text": '{"pages": [{"title": "嫦娥六号", "url": "https://a.com", "snippet": "月背采样"}]}'}
                ]
            }
        }
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json"},
            json_data=tool_payload,
        )
        pages = service.search("嫦娥六号", count=5)
        assert len(pages) == 1
        assert pages[0]["title"] == "嫦娥六号"
        # count 参数透传
        args = service._http_client.post.call_args.kwargs["json"]
        assert args["params"]["arguments"]["count"] == 5

    def test_search_non_json_text_fallback(self, service):
        """非 JSON 文本应降级为纯文本结果条目"""
        service._session_id = "sess"
        tool_payload = {
            "result": {"content": [{"type": "text", "text": "搜索返回的纯文本内容"}]}
        }
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json"},
            json_data=tool_payload,
        )
        pages = service.search("某议题")
        assert len(pages) == 1
        assert pages[0]["snippet"].startswith("搜索返回的纯文本")

    def test_search_no_valid_content(self, service):
        """无有效 content 应返回空列表"""
        service._session_id = "sess"
        service._http_client.post.return_value = _mock_response(
            headers={"content-type": "application/json"},
            json_data={"result": {"content": []}},
        )
        assert service.search("某议题") == []

    def test_search_rpc_none_returns_empty(self, service):
        """JSON-RPC 返回 None 应返回空列表"""
        service._session_id = "sess"
        with patch.object(service, '_jsonrpc_call', return_value=None):
            assert service.search("某议题") == []


class TestSearchForTopic:
    """多角度议题搜索测试"""

    def test_dedup_by_url(self, service):
        """相同 URL 的结果应去重（url 优先，link 兜底）"""
        results = [
            {"title": "A", "url": "https://same.com/a", "snippet": "1"},
            {"title": "A2", "url": "https://same.com/a", "snippet": "2"},
            {"title": "B", "link": "https://same.com/b", "snippet": "3"},
            {"title": "B2", "link": "https://same.com/b", "snippet": "4"},
        ]
        with patch.object(service, 'search', side_effect=[results[:2], results[2:], []]):
            merged = service.search_for_topic("嫦娥六号")
        urls = [r.get("url") or r.get("link") for r in merged]
        assert urls.count("https://same.com/a") == 1
        assert urls.count("https://same.com/b") == 1
        assert len(merged) == 2

    def test_three_queries_issued(self, service):
        """应为议题构造 3 个搜索查询"""
        with patch.object(service, 'search', return_value=[]) as mock_search:
            service.search_for_topic("天问三号")
        assert mock_search.call_count == 3
        queries = [c.args[0] for c in mock_search.call_args_list]
        assert any("科学事实" in q for q in queries)
        assert any("international media" in q for q in queries)
        assert any("国际舆论" in q for q in queries)

    def test_no_url_uses_title_key(self, service):
        """无 url/link 的条目按 title+计数 键去重，不丢结果"""
        results = [
            {"title": "无链接结果", "snippet": "x"},
            {"title": "无链接结果", "snippet": "y"},
        ]
        with patch.object(service, 'search', side_effect=[results, [], []]):
            merged = service.search_for_topic("某议题")
        assert len(merged) == 2
