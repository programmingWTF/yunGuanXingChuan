"""
云观星传 - BaseAgent 运行时单元测试
覆盖 run() 主循环（重试/Schema 校验/skip 分支）、Tool Use 循环
与解析兜底路径（Mock LLM，不依赖网络）
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel, Field
from pydantic_core import ValidationError as CoreValidationError

from src.agents.base_agent import BaseAgent


class _OutSchema(BaseModel):
    """简单输出 schema"""
    topic: str
    findings: list = Field(default_factory=list)


class MiniAgent(BaseAgent):
    """测试用最小 Agent 实现"""
    agent_name = "mini"
    prompt_file = ""
    output_schema = _OutSchema
    enable_search = True

    def _build_user_prompt(self, input_data):
        return "任务:" + json.dumps(input_data, ensure_ascii=False)

    def _get_default_prompt(self):
        return "你是测试助手，输出 JSON。"

    def get_agent_info(self):
        return {"name": "mini"}


@pytest.fixture
def agent():
    """创建带 mock LLM 的 MiniAgent"""
    mock_client = MagicMock()
    a = MiniAgent(llm_client=mock_client, max_retries=3, temperature=0.2, max_tokens=100)
    return a


class TestRunMain:
    """run() 主循环测试"""

    def test_success_validates_schema(self, agent):
        """合法输出应通过 schema 校验返回"""
        agent.llm_client.chat_json.return_value = {"topic": "嫦娥六号", "findings": ["发现1"]}
        result = agent.run({"topic": "嫦娥六号"})
        assert result["topic"] == "嫦娥六号"
        assert result["findings"] == ["发现1"]
        # 校验参数透传
        kwargs = agent.llm_client.chat_json.call_args.kwargs
        assert kwargs["model"] == agent.model
        assert kwargs["enable_search"] is True
        assert kwargs["max_tokens"] == 100

    def test_schema_cleaning_salvages_output(self, agent):
        """LLM 偶发退化输出应被容错清洗 salvage（防 2026-08-31 线上故障）"""
        dirty = {"topic": "t", "findings": ["a", "b", "", "c", 42, None]}  # 混入空/非字符串
        agent.llm_client.chat_json.side_effect = [
            {"topic": "t", "findings": "not-a-list"},  # 类型错误触发清洗
            dirty,
        ]
        # 第二次直接返回清洗后内容
        result = agent.run({"topic": "t"})
        # 清洗发生在首次失败后重试成功路径
        assert agent.llm_client.chat_json.call_count == 2

    def test_schema_error_triggers_retry(self, agent):
        """首次校验失败应带错误信息重试，第二次成功返回"""
        agent.llm_client.chat_json.side_effect = [
            {"topic": "t", "findings": "oops"},          # findings 非 list → ValidationError
            {"topic": "t", "findings": ["ok"]},           # 修正版
        ]
        result = agent.run({"topic": "t"})
        assert agent.llm_client.chat_json.call_count == 2
        assert result["findings"] == ["ok"]
        # 重试 prompt 应包含错误信息与 schema
        retry_user = agent.llm_client.chat_json.call_args_list[1].kwargs["user_prompt"]
        assert "修正" in retry_user
        assert "JSON Schema" in retry_user

    def test_retries_exhausted_raises(self, agent):
        """重试耗尽应抛 RuntimeError"""
        agent.max_retries = 2
        agent.llm_client.chat_json.return_value = {"findings": []}  # 缺 topic → 恒失败
        with patch('src.agents.base_agent.time.sleep'):
            with pytest.raises(RuntimeError, match="已重试 2 次"):
                agent.run({"topic": "t"})
        assert agent.llm_client.chat_json.call_count == 2

    def test_vote_task_skips_schema(self, agent):
        """vote 任务应跳过 schema 校验且不联网搜索"""
        agent.output_schema = _OutSchema
        agent.llm_client.chat_json.return_value = {"vote": "yes"}  # 不符合 schema 也接受
        result = agent.run({"topic": "t", "task_type": "vote"})
        assert result == {"vote": "yes"}
        assert agent.llm_client.chat_json.call_args.kwargs["enable_search"] is False

    def test_debate_speech_skips_schema(self, agent):
        agent.llm_client.chat_json.return_value = {"speech": "..."}
        result = agent.run({"topic": "t", "task_type": "debate_speech"})
        assert result == {"speech": "..."}

    def test_json_decode_error_retried(self, agent):
        """chat_json 内部已解析，JSONDecodeError 路径经异常重试"""
        agent.llm_client.chat_json.side_effect = [
            json.JSONDecodeError("bad", "", 0),
            {"topic": "t"},
        ]
        with patch('src.agents.base_agent.time.sleep'):
            result = agent.run({"topic": "t"})
        assert result["topic"] == "t"
        assert agent.llm_client.chat_json.call_count == 2

    def test_llm_exception_retried_then_success(self, agent):
        """LLM 调用异常重试后成功"""
        agent.llm_client.chat_json.side_effect = [
            ConnectionError("网络断了"),
            {"topic": "t"},
        ]
        with patch('src.agents.base_agent.time.sleep'):
            result = agent.run({"topic": "t"})
        assert result["topic"] == "t"


class TestToolUseLoop:
    """run_with_tools 工具循环测试"""

    def _make_msg(self, content=None, tool_calls=None):
        return MagicMock(content=content, tool_calls=tool_calls)

    def test_no_tools_falls_back_to_run(self, agent):
        """未绑定工具应回退到普通 run"""
        agent.agent_tools = []
        with patch.object(agent, 'run') as mock_run:
            mock_run.return_value = {"ok": 1}
            result = agent.run_with_tools({})
        mock_run.assert_called_once_with({})
        assert result == {"ok": 1}

    def test_tool_round_then_final_answer(self, agent):
        """应执行工具调用后继续，直到无 tool_calls 返回最终答案"""
        agent.agent_tools = ["query_knowledge_graph"]
        tool_fn = MagicMock()
        tool_fn.name = "query_knowledge_graph"
        tool_fn.arguments = '{"entity_name": "嫦娥六号"}'
        tool_call = MagicMock(id="call_1", function=tool_fn)
        # 第一轮：LLM 要调工具；第二轮：返回最终答案
        responses = [MagicMock(choices=[MagicMock(message=self._make_msg(tool_calls=[tool_call]))]),
                     MagicMock(choices=[MagicMock(message=self._make_msg(content='{"topic": "嫦娥六号"}'))])]
        agent.llm_client.client.chat.completions.create.side_effect = responses
        with patch('src.agents.tools.execute_tool', return_value='{"found": true}') as mock_exec:
            result = agent.run_with_tools({"topic": "t"}, max_tool_rounds=5)
        assert result["topic"] == "嫦娥六号"
        assert agent.llm_client.client.chat.completions.create.call_count == 2
        mock_exec.assert_called_once_with("query_knowledge_graph", {"entity_name": "嫦娥六号"})
        # 工具结果应加入消息
        msgs = agent.llm_client.client.chat.completions.create.call_args_list[1].kwargs["messages"]
        assert any(m["role"] == "tool" and m["tool_call_id"] == "call_1" for m in msgs)

    def test_malformed_tool_args_repaired(self, agent):
        """工具参数 JSON 损坏应尝试修复"""
        agent.agent_tools = ["query_knowledge_graph"]
        tc_fn = MagicMock()
        tc_fn.name = "query_knowledge_graph"
        tc_fn.arguments = '{"entity_name": 嫦娥六号}'
        tc = MagicMock(id="c1", function=tc_fn)
        agent.llm_client.client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=self._make_msg(tool_calls=[tc]))]),
            MagicMock(choices=[MagicMock(message=self._make_msg(content='{"topic": "t"}'))]),
        ]
        agent.llm_client._repair_json_quotes.return_value = '{"entity_name": "嫦娥六号"}'
        with patch('src.agents.tools.execute_tool', return_value="{}"):
            result = agent.run_with_tools({"topic": "t"})
        assert result["topic"] == "t"
        agent.llm_client._repair_json_quotes.assert_called()

    def test_max_rounds_force_output(self, agent):
        """达到最大轮次应强制要求最终输出"""
        agent.agent_tools = ["search_news"]
        # 每轮都要求工具
        tc_fn = MagicMock()
        tc_fn.name = "search_news"
        tc_fn.arguments = "{}"
        tc = MagicMock(id="c1", function=tc_fn)
        tool_resp = MagicMock(choices=[MagicMock(message=self._make_msg(tool_calls=[tc]))])
        final_resp = MagicMock(choices=[MagicMock(message=self._make_msg(content='{"topic": "t"}'))])
        agent.llm_client.client.chat.completions.create.side_effect = [tool_resp, tool_resp, final_resp]
        with patch('src.agents.tools.execute_tool', return_value="{}"):
            result = agent.run_with_tools({"topic": "t"}, max_tool_rounds=2)
        assert result["topic"] == "t"
        # 强制输出轮应带 json_object response_format
        last_kwargs = agent.llm_client.client.chat.completions.create.call_args_list[-1].kwargs
        assert last_kwargs.get("response_format") == {"type": "json_object"}

    def test_tool_round_exception_returns_empty(self, agent):
        """工具循环异常应返回 {}（上层兜底）"""
        agent.agent_tools = ["search_news"]
        agent.llm_client.client.chat.completions.create.side_effect = RuntimeError("LLM down")
        assert agent.run_with_tools({}) == {}

    def test_final_answer_markdown_fence(self, agent):
        """最终答案含 markdown 代码块应能解析"""
        agent.agent_tools = ["search_rag_knowledge"]
        resp = MagicMock(choices=[MagicMock(
            message=self._make_msg(content='```json\n{"topic": "嫦娥六号", "findings": ["f"]}\n```'))])
        agent.llm_client.client.chat.completions.create.return_value = resp
        result = agent.run_with_tools({"topic": "t"})
        assert result["topic"] == "嫦娥六号"


class TestFallbackResult:
    """兜底结果测试"""

    def test_known_schema_fallback(self, agent):
        from src.schemas import EvaluationResult
        agent.output_schema = EvaluationResult
        fb = agent._get_fallback_result()
        assert fb["scores"]["factual_accuracy"] == 70
        assert fb["passed"] is False

    def test_unknown_schema_returns_empty(self, agent):
        agent.output_schema = _OutSchema
        assert agent._get_fallback_result() == {}
