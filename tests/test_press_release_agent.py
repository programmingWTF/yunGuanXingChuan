"""
云观星传 - 新闻传播建议稿 Agent 单元测试（mock LLM）
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
    """创建 PressReleaseAgent，注入 mock LLM 客户端"""
    with patch('src.llm_client.OpenAI'), patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.press_release_agent import PressReleaseAgent
        a = PressReleaseAgent(llm_client=mock_client)
        a.llm_client = mock_client
        yield a, mock_client


class TestPressReleaseAgent:
    """新闻传播建议稿 Agent 测试"""

    def test_schema_valid(self):
        """PressReleaseDraft schema 全字段往返"""
        from src.schemas import PressReleaseDraft
        draft = PressReleaseDraft(
            topic="嫦娥六号",
            communication_goals=["提升公众认知"],
            recommended_titles=["人类首次月背采样返回"],
            lead_suggestions=["导语建议"],
            body_framework=["正文框架"],
            interview_subjects=["吴伟仁｜总设计师｜官方信源"],
            image_suggestions=["着陆器画面｜俯拍"],
            platform_suggestions=["微信公众号｜图文"],
            evidence_sources=["新华社"],
            note="助传说明",
        )
        data = draft.model_dump()
        assert data["topic"] == "嫦娥六号"
        assert len(data["interview_subjects"]) == 1

    def test_build_user_prompt_contains_topic(self, agent):
        """user prompt 应包含议题与素材"""
        a, _ = agent
        prompt = a._build_user_prompt({"topic": "嫦娥六号", "science_facts": {"key_facts": ["test"]}})
        assert "嫦娥六号" in prompt
        assert "key_facts" in prompt

    def test_run_with_mock_llm(self, agent):
        """mock LLM 返回合法 JSON 时应成功解析为 schema"""
        a, mock_client = agent
        mock_client.chat_json.return_value = {
            "topic": "嫦娥六号",
            "communication_goals": ["目标1"],
            "recommended_titles": ["标题1"],
            "lead_suggestions": ["导语1"],
            "body_framework": ["框架1"],
            "interview_subjects": ["人物1"],
            "image_suggestions": ["配图1"],
            "platform_suggestions": ["平台1"],
            "evidence_sources": ["新华社"],
            "note": "说明",
        }
        result = a.run({"topic": "嫦娥六号"})
        assert result["topic"] == "嫦娥六号"
        assert result["lead_suggestions"] == ["导语1"]

    def test_get_agent_info(self, agent):
        """agent 信息应包含描述"""
        a, _ = agent
        info = a.get_agent_info()
        assert info["name"] == "press_release_agent"
        assert "助传" in info["description"]
