"""
云观星传 - 表达适配 Agent 单元测试（mock LLM）
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
    """创建 ExpressionAdaptationAgent，注入 mock LLM 客户端"""
    with patch('src.llm_client.OpenAI'), patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.expression_adaptation_agent import ExpressionAdaptationAgent
        a = ExpressionAdaptationAgent(llm_client=mock_client)
        a.llm_client = mock_client
        yield a, mock_client


def _valid_adaptation_json():
    """构造合法的表达适配 JSON"""
    return {
        "topic": "嫦娥六号",
        "terms": [
            {"chinese": "天宫", "english": "Tiangong Space Station", "context": "官方译名，学术论文通用"},
            {"chinese": "嫦娥", "english": "Chang'e (Lunar Exploration Program)", "context": "首次出现需括号注释"},
            {"chinese": "月球背面", "english": "far side of the Moon", "context": "注意非 dark side（有歧义）"},
            {"chinese": "采样返回", "english": "sample return mission", "context": "航天领域标准术语"},
            {"chinese": "着陆器", "english": "lander", "context": "区别于 orbiter（轨道器）"},
        ],
        "metaphors": [
            {"chinese": "逐梦星辰", "english": "Reaching for the Stars", "note": "适合社交媒体，学术场合慎用"},
            {"chinese": "弯道超车", "english": "leapfrog development", "note": "直译易误解为赛车，建议意译"},
            {"chinese": "太空丝绸之路", "english": "Space Silk Road", "note": "政治敏感度高，欧美媒体慎用"},
        ],
        "suggestions": [
            {
                "scenario": "欧美主流媒体",
                "recommended": "Global Scientific Cooperation / Lunar Research Milestone",
                "avoid": "民族复兴 / 太空霸权",
                "reason": "避免触发'中国威胁论'框架，聚焦科学合作叙事",
            },
            {
                "scenario": "国际学术期刊",
                "recommended": "sample return from the lunar far side",
                "avoid": "太空竞赛",
                "reason": "学术语境强调客观性，避免冷战隐喻",
            },
            {
                "scenario": "海外社交平台",
                "recommended": "Humanity's first sample from the Moon's far side 🌙",
                "avoid": "",
                "reason": "社交传播需简洁、有感染力，突出'人类首次'",
            },
        ],
        "evidence_sources": ["新华社", "Nature"],
        "note": "整体建议：以'全人类科学探索'为主框架，弱化国家竞争叙事，强化国际合作与科学价值。",
    }


class TestExpressionAdaptationAgent:
    """表达适配 Agent 测试"""

    def test_schema_valid(self):
        """ExpressionAdaptation schema 全字段往返"""
        from src.schemas import ExpressionAdaptation
        adaptation = ExpressionAdaptation(**_valid_adaptation_json())
        data = adaptation.model_dump()
        assert len(data["terms"]) == 5
        assert len(data["metaphors"]) == 3
        assert len(data["suggestions"]) == 3
        assert data["terms"][0]["chinese"] == "天宫"

    def test_build_user_prompt_contains_topic(self, agent):
        """user prompt 应包含议题"""
        a, _ = agent
        prompt = a._build_user_prompt({"topic": "嫦娥六号", "science_facts": {"key_facts": ["test"]}})
        assert "嫦娥六号" in prompt
        assert "中英对照" in prompt
        assert "术语" in prompt

    def test_build_user_prompt_with_kg(self, agent):
        """user prompt 应包含知识图谱实体"""
        a, _ = agent
        mock_kg = MagicMock()
        mock_kg.find_related_entities.return_value = [
            {"entity": "嫦娥六号", "relation": "mission"},
        ]
        with patch('src.agents.expression_adaptation_agent.get_knowledge_graph', return_value=mock_kg):
            prompt = a._build_user_prompt({
                "topic": "嫦娥六号",
                "science_facts": {"key_facts": ["test"]},
            })
        assert "知识图谱相关实体" in prompt

    def test_run_with_mock_llm(self, agent):
        """mock LLM 返回合法 JSON 时应成功解析"""
        a, mock_client = agent
        mock_client.chat_json.return_value = _valid_adaptation_json()
        result = a.run({"topic": "嫦娥六号"})
        assert len(result["terms"]) == 5
        assert result["terms"][0]["english"] == "Tiangong Space Station"
        assert result["suggestions"][0]["scenario"] == "欧美主流媒体"

    def test_get_agent_info(self, agent):
        """agent 信息应包含描述"""
        a, _ = agent
        info = a.get_agent_info()
        assert info["name"] == "expression_adaptation_agent"
        assert "表达适配" in info["description"]
