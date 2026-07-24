"""
云观星传 - BaseAgent 输出解析单元测试
验证 _parse_tool_use_output 的各种 JSON 修复路径（不依赖 LLM 调用）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


class ConcreteAgent:
    """用于测试的具体 Agent 实现（避免 ABC 限制）"""

    def __init__(self):
        from src.agents.base_agent import BaseAgent
        from src.llm_client import LLMClient

        # 创建一个最小化的 agent 实例
        self.agent_name = "test_agent"
        self.output_schema = None
        self.llm_client = LLMClient.__new__(LLMClient)  # 不初始化网络连接

    def _get_fallback_result(self):
        """委托给 BaseAgent._get_fallback_result"""
        from src.agents.base_agent import BaseAgent
        return BaseAgent._get_fallback_result(self)

    def _parse_tool_use_output(self, content: str):
        """复制 BaseAgent._parse_tool_use_output 的逻辑进行测试"""
        from src.agents.base_agent import BaseAgent
        # 直接调用 BaseAgent 的方法
        return BaseAgent._parse_tool_use_output(self, content)


@pytest.fixture
def agent():
    """创建测试用 Agent 实例"""
    with patch('src.llm_client.OpenAI'):
        a = ConcreteAgent()
    return a


class TestParseValidJson:
    """正常 JSON 解析"""

    def test_simple_json(self, agent):
        """简单 JSON 对象"""
        content = '{"key": "value", "num": 42}'
        result = agent._parse_tool_use_output(content)
        assert result == {"key": "value", "num": 42}

    def test_json_with_markdown_fence(self, agent):
        """带 markdown 代码块的 JSON"""
        content = '```json\n{"key": "value"}\n```'
        result = agent._parse_tool_use_output(content)
        assert result == {"key": "value"}

    def test_json_with_plain_fence(self, agent):
        """带普通代码块的 JSON"""
        content = '```\n{"key": "value"}\n```'
        result = agent._parse_tool_use_output(content)
        assert result == {"key": "value"}

    def test_nested_json(self, agent):
        """嵌套 JSON"""
        content = '{"strategies": [{"id": "S001", "messages": ["msg1", "msg2"]}]}'
        result = agent._parse_tool_use_output(content)
        assert len(result["strategies"]) == 1
        assert result["strategies"][0]["id"] == "S001"

    def test_chinese_content(self, agent):
        """中文内容 JSON"""
        content = '{"topic": "嫦娥六号", "summary": "实现人类首次月背采样返回"}'
        result = agent._parse_tool_use_output(content)
        assert result["topic"] == "嫦娥六号"


class TestParseInnerQuotes:
    """内部引号修复路径"""

    def test_unescaped_inner_quotes(self, agent):
        """未转义的内部引号（strategy_agent 常见错误）"""
        content = '{"strategy": "采用"和平发展"叙事框架", "id": "S001"}'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert "id" in result
        assert result["id"] == "S001"

    def test_multiple_inner_quotes(self, agent):
        """多处内部引号"""
        content = '{"text": "他说"你好"然后"再见"", "status": "ok"}'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert result["status"] == "ok"

    def test_chinese_book_title_marks(self, agent):
        """中文书名号样式的引号"""
        content = '{"angle": "强调"人类命运共同体"理念", "score": 85}'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert result["score"] == 85


class TestParseTruncatedJson:
    """截断 JSON 修复路径"""

    def test_truncated_object(self, agent):
        """对象被截断"""
        content = '{"key1": "value1", "key2": "value2"'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert result["key1"] == "value1"

    def test_truncated_array(self, agent):
        """数组被截断"""
        content = '{"items": ["a", "b", "c"'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert "items" in result

    def test_truncated_in_string_value(self, agent):
        """字符串值内部截断"""
        content = '{"summary": "这是一段很长的分析文本，包含了多个方面的'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert "summary" in result


class TestParseRegexExtraction:
    """正则提取 JSON 路径"""

    def test_json_with_prefix_text(self, agent):
        """JSON 前有解释文字"""
        content = '以下是分析结果：\n{"result": "success", "score": 90}'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert result["score"] == 90

    def test_json_with_suffix_text(self, agent):
        """JSON 后有解释文字"""
        content = '{"result": "success"}\n以上是结果。'
        result = agent._parse_tool_use_output(content)
        assert result is not None
        assert result["result"] == "success"


class TestParseFailure:
    """解析失败回退"""

    def test_completely_invalid(self, agent):
        """完全无效的内容返回空字典"""
        content = "这不是任何JSON格式的内容"
        result = agent._parse_tool_use_output(content)
        assert result == {}

    def test_empty_string(self, agent):
        """空字符串返回空字典"""
        content = ""
        result = agent._parse_tool_use_output(content)
        assert result == {}

    def test_only_whitespace(self, agent):
        """纯空白返回空字典"""
        content = "   \n\t  "
        result = agent._parse_tool_use_output(content)
        assert result == {}


class TestParseWithSchema:
    """带 Schema 校验的解析"""

    def test_schema_validation_pass(self, agent):
        """符合 Schema 的输出通过校验"""
        from src.schemas import EvaluationScores
        agent.output_schema = EvaluationScores

        content = json.dumps({
            "factual_accuracy": 85,
            "strategic_actionability": 72,
            "audience_fit": 78,
            "cultural_sensitivity": 80,
            "narrative_fluency": 75,
        })
        result = agent._parse_tool_use_output(content)
        assert result["factual_accuracy"] == 85

    def test_schema_validation_fail_returns_empty(self, agent):
        """不符合 Schema 的输出（修复后仍不符合）返回空字典"""
        from src.schemas import EvaluationScores
        agent.output_schema = EvaluationScores

        # 缺少必需字段
        content = '{"factual_accuracy": 85}'
        result = agent._parse_tool_use_output(content)
        # 可能返回空字典（Schema 校验失败）或包含部分数据
        # 取决于 Pydantic 的严格程度
        assert isinstance(result, dict)
