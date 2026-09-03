"""
云观星传 - 核心分析 Agent Prompt 构造单元测试
覆盖 Humanist / Evaluator / Hypothesis / Strategy / Context 五个 Agent 的
user prompt 构造、task_type 路由（议会辩论）与 agent_info（Mock LLM/数据加载）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


def _make_agent(module_path, class_name):
    """按现有测试模式构造带 mock LLM 的 Agent

    BaseAgent.__init__ 中调用 get_llm_client()，打点在 base_agent 上。
    """
    with patch('src.llm_client.OpenAI'), \
         patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        agent = cls(llm_client=mock_client)
        agent.llm_client = mock_client
        return agent


@pytest.fixture
def humanist():
    return _make_agent('src.agents.humanist_agent', 'HumanistAgent')


@pytest.fixture
def hypothesis():
    return _make_agent('src.agents.hypothesis_agent', 'HypothesisAgent')


@pytest.fixture
def strategy():
    return _make_agent('src.agents.strategy_agent', 'StrategyAgent')


@pytest.fixture
def context():
    return _make_agent('src.agents.context_agent', 'ContextAgent')


@pytest.fixture
def evaluator():
    return _make_agent('src.agents.evaluator_agent', 'EvaluatorAgent')


class TestHumanistPrompts:
    """人文学者 Agent 测试"""

    def test_default_is_cultural_review(self, humanist):
        """无 task_type 时应构造文化审查 prompt"""
        prompt = humanist._build_user_prompt({"topic": "嫦娥六号"})
        assert "嫦娥六号" in prompt

    def test_opening_report_route(self, humanist):
        """opening_report 应路由到开幕报告 prompt"""
        prompt = humanist._build_user_prompt({
            "topic": "天问三号", "task_type": "opening_report",
        })
        assert "天问三号" in prompt
        # 与文化审查 prompt 不同路径：开幕报告应包含立场/角色表述
        assert "人文学者" in prompt or "人文" in prompt

    def test_debate_speech_route(self, humanist):
        """debate_speech 应构造辩论发言 prompt"""
        prompt = humanist._build_user_prompt({
            "topic": "嫦娥六号", "task_type": "debate_speech",
            "current_motion": {"motion": "测试动议"}, "debate_summary": "前轮摘要",
        })
        assert "嫦娥六号" in prompt

    def test_vote_route_contains_criteria(self, humanist):
        """vote prompt 应包含投票标准与动议内容"""
        prompt = humanist._build_user_prompt({
            "task_type": "vote",
            "current_motion": {"motion": "发布月球科研站报道"},
            "debate_summary": "双方已充分辩论",
        })
        assert "投票表决" in prompt
        assert "月球科研站报道" in prompt
        assert "yes/no/abstain" in prompt

    def test_get_agent_info(self, humanist):
        info = humanist.get_agent_info()
        assert info["name"] == "humanist"
        assert info["prompt_file"]


class TestHypothesisPrompts:
    """假设生成 Agent 测试"""

    def test_user_prompt_contains_topic_and_facts(self, hypothesis):
        prompt = hypothesis._build_user_prompt({
            "topic": "嫦娥六号",
            "science_facts": {"key_facts": ["2024年6月25日返回"]},
            "context_analysis": {"frameworks": ["competition"]},
        })
        assert "嫦娥六号" in prompt
        assert "科学事实" in prompt
        assert "假设" in prompt

    def test_debate_route(self, hypothesis):
        prompt = hypothesis._build_user_prompt({
            "task_type": "debate_speech", "topic": "嫦娥六号",
            "current_motion": {}, "debate_summary": "",
        })
        assert "嫦娥六号" in prompt

    def test_vote_route(self, hypothesis):
        prompt = hypothesis._build_user_prompt({
            "task_type": "vote",
            "current_motion": {"motion": "假设H1成立"},
            "debate_summary": "摘要",
        })
        assert "投票" in prompt
        assert "假设H1成立" in prompt

    def test_get_agent_info(self, hypothesis):
        info = hypothesis.get_agent_info()
        assert info["name"] == "hypothesis_agent"
        assert "HypothesisSet" in info["output"]


class TestStrategyPrompts:
    """策略转译 Agent 测试"""

    def test_user_prompt_contains_audiences(self, strategy):
        """prompt 应包含议题与受众画像内容"""
        prompt = strategy._build_user_prompt({
            "topic": "嫦娥六号",
            "science_facts": {"key_facts": ["事实"]},
            "hypotheses": [{"hypothesis_id": "H001", "statement": "假设一"}],
        })
        assert "嫦娥六号" in prompt
        assert "策略" in prompt or "受众" in prompt

    def test_vote_route(self, strategy):
        prompt = strategy._build_user_prompt({
            "task_type": "vote",
            "current_motion": {"motion": "对美受众强化叙事"},
            "debate_summary": "",
        })
        assert "投票" in prompt

    def test_get_agent_info(self, strategy):
        info = strategy.get_agent_info()
        assert info["name"] == "strategy_agent"


class TestContextPrompts:
    """语境分析 Agent 测试"""

    def test_user_prompt_contains_media(self, context):
        """prompt 应包含媒体报道数据段落"""
        prompt = context._build_user_prompt({
            "topic": "嫦娥六号",
            "science_facts": {"key_facts": ["事实"]},
            "search_context": "联网补充信息",
        })
        assert "嫦娥六号" in prompt
        assert "报道框架" in prompt
        assert "联网补充信息" in prompt  # search_context 注入

    def test_search_context_omitted(self, context):
        """无 search_context 时不应报错"""
        prompt = context._build_user_prompt({"topic": "嫦娥六号"})
        assert "嫦娥六号" in prompt

    def test_vote_route(self, context):
        prompt = context._build_user_prompt({
            "task_type": "vote",
            "current_motion": {"motion": "动议"},
            "debate_summary": "",
        })
        assert "投票" in prompt

    def test_get_agent_info(self, context):
        info = context.get_agent_info()
        assert info["name"] == "context_agent"


class TestEvaluatorPrompts:
    """评测 Agent 测试"""

    def test_user_prompt_contains_scores_context(self, evaluator):
        """prompt 应包含待评测策略与迭代轮次"""
        prompt = evaluator._build_user_prompt({
            "topic": "嫦娥六号",
            "strategies": [{"strategy": "针对美国精英的叙事"}],
            "iteration_round": 2,
        })
        assert "嫦娥六号" in prompt
        assert "五维评分" in prompt
        assert "第 2 轮" in prompt
        assert "针对美国精英的叙事" in prompt

    def test_previous_feedback_included(self, evaluator):
        """上一轮反馈应注入 prompt"""
        prompt = evaluator._build_user_prompt({
            "topic": "嫦娥六号",
            "strategies": [],
            "previous_feedback": ["上轮建议：加强证据链"],
        })
        assert "加强证据链" in prompt

    def test_vote_route(self, evaluator):
        prompt = evaluator._build_user_prompt({
            "task_type": "vote",
            "current_motion": {"motion": "动议"},
            "debate_summary": "",
        })
        assert "投票" in prompt

    def test_get_agent_info(self, evaluator):
        info = evaluator.get_agent_info()
        assert info["name"] == "evaluator_agent"


class TestAgentToolUse:
    """Agent 工具注册测试"""

    def test_tools_module_loadable(self):
        """工具模块应可加载（tool use 基础设施）"""
        from src.agents import tools
        assert tools is not None


class TestScienceAgent:
    """科学理解 Agent 测试"""

    @pytest.fixture
    def science(self):
        with patch('src.llm_client.OpenAI'), \
             patch('src.agents.base_agent.get_llm_client') as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            from src.agents.science_agent import ScienceAgent
            agent = ScienceAgent(llm_client=mock_client)
            agent.llm_client = mock_client
            yield agent

    def test_prompt_contains_topic_and_search_context(self, science):
        """prompt 应包含议题与搜索上下文"""
        with patch.object(science, 'data_loader') as loader:
            loader.load_science_facts.return_value = [{"topic": "嫦娥六号", "key_facts": ["事实"]}]
            prompt = science._build_user_prompt({
                "topic": "嫦娥六号", "search_context": "联网信息XYZ"})
        assert "嫦娥六号" in prompt
        assert "联网信息XYZ" in prompt

    def test_rag_context_injected(self, science):
        """向量检索结果应注入 prompt"""
        with patch.object(science, 'data_loader') as loader:
            loader.load_science_facts.return_value = []
            vs = MagicMock()
            vs.index.ntotal = 5
            vs.search.return_value = [{"text": "RAG片段A"}]
            with patch('src.agents.science_agent.get_vector_store', return_value=vs):
                prompt = science._build_user_prompt({"topic": "天问三号"})
        assert "RAG片段A" in prompt
        assert "RAG 检索" in prompt

    def test_rag_down_degrades(self, science):
        """向量库不可用时应降级不报错"""
        with patch.object(science, 'data_loader') as loader:
            loader.load_science_facts.return_value = []
            with patch('src.agents.science_agent.get_vector_store',
                       side_effect=RuntimeError("vs down")):
                prompt = science._build_user_prompt({"topic": "朱雀二号"})
        assert "朱雀二号" in prompt

    def test_task_type_routes(self, science):
        """debate/vote/opening 路由"""
        for tt in ("debate_speech", "vote", "opening_report"):
            prompt = science._build_user_prompt({"topic": "嫦娥六号", "task_type": tt,
                                                 "current_motion": {}, "debate_summary": ""})
            assert prompt  # 各路由均能生成

    def test_get_agent_info(self, science):
        assert science.get_agent_info()["name"] == "science_agent"


class TestResearchPlanAgent:
    """科研助研 Agent 测试"""

    @pytest.fixture
    def rp_agent(self):
        with patch('src.llm_client.OpenAI'), \
             patch('src.agents.base_agent.get_llm_client') as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            from src.agents.research_plan_agent import ResearchPlanAgent
            agent = ResearchPlanAgent(llm_client=mock_client)
            agent.llm_client = mock_client
            yield agent

    def test_prompt_with_provided_facts(self, rp_agent):
        """显式提供 science_facts 时不再加载本地素材"""
        prompt = rp_agent._build_user_prompt({
            "topic": "嫦娥六号",
            "science_facts": {"key_facts": ["2024年6月25日返回"]},
            "hypotheses": [{"hypothesis_id": "H1", "statement": "假设"}],
        })
        assert "嫦娥六号" in prompt
        assert "2024年6月25日返回" in prompt
        assert "科研层面" in prompt or "科学假设" in prompt

    def test_load_science_material_fallback(self, rp_agent):
        """无上游结果时应从本地三库加载素材"""
        with patch.object(rp_agent, 'data_loader') as loader:
            loader.load_science_facts.return_value = [{"topic": "嫦娥六号", "key_facts": ["本地事实"]}]
            prompt = rp_agent._build_user_prompt({"topic": "嫦娥六号"})
        assert "本地事实" in prompt

    def test_load_material_empty_fallback(self, rp_agent):
        """本地无数据与加载异常都应返回空模板"""
        with patch.object(rp_agent, 'data_loader') as loader:
            loader.load_science_facts.side_effect = RuntimeError("loader down")
            material = rp_agent._load_science_material("新议题")
        assert material["topic"] == "新议题"
        assert material["key_facts"] == []

    def test_get_agent_info(self, rp_agent):
        assert rp_agent.get_agent_info()["name"] == "research_plan_agent"
        assert rp_agent.output_schema is not None
