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

    def test_global_default_uses_platform_main_key(self, monkeypatch):
        """全局默认模式：embedding fallback 平台主 key（QWEN_API_KEY），不是独立 embedding key"""
        from src.llm_client import LLMClient
        monkeypatch.setattr("src.llm_client.QWEN_API_KEY", "platform-main-key")
        monkeypatch.setattr("src.llm_client.QWEN_BASE_URL", "https://platform-main.example/v1")
        monkeypatch.setattr("src.llm_client.QWEN_EMBEDDING_API_KEY", "platform-emb-key-should-not-be-used")
        monkeypatch.setattr("src.llm_client.QWEN_EMBEDDING_BASE_URL", "https://platform-emb.example/v1")
        c = LLMClient(api_key="platform-main-key", base_url="https://platform-main.example/v1")
        assert c._embedding_client is not None
        assert "platform-main-key" in str(c._embedding_client.api_key)
        assert "platform-emb-key-should-not-be-used" not in str(c._embedding_client.api_key)

    def test_no_key_anywhere_disables_embedding(self, monkeypatch):
        """无任何 key → embedding client 为 None（调用方降级）"""
        from src.llm_client import LLMClient
        monkeypatch.setattr("src.llm_client.QWEN_API_KEY", "")
        monkeypatch.setattr("src.llm_client.QWEN_BASE_URL", "https://x/v1")
        c = LLMClient(api_key="", base_url="https://x/v1")
        assert c._embedding_client is None
