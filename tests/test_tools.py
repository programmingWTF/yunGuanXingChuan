"""
云观星传 - Agent 工具集单元测试
验证工具注册、执行器映射、搜索链路正确性
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock


class TestToolRegistry:
    """工具注册表测试"""

    def test_all_tools_registered(self):
        """验证所有工具都有定义和执行器"""
        from src.agents.tools import AGENT_TOOLS, TOOL_REGISTRY, TOOL_EXECUTORS

        for tool_def in AGENT_TOOLS:
            name = tool_def["function"]["name"]
            assert name in TOOL_REGISTRY, f"工具 {name} 未在 TOOL_REGISTRY 中注册"
            assert name in TOOL_EXECUTORS, f"工具 {name} 未在 TOOL_EXECUTORS 中注册"

    def test_tool_definitions_valid(self):
        """验证工具定义格式正确（OpenAI Function Calling 格式）"""
        from src.agents.tools import AGENT_TOOLS

        for tool_def in AGENT_TOOLS:
            assert tool_def["type"] == "function"
            func = tool_def["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"
            assert "properties" in func["parameters"]

    def test_search_web_tool_exists(self):
        """验证 search_web 双引擎工具已注册"""
        from src.agents.tools import TOOL_REGISTRY
        assert "search_web" in TOOL_REGISTRY
        desc = TOOL_REGISTRY["search_web"]["function"]["description"]
        assert "Tavily" in desc
        assert "百炼" in desc or "WebSearch" in desc

    def test_search_news_tool_exists(self):
        """验证 search_news 工具已注册"""
        from src.agents.tools import TOOL_REGISTRY
        assert "search_news" in TOOL_REGISTRY

    def test_get_tools_for_agent(self):
        """验证按名称获取工具子集"""
        from src.agents.tools import get_tools_for_agent
        tools = get_tools_for_agent(["search_web", "search_news"])
        assert len(tools) == 2
        names = [t["function"]["name"] for t in tools]
        assert "search_web" in names
        assert "search_news" in names

    def test_get_tools_unknown_name(self):
        """验证未知工具名不报错，只跳过"""
        from src.agents.tools import get_tools_for_agent
        tools = get_tools_for_agent(["nonexistent_tool"])
        assert tools == []


class TestToolExecutors:
    """工具执行器测试（Mock 外部依赖）"""

    def test_execute_tool_unknown(self):
        """验证未知工具返回错误 JSON"""
        import json
        from src.agents.tools import execute_tool
        result = execute_tool("nonexistent_tool", {})
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("src.search.tavily_search.get_search_service")
    def test_search_news_calls_tavily(self, mock_get_service):
        """验证 search_news 调用 Tavily"""
        import json
        from src.agents.tools import execute_tool

        # Mock Tavily
        mock_tavily = MagicMock()
        mock_source = MagicMock()
        mock_source.title = "Test Title"
        mock_source.content = "Test content"
        mock_source.url = "https://example.com"
        mock_tavily.search.return_value = [mock_source]
        mock_get_service.return_value = mock_tavily

        # Mock QwenWebSearch
        with patch("src.search.qwen_websearch.QwenWebSearchService") as mock_qwen_cls:
            mock_qwen = MagicMock()
            mock_qwen.search.return_value = []
            mock_qwen_cls.return_value = mock_qwen

            result = json.loads(execute_tool("search_news", {"query": "test"}))
            assert result["count"] >= 1
            assert result["results"][0]["source"] == "TavilySearch"

    @patch("src.search.tavily_search.get_search_service")
    def test_search_web_parallel(self, mock_get_service):
        """验证 search_web 并行调用双引擎"""
        import json
        from src.agents.tools import execute_tool

        # Mock Tavily
        mock_tavily = MagicMock()
        mock_source = MagicMock()
        mock_source.title = "Tavily Result"
        mock_source.content = "Content from Tavily"
        mock_source.url = "https://tavily.com"
        mock_tavily.search.return_value = [mock_source]
        mock_get_service.return_value = mock_tavily

        # Mock Qwen
        with patch("src.search.qwen_websearch.QwenWebSearchService") as mock_qwen_cls:
            mock_qwen = MagicMock()
            mock_qwen.search.return_value = [
                {"title": "Qwen Result", "snippet": "Content from Qwen", "url": "https://qwen.com"}
            ]
            mock_qwen_cls.return_value = mock_qwen

            result = json.loads(execute_tool("search_web", {"query": "test"}))
            assert result["count"] == 2
            assert result["engines"]["tavily"] == 1
            assert result["engines"]["qwen"] == 1
            sources = [r["source"] for r in result["results"]]
            assert "TavilySearch" in sources
            assert "QwenWebSearch" in sources


class TestAgentSearchConfig:
    """验证所有 Agent 的搜索配置"""

    def test_all_agents_enable_search(self):
        """验证所有 Agent 启用了 enable_search"""
        from src.agents.science_agent import ScienceAgent
        from src.agents.context_agent import ContextAgent
        from src.agents.humanist_agent import HumanistAgent
        from src.agents.hypothesis_agent import HypothesisAgent
        from src.agents.strategy_agent import StrategyAgent
        from src.agents.evaluator_agent import EvaluatorAgent
        from src.parliament.speaker import SpeakerAgent

        agents = [ScienceAgent, ContextAgent, HumanistAgent,
                  HypothesisAgent, StrategyAgent, EvaluatorAgent, SpeakerAgent]
        for cls in agents:
            assert cls.enable_search is True, f"{cls.__name__} 未启用 enable_search"

    def test_all_agents_have_search_tools(self):
        """验证所有 Agent 的 agent_tools 包含搜索工具"""
        from src.agents.science_agent import ScienceAgent
        from src.agents.context_agent import ContextAgent
        from src.agents.humanist_agent import HumanistAgent
        from src.agents.hypothesis_agent import HypothesisAgent
        from src.agents.strategy_agent import StrategyAgent
        from src.agents.evaluator_agent import EvaluatorAgent
        from src.parliament.speaker import SpeakerAgent

        agents = [ScienceAgent, ContextAgent, HumanistAgent,
                  HypothesisAgent, StrategyAgent, EvaluatorAgent, SpeakerAgent]
        for cls in agents:
            has_search = "search_news" in cls.agent_tools or "search_web" in cls.agent_tools
            assert has_search, f"{cls.__name__} 的 agent_tools 缺少搜索工具"

    def test_search_web_in_all_agent_tools(self):
        """验证所有 Agent 都有 search_web 工具"""
        from src.agents.science_agent import ScienceAgent
        from src.agents.context_agent import ContextAgent
        from src.agents.humanist_agent import HumanistAgent
        from src.agents.hypothesis_agent import HypothesisAgent
        from src.agents.strategy_agent import StrategyAgent
        from src.agents.evaluator_agent import EvaluatorAgent
        from src.parliament.speaker import SpeakerAgent

        agents = [ScienceAgent, ContextAgent, HumanistAgent,
                  HypothesisAgent, StrategyAgent, EvaluatorAgent, SpeakerAgent]
        for cls in agents:
            assert "search_web" in cls.agent_tools, f"{cls.__name__} 缺少 search_web"


class TestDebateSearchInjection:
    """验证辩论中搜索上下文注入"""

    def test_debate_prompt_includes_search_context(self):
        """验证 debate_speech prompt 包含 search_context"""
        from src.agents.science_agent import ScienceAgent

        agent = ScienceAgent.__new__(ScienceAgent)
        input_data = {
            "topic": "测试议题",
            "task_type": "debate_speech",
            "current_motion": {"motion_id": "M001", "content": "测试动议"},
            "previous_speeches": [],
            "round_num": 1,
            "search_context": "## 联网搜索内容\n[1] 测试结果",
        }
        prompt = agent._build_user_prompt(input_data)
        assert "联网搜索内容" in prompt
        assert "测试结果" in prompt

    def test_debate_prompt_without_search_context(self):
        """验证无搜索上下文时 prompt 正常"""
        from src.agents.science_agent import ScienceAgent

        agent = ScienceAgent.__new__(ScienceAgent)
        input_data = {
            "topic": "测试议题",
            "task_type": "debate_speech",
            "current_motion": {"motion_id": "M001", "content": "测试动议"},
            "previous_speeches": [],
            "round_num": 1,
        }
        prompt = agent._build_user_prompt(input_data)
        assert "测试议题" in prompt
        assert "联网搜索内容" not in prompt


class TestFallbackResult:
    """验证兜底结果生成"""

    def test_evaluation_fallback(self):
        """验证 EvaluationResult 兜底包含所有必填字段"""
        from src.agents.evaluator_agent import EvaluatorAgent

        agent = EvaluatorAgent.__new__(EvaluatorAgent)
        agent.output_schema = EvaluatorAgent.output_schema
        fallback = agent._get_fallback_result()
        assert "scores" in fallback
        assert "experience_log" in fallback
        assert "passed" in fallback
        assert "feedback" in fallback
        assert "audience_simulation" in fallback

    def test_strategy_fallback(self):
        """验证 StrategySet 兜底包含所有必填字段"""
        from src.agents.strategy_agent import StrategyAgent

        agent = StrategyAgent.__new__(StrategyAgent)
        agent.output_schema = StrategyAgent.output_schema
        fallback = agent._get_fallback_result()
        assert "topic" in fallback
        assert "strategies" in fallback


# ══════════════════════════════════════════════════════════════
# 以下为补充测试：单个工具执行器（KG / RAG / Wikipedia / 外部校验）
# ══════════════════════════════════════════════════════════════


class TestExecQueryKnowledgeGraph:
    """KG 查询工具测试"""

    def test_entity_found(self):
        from src.agents.tools import _exec_query_knowledge_graph
        mock_kg = MagicMock()
        mock_kg.find_related_entities.return_value = [
            {"entity": "长征五号", "relation": "launched_by", "direction": "outgoing", "depth": 1}]
        with patch('src.knowledge.kg_builder.get_knowledge_graph', return_value=mock_kg):
            result = _exec_query_knowledge_graph("嫦娥六号")
        assert result["found"] is True
        assert result["count"] == 1
        mock_kg.find_related_entities.assert_called_once_with("嫦娥六号", depth=2)

    def test_entity_not_found(self):
        from src.agents.tools import _exec_query_knowledge_graph
        mock_kg = MagicMock()
        mock_kg.find_related_entities.return_value = []
        with patch('src.knowledge.kg_builder.get_knowledge_graph', return_value=mock_kg):
            result = _exec_query_knowledge_graph("未知实体")
        assert result["found"] is False
        assert "未找到" in result["message"]

    def test_depth_capped_at_3(self):
        from src.agents.tools import _exec_query_knowledge_graph
        mock_kg = MagicMock()
        mock_kg.find_related_entities.return_value = []
        with patch('src.knowledge.kg_builder.get_knowledge_graph', return_value=mock_kg):
            _exec_query_knowledge_graph("x", depth=99)
        # depth 被 min(depth, 3) 限制
        assert mock_kg.find_related_entities.call_args.kwargs["depth"] == 3


class TestExecSearchRag:
    """RAG 检索工具测试"""

    def test_empty_index(self):
        from src.agents.tools import _exec_search_rag_knowledge
        vs = MagicMock()
        vs.index.ntotal = 0
        with patch('src.knowledge.vector_store.get_vector_store', return_value=vs):
            result = _exec_search_rag_knowledge("嫦娥六号")
        assert result["results"] == []
        assert "向量库为空" in result["message"]

    def test_returns_results(self):
        from src.agents.tools import _exec_search_rag_knowledge
        vs = MagicMock()
        vs.index.ntotal = 10
        vs.search.return_value = [
            {"text": "月球采样返回" * 50, "score": 0.92, "metadata": {}},
            {"text": "短文", "score": 0.5, "metadata": {}},
        ]
        with patch('src.knowledge.vector_store.get_vector_store', return_value=vs):
            result = _exec_search_rag_knowledge("月球")
        assert result["count"] == 2
        assert len(result["results"][0]["text"]) <= 300  # 截断
        assert result["results"][0]["score"] == 0.92


class TestExecSearchWikipedia:
    """Wikipedia 搜索工具测试（mock httpx）"""

    def test_success_flow(self):
        from src.agents.tools import _exec_search_wikipedia
        fake_client = MagicMock()
        # 支持 with 上下文协议：__enter__ 返回自身
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        search_resp = MagicMock()
        search_resp.json.return_value = {"query": {"search": [{"title": "嫦娥六号"}, {"title": "嫦娥五号"}]}}
        extract_resp = MagicMock()
        extract_resp.json.return_value = {"query": {"pages": {"1": {"extract": "嫦娥六号是中国探月任务"}}}}
        fake_client.get.side_effect = [search_resp, extract_resp]
        with patch('httpx.Client', return_value=fake_client) as MockClient:
            result = _exec_search_wikipedia("嫦娥六号")
        assert result["title"] == "嫦娥六号"
        assert result["extract"] == "嫦娥六号是中国探月任务"
        assert result["other_titles"] == ["嫦娥五号"]
        MockClient.assert_called_once_with(timeout=5.0, follow_redirects=True)

    def test_no_titles(self):
        from src.agents.tools import _exec_search_wikipedia
        fake_client = MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = False
        search_resp = MagicMock()
        search_resp.json.return_value = {"query": {"search": []}}
        fake_client.get.return_value = search_resp
        with patch('httpx.Client', return_value=fake_client):
            result = _exec_search_wikipedia("不存在的话题")
        assert result["results"] == []

    def test_exception_degraded(self):
        from src.agents.tools import _exec_search_wikipedia
        with patch('httpx.Client', side_effect=ConnectionError("no net")):
            result = _exec_search_wikipedia("嫦娥六号")
        assert "error" in result


class TestExecVerifyExternal:
    """外部校验工具测试"""

    def test_validates_claim(self):
        from src.agents.tools import _exec_verify_claim_external
        validator = MagicMock()
        validator.validate.return_value = {"status": "verified", "confidence": 0.9}
        with patch('src.verification.external_validator.get_external_validator', return_value=validator):
            result = _exec_verify_claim_external("嫦娥六号2024年发射", ["嫦娥六号"])
        assert result["status"] == "verified"
        validator.validate.assert_called_once_with("嫦娥六号2024年发射", entities=["嫦娥六号"])


class TestExecuteToolErrors:
    """execute_tool 错误路径测试"""

    def test_unknown_tool_returns_error_json(self):
        from src.agents.tools import execute_tool
        import json
        out = execute_tool("not_a_tool", {})
        assert json.loads(out)["error"] == "未知工具: not_a_tool"

    def test_executor_exception_returns_error_json(self):
        from src.agents.tools import execute_tool, TOOL_EXECUTORS
        import json
        with patch.dict(TOOL_EXECUTORS, {"boom": lambda **k: (_ for _ in ()).throw(RuntimeError("炸了"))}):
            out = execute_tool("boom", {})
        parsed = json.loads(out)
        assert "error" in parsed
        assert "工具执行失败" in parsed["error"]
        assert parsed["tool"] == "boom"

    def test_executor_json_serializable(self):
        """带非 JSON 类型返回值也应序列化成功（default=str）"""
        from src.agents.tools import execute_tool, TOOL_EXECUTORS
        import json
        with patch.dict(TOOL_EXECUTORS, {"weird": lambda **k: {"dt": object()}}):
            out = execute_tool("weird", {})
        assert '"dt"' in out
