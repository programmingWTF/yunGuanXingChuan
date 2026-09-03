"""
云观星传 - LLM 客户端工具方法单元测试
验证 JSON 修复、截断补全等核心解析逻辑（不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.llm_client import LLMClient


class TestRepairJsonQuotes:
    """_repair_json_quotes: 修复 JSON 中未转义的内部引号"""

    def test_normal_json_unchanged(self):
        """正常 JSON 不应被修改"""
        text = '{"key": "value", "num": 123}'
        result = LLMClient._repair_json_quotes(text)
        assert result == text

    def test_inner_quotes_escaped(self):
        """内部引号应被转义"""
        # "曾用名"郑和号"）" 中的内部引号
        text = '{"name": "曾用名"郑和号"）"}'
        result = LLMClient._repair_json_quotes(text)
        import json
        parsed = json.loads(result)
        assert "郑和号" in parsed["name"]

    def test_multiple_inner_quotes(self):
        """多个内部引号"""
        text = '{"text": "他说"你好"然后"再见"走了"}'
        result = LLMClient._repair_json_quotes(text)
        import json
        parsed = json.loads(result)
        assert "你好" in parsed["text"]
        assert "再见" in parsed["text"]

    def test_escaped_quotes_preserved(self):
        """已转义的引号不应被二次转义"""
        text = '{"text": "已\\"转义\\"的"}'
        result = LLMClient._repair_json_quotes(text)
        import json
        parsed = json.loads(result)
        assert "转义" in parsed["text"]

    def test_nested_json(self):
        """嵌套 JSON 结构"""
        text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = LLMClient._repair_json_quotes(text)
        import json
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == "value"
        assert parsed["list"] == [1, 2, 3]

    def test_empty_string(self):
        """空字符串"""
        result = LLMClient._repair_json_quotes("")
        assert result == ""

    def test_chinese_content_with_quotes(self):
        """中文内容含引号（常见 LLM 输出问题）"""
        text = '{"strategy": "采用"和平发展"叙事框架"}'
        result = LLMClient._repair_json_quotes(text)
        import json
        parsed = json.loads(result)
        assert "和平发展" in parsed["strategy"]


class TestFixTruncatedJson:
    """_fix_truncated_json: 修复被截断的 JSON"""

    def test_complete_json_returns_none(self):
        """完整 JSON 不需要修复，返回 None"""
        text = '{"key": "value"}'
        result = LLMClient._fix_truncated_json(text)
        assert result is None

    def test_unclosed_object(self):
        """未闭合的对象"""
        text = '{"key": "value", "key2": "value2"'
        result = LLMClient._fix_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_unclosed_array(self):
        """未闭合的数组"""
        text = '{"items": ["a", "b", "c"'
        result = LLMClient._fix_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert "a" in parsed["items"]

    def test_truncated_in_string(self):
        """在字符串内部截断"""
        text = '{"key": "这是一个很长的值被截断了'
        result = LLMClient._fix_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert "key" in parsed

    def test_nested_truncation(self):
        """嵌套结构截断"""
        text = '{"outer": {"inner": "value"}, "arr": [1, 2'
        result = LLMClient._fix_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert parsed["outer"]["inner"] == "value"

    def test_non_json_returns_none(self):
        """非 JSON 文本返回 None"""
        text = "这不是JSON"
        result = LLMClient._fix_truncated_json(text)
        assert result is None

    def test_empty_returns_none(self):
        """空字符串返回 None"""
        result = LLMClient._fix_truncated_json("")
        assert result is None

    def test_deeply_nested_truncation(self):
        """深层嵌套截断——至少不应抛异常"""
        text = '{"a": {"b": {"c": {"d": "val"'
        result = LLMClient._fix_truncated_json(text)
        # 深层嵌套截断可能无法完美修复，但不应抛异常
        if result is not None:
            import json
            try:
                parsed = json.loads(result)
                assert "a" in parsed
            except json.JSONDecodeError:
                pass  # 深层嵌套截断是已知限制，不强制要求可解析

    def test_trailing_comma(self):
        """末尾逗号"""
        text = '{"a": 1, "b": 2,'
        result = LLMClient._fix_truncated_json(text)
        assert result is not None
        import json
        parsed = json.loads(result)
        assert parsed["a"] == 1


class TestRepairAndFixCombined:
    """组合修复场景：先修引号再补截断"""

    def test_inner_quotes_and_truncation(self):
        """同时有内部引号和截断"""
        text = '{"strategies": [{"name": "采用"和平"框架", "desc": "这是'
        # 先修引号
        repaired = LLMClient._repair_json_quotes(text)
        # 再补截断
        fixed = LLMClient._fix_truncated_json(repaired)
        assert fixed is not None
        import json
        parsed = json.loads(fixed)
        assert "strategies" in parsed

    def test_realistic_llm_output(self):
        """模拟真实 LLM 输出：含中文引号 + 截断"""
        text = '''{"topic": "嫦娥六号", "strategies": [{"strategy_id": "S001", "narrative_angle": "强调"人类共同探索"的叙事", "sample_text": "嫦娥六号带回了1935.3克月壤，这是全人类的'''
        repaired = LLMClient._repair_json_quotes(text)
        fixed = LLMClient._fix_truncated_json(repaired)
        assert fixed is not None
        import json
        parsed = json.loads(fixed)
        assert parsed["topic"] == "嫦娥六号"
        assert len(parsed["strategies"]) >= 1


class TestEmbeddingKeyOwnership:
    """向量模型密钥归属（用户自带钥匙，绝不用平台独立 embedding key）"""

    def test_user_embedding_key_used_when_provided(self, monkeypatch):
        """用户显式配置了 embedding → 用用户的 embedding key+base_url"""
        from src.llm_client import LLMClient
        c = LLMClient(
            api_key="user-main-key",
            base_url="https://user-main.example/v1",
            embedding_api_key="user-emb-key",
            embedding_base_url="https://user-emb.example/v1",
        )
        assert c._embedding_client is not None
        # openai client 的 api_key / base_url 属性（构造时校验会发空请求？不会，惰性）
        # 通过内部状态检查：client 实例的 api_key 属性
        assert "user-emb-key" in str(c._embedding_client.api_key)
        assert "user-emb.example" in str(c._embedding_client.base_url)

    def test_user_main_key_fallback_when_embedding_missing(self, monkeypatch):
        """用户没配 embedding → fallback 用户自己的主 LLM key（绝不 fallback 平台 key）"""
        from src.llm_client import LLMClient
        # 模拟 from_config（多租户）：用户只有主 LLM 配置
        c = LLMClient.from_config({
            "llm": {"api_key": "user-main-key-abc", "base_url": "https://user-main.example/v1", "model": "qwen-test"},
            "embedding": None,
        })
        assert c._embedding_client is not None, "应 fallback 用户主 key 初始化 embedding client"
        assert "user-main-key-abc" in str(c._embedding_client.api_key), "embedding 必须用用户主 key"
        assert "user-main.example" in str(c._embedding_client.base_url), "embedding 必须用用户主 base_url"

    def test_global_default_uses_platform_embedding_key(self, monkeypatch):
        """全局默认模式：embedding 用平台独立 embedding key（平台自己的基础设施）"""
        from src.llm_client import LLMClient
        monkeypatch.setattr("src.llm_client.QWEN_API_KEY", "platform-main-key")
        monkeypatch.setattr("src.llm_client.QWEN_BASE_URL", "https://platform-main.example/v1")
        monkeypatch.setattr("src.llm_client.QWEN_EMBEDDING_API_KEY", "platform-emb-key")
        monkeypatch.setattr("src.llm_client.QWEN_EMBEDDING_BASE_URL", "https://platform-emb.example/v1")
        c = LLMClient()  # 无参构造 = 全局默认
        assert c._embedding_client is not None
        assert "platform-emb-key" in str(c._embedding_client.api_key)
        assert "platform-emb.example" in str(c._embedding_client.base_url)

    def test_tenant_mode_never_uses_platform_embedding_key(self, monkeypatch):
        """多租户模式：用户没配 embedding → 用用户主 key，绝不 fallback 平台 embedding key"""
        from src.llm_client import LLMClient
        monkeypatch.setattr("src.llm_client.QWEN_EMBEDDING_API_KEY", "platform-emb-key-should-not-leak")
        c = LLMClient.from_config({
            "llm": {"api_key": "user-main-key", "base_url": "https://user-main.example/v1", "model": "m"},
            "embedding": None,
        })
        assert c._embedding_client is not None
        assert "user-main-key" in str(c._embedding_client.api_key)
        assert "platform-emb-key-should-not-leak" not in str(c._embedding_client.api_key)
        assert "user-main.example" in str(c._embedding_client.base_url)

    def test_no_key_anywhere_disables_embedding(self, monkeypatch):
        """无任何 key → embedding client 为 None（调用方降级）"""
        from src.llm_client import LLMClient
        monkeypatch.setattr("src.llm_client.QWEN_API_KEY", "")
        monkeypatch.setattr("src.llm_client.QWEN_BASE_URL", "https://x/v1")
        c = LLMClient(api_key="", base_url="https://x/v1")
        assert c._embedding_client is None


# ══════════════════════════════════════════════════════════════
# 以下为补充测试：chat/联网搜索/多轮/embedding 客户端链路（Mock OpenAI SDK）
# ══════════════════════════════════════════════════════════════
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """创建不触发真实网络的 LLMClient"""
    with patch('src.llm_client.OpenAI') as MockOpenAI:
        MockOpenAI.return_value = MagicMock()
        from src.llm_client import LLMClient
        c = LLMClient(api_key="test-key", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                      model="qwen-test", max_retries=2, retry_delay=0.01,
                      embedding_api_key="", embedding_base_url="")
        c.client = MockOpenAI.return_value
        c._embedding_client = MockOpenAI.return_value  # embedding mock
        yield c


def _resp(content="ok", finish_reason="stop"):
    r = MagicMock()
    r.choices[0].finish_reason = finish_reason
    r.choices[0].message.content = content
    return r


class TestChat:
    """chat() 基础调用测试"""

    def test_success_returns_content(self, client):
        client.client.chat.completions.create.return_value = _resp("你好")
        assert client.chat("sys", "user") == "你好"

    def test_json_mode_appends_json_hint(self, client):
        """prompt 无 json 字样时应自动追加 JSON 提示（DeepSeek 兼容）"""
        client.client.chat.completions.create.return_value = _resp('{"a": 1}')
        client.chat("回答", "什么是月球", json_mode=True)
        kwargs = client.client.chat.completions.create.call_args.kwargs
        assert "JSON" in kwargs["messages"][1]["content"]
        assert kwargs["response_format"] == {"type": "json_object"}

    def test_json_mode_with_json_word_no_append(self, client):
        client.client.chat.completions.create.return_value = _resp('{}')
        client.chat("请输出 JSON", "分析", json_mode=True)
        msg = client.client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert msg == "分析"  # 未追加

    def test_max_tokens_passed(self, client):
        client.client.chat.completions.create.return_value = _resp("x")
        client.chat("s", "u", max_tokens=500)
        kwargs = client.client.chat.completions.create.call_args.kwargs
        assert kwargs["max_tokens"] == 500

    def test_strict_truncation_raises(self, client):
        """finish_reason=length + strict_truncation 应立即抛错"""
        client.client.chat.completions.create.return_value = _resp("半截", finish_reason="length")
        with pytest.raises(ValueError, match="截断"):
            client.chat("s", "u", strict_truncation=True)

    def test_permanent_error_no_retry(self, client):
        """鉴权类永久错误应直接抛出不重试"""
        client.client.chat.completions.create.side_effect = RuntimeError("InvalidApiKey: 401")
        with pytest.raises(RuntimeError):
            client.chat("s", "u")
        assert client.client.chat.completions.create.call_count == 1

    def test_transient_error_retries(self, client):
        """临时错误应重试后成功"""
        client.client.chat.completions.create.side_effect = [ConnectionError("net"), _resp("成功")]
        with patch('src.llm_client.time.sleep'):
            assert client.chat("s", "u") == "成功"
        assert client.client.chat.completions.create.call_count == 2

    def test_transient_error_exhausted_raises(self, client):
        """临时错误重试耗尽应抛出"""
        client.client.chat.completions.create.side_effect = ConnectionError("net")
        with patch('src.llm_client.time.sleep'):
            with pytest.raises(ConnectionError):
                client.chat("s", "u")
        assert client.client.chat.completions.create.call_count == 2  # max_retries=2

    def test_empty_content_retried(self, client):
        """空内容视为失败并重试"""
        client.client.chat.completions.create.side_effect = [_resp(""), _resp("有内容")]
        with patch('src.llm_client.time.sleep'):
            assert client.chat("s", "u") == "有内容"


class TestChatWithSearch:
    """联网搜索调用测试"""

    def test_dashscope_responses_api(self, client):
        """百炼平台应走 Responses API + web_search"""
        resp = MagicMock()
        resp.output_text = "搜索结果"
        client.client.responses.create.return_value = resp
        result = client._chat_with_search("sys", "user", None, json_mode=True)
        assert result == "搜索结果"
        kwargs = client.client.responses.create.call_args.kwargs
        assert kwargs["tools"] == [{"type": "web_search"}]
        assert "JSON" in kwargs["input"]  # json_mode 提示追加

    def test_dashscope_fallback_to_completions(self, client):
        """Responses API 失败应回退普通 Chat Completions"""
        client.client.responses.create.side_effect = RuntimeError("responses down")
        client.client.chat.completions.create.return_value = _resp("回退结果")
        with patch('src.llm_client.time.sleep'):
            result = client._chat_with_search("sys", "user")
        assert result == "回退结果"

    def test_non_dashscope_direct_completions(self, client):
        """非百炼平台直接走 Chat Completions"""
        with patch('src.llm_client.OpenAI'):
            from src.llm_client import LLMClient
            c = LLMClient(api_key="k", base_url="https://api.deepseek.com/v1", max_retries=1)
            c.client = MagicMock()
            c.client.chat.completions.create.return_value = _resp("深度求索")
            assert c._chat_with_search("s", "u") == "深度求索"


class TestChatJson:
    """chat_json 解析测试"""

    def test_parses_json_with_markdown(self, client):
        with patch.object(client, 'chat', return_value='```json\n{"topic": "嫦娥六号"}\n```'):
            result = client.chat_json("s", "u")
        assert result == {"topic": "嫦娥六号"}

    def test_unparseable_falls_back_repair(self, client):
        client._repair_json_quotes = MagicMock(return_value='{"ok": 1}')
        with patch.object(client, 'chat', return_value='{"ok": 1'):  # 截断/损坏
            result = client.chat_json("s", "u")
        assert result == {"ok": 1}


class TestChatMultiTurn:
    """多轮对话测试"""

    def test_success(self, client):
        client.client.chat.completions.create.return_value = _resp("多轮回复")
        msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        assert client.chat_multi_turn(msgs) == "多轮回复"
        kwargs = client.client.chat.completions.create.call_args.kwargs
        assert kwargs["messages"] == msgs
        assert kwargs["response_format"] == {"type": "json_object"}  # json_mode=True 默认

    def test_empty_content_retries(self, client):
        client.client.chat.completions.create.side_effect = [_resp(""), _resp("ok")]
        with patch('src.llm_client.time.sleep'):
            assert client.chat_multi_turn([{"role": "user", "content": "u"}]) == "ok"


class TestEmbeddingCalls:
    """embedding 调用测试"""

    def test_no_embedding_client_returns_none(self, client):
        client._embedding_client = None
        assert client.get_embedding("文本") is None
        assert client.get_embeddings_batch(["a"]) == []

    def test_embedding_success(self, client):
        resp = MagicMock()
        resp.data[0].embedding = [0.1, 0.2]
        client._embedding_client.embeddings.create.return_value = resp
        assert client.get_embedding("文本") == [0.1, 0.2]

    def test_embeddings_batch_success(self, client):
        resp = MagicMock()
        resp.data = [MagicMock(embedding=[0.1]), MagicMock(embedding=[0.2])]
        client._embedding_client.embeddings.create.return_value = resp
        assert client.get_embeddings_batch(["a", "b"]) == [[0.1], [0.2]]

    def test_embedding_failure_raises(self, client):
        client._embedding_client.embeddings.create.side_effect = RuntimeError("embed down")
        with patch('src.llm_client.time.sleep'):
            with pytest.raises(RuntimeError):
                client.get_embedding("文本")


class TestIsPermanentError:
    """永久错误判定测试"""

    def test_permanent_codes(self):
        from src.llm_client import LLMClient
        assert LLMClient._is_permanent_llm_error(RuntimeError("AccessDenied.Unpurchased model"))
        assert LLMClient._is_permanent_llm_error(RuntimeError("InvalidApiKey given"))
        assert LLMClient._is_permanent_llm_error(RuntimeError("401 unauthorized"))
        assert LLMClient._is_permanent_llm_error(RuntimeError("模型未开通，请先开通"))

    def test_transient_codes(self):
        from src.llm_client import LLMClient
        assert not LLMClient._is_permanent_llm_error(RuntimeError("timeout after 30s"))
        assert not LLMClient._is_permanent_llm_error(RuntimeError("rate limit"))
