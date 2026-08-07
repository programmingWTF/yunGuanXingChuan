"""
云观星传 - 国际传播策略报告 Agent 单元测试（mock LLM / data_loader）
补齐 strategy_report_agent.py 的测试覆盖（此前为 0%）
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


@pytest.fixture
def agent():
    """创建 StrategyReportAgent，注入 mock LLM 客户端与 data_loader"""
    with patch('src.llm_client.OpenAI'), \
         patch('src.agents.base_agent.get_llm_client') as mock_get, \
         patch('src.agents.strategy_report_agent.get_data_loader') as mock_dl:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        mock_loader = MagicMock()
        mock_loader.load_audience_profiles.return_value = {
            "international_media": {"name": "国际媒体", "concerns": ["客观性"]},
            "domestic_public": {"name": "国内公众", "concerns": ["自豪感"]},
        }
        mock_dl.return_value = mock_loader
        from src.agents.strategy_report_agent import StrategyReportAgent
        a = StrategyReportAgent(llm_client=mock_client)
        a.llm_client = mock_client
        yield a, mock_client


class TestStrategyReportAgent:
    """国际传播策略报告 Agent 测试"""

    def test_agent_name_and_info(self, agent):
        a, _ = agent
        info = a.get_agent_info()
        assert info["name"] == "strategy_report_agent"
        assert "传播策略" in info["description"]
        assert info["output"] == "CommunicationStrategyReport (JSON)"

    def test_class_attributes(self):
        from src.agents.strategy_report_agent import StrategyReportAgent
        from src.schemas import CommunicationStrategyReport
        assert StrategyReportAgent.output_schema is CommunicationStrategyReport
        assert StrategyReportAgent.enable_search is True
        assert "search_news" in StrategyReportAgent.agent_tools

    def test_build_user_prompt_contains_topic_and_facts(self, agent):
        a, _ = agent
        prompt = a._build_user_prompt({
            "topic": "嫦娥六号",
            "science_facts": {"key_facts": ["月背采样"]},
            "context_analysis": {"framework": "competition"},
            "strategies": [{"name": "科技叙事"}],
            "final_report": {"summary": "议会总结"},
        })
        assert "嫦娥六号" in prompt
        assert "月背采样" in prompt
        assert "competition" in prompt
        assert "科技叙事" in prompt
        assert "国际媒体" in prompt  # 受众画像被注入

    def test_build_user_prompt_defaults(self, agent):
        a, _ = agent
        # 空输入时使用默认议题
        prompt = a._build_user_prompt({})
        assert "嫦娥六号" in prompt

    def test_build_user_prompt_mingming_requirements(self, agent):
        """生成要求应包含具体对比、媒体、标题、风险、证据五要素"""
        a, _ = agent
        prompt = a._build_user_prompt({"topic": "嫦娥六号"})
        assert "china_media_differences" in prompt
        assert "recommended_media" in prompt
        assert "recommended_titles" in prompt
        assert "risk_warnings" in prompt
        assert "evidence_sources" in prompt

    def test_schema_roundtrip(self):
        """CommunicationStrategyReport schema 全字段往返"""
        from src.schemas import CommunicationStrategyReport, MediaRecommendation
        report = CommunicationStrategyReport(
            topic="嫦娥六号",
            target_countries=["美国", "法国"],
            recommended_media=[MediaRecommendation(media="新华社", reason="权威")],
            evidence_sources=["新华社"],
        )
        data = report.model_dump()
        assert data["topic"] == "嫦娥六号"
        assert len(data["target_countries"]) == 2
        assert data["recommended_media"][0]["media"] == "新华社"