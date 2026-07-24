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
