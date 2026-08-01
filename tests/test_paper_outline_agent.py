"""
云观星传 - 论文大纲 Agent 单元测试（mock LLM）
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
    """创建 PaperOutlineAgent，注入 mock LLM 客户端"""
    with patch('src.llm_client.OpenAI'), patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.paper_outline_agent import PaperOutlineAgent
        a = PaperOutlineAgent(llm_client=mock_client)
        a.llm_client = mock_client
        yield a, mock_client


def _valid_outline_json():
    """构造合法的论文大纲 JSON（8 段结构）"""
    return {
        "topic": "嫦娥六号",
        "paper_title": "月背采样返回的国际传播效果研究",
        "abstract_framework": "背景/方法/结果/意义",
        "introduction_framework": "研究背景/问题/目的",
        "literature_review_framework": "综述范围/分类",
        "method_framework": "数据/方法/工具",
        "result_framework": "主要发现/呈现",
        "discussion_framework": "解释/比较/局限",
        "future_work_framework": "未来方向",
        "research_questions": ["RQ1", "RQ2"],
        "evidence_sources": ["新华社"],
        "note": "助研说明",
    }


class TestPaperOutlineAgent:
    """论文大纲 Agent 测试"""

    def test_schema_valid(self):
        """PaperOutline schema 全字段往返"""
        from src.schemas import PaperOutline
        outline = PaperOutline(**_valid_outline_json())
        data = outline.model_dump()
        assert data["paper_title"].startswith("月背")
        assert len(data["research_questions"]) == 2

    def test_build_user_prompt_contains_topic(self, agent):
        """user prompt 应包含议题"""
        a, _ = agent
        prompt = a._build_user_prompt({"topic": "嫦娥六号", "science_facts": {"key_facts": ["test"]}})
        assert "嫦娥六号" in prompt
        assert "key_facts" in prompt
        assert "不写正文" in prompt  # 助研定位：提示不写正文

    def test_run_with_mock_llm(self, agent):
        """mock LLM 返回合法 JSON 时应成功解析为 schema"""
        a, mock_client = agent
        mock_client.chat_json.return_value = _valid_outline_json()
        result = a.run({"topic": "嫦娥六号"})
        assert result["paper_title"]
        assert result["abstract_framework"]
        assert result["method_framework"]

    def test_get_agent_info(self, agent):
        """agent 信息应包含描述"""
        a, _ = agent
        info = a.get_agent_info()
        assert info["name"] == "paper_outline_agent"
        assert "助研" in info["description"]
