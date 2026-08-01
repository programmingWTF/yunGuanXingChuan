"""
云观星传 - 科普视频脚本 Agent 单元测试（mock LLM）
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
    """创建 ScienceScriptAgent，注入 mock LLM 客户端"""
    with patch('src.llm_client.OpenAI'), patch('src.agents.base_agent.get_llm_client') as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        from src.agents.science_script_agent import ScienceScriptAgent
        a = ScienceScriptAgent(llm_client=mock_client)
        a.llm_client = mock_client
        yield a, mock_client


def _valid_script_json():
    """构造合法的科普视频脚本 JSON"""
    return {
        "topic": "嫦娥六号",
        "platform": "B站",
        "title": "月背挖土！嫦娥六号凭什么让全世界关注？",
        "opening_hook": "你知道吗？人类第一次从月球背面带回了土壤",
        "shots": [
            {
                "scene_no": 1,
                "scene_description": "火箭发射升空，远景切近景",
                "duration_seconds": 5,
                "caption": "2024年6月25日 嫦娥六号返回地球",
                "narration": "这一天，全人类都在关注中国",
                "visual_suggestion": "发射现场航拍 + 数据叠加",
            },
            {
                "scene_no": 2,
                "scene_description": "月球表面采样动画",
                "duration_seconds": 8,
                "caption": "月球背面 vs 正面",
                "narration": "月球背面到底有什么不一样？",
                "visual_suggestion": "3D 动画对比月球的正面和背面",
            },
        ],
        "bgm_suggestion": "科技感电子音乐，节奏中等偏快",
        "hashtags": ["嫦娥六号", "月球背面", "中国航天", "科普"],
        "author_notes": "建议工作日晚 8 点发布，封面用月球背面对比图",
        "evidence_sources": ["新华社", "国家航天局"],
    }


class TestScienceScriptAgent:
    """科普视频脚本 Agent 测试"""

    def test_schema_valid(self):
        """ScienceScript schema 全字段往返"""
        from src.schemas import ScienceScript
        script = ScienceScript(**_valid_script_json())
        data = script.model_dump()
        assert data["platform"] == "B站"
        assert len(data["shots"]) == 2
        assert data["shots"][0]["scene_no"] == 1

    def test_build_user_prompt_contains_topic_and_platform(self, agent):
        """user prompt 应包含议题与平台"""
        a, _ = agent
        prompt = a._build_user_prompt({
            "topic": "嫦娥六号",
            "platform": "B站",
            "science_facts": {"key_facts": ["test"]},
        })
        assert "嫦娥六号" in prompt
        assert "B站" in prompt
        assert "key_facts" in prompt

    def test_build_user_prompt_with_kg_entities(self, agent):
        """user prompt 应包含知识图谱实体"""
        a, _ = agent
        mock_kg = MagicMock()
        mock_kg.find_related_entities.return_value = [
            {"entity": "嫦娥六号", "relation": "mission"},
            {"entity": "月球采样", "relation": "task"},
        ]
        with patch('src.agents.science_script_agent.get_knowledge_graph', return_value=mock_kg):
            prompt = a._build_user_prompt({
                "topic": "嫦娥六号",
                "platform": "短视频",
                "science_facts": {"key_facts": ["test"]},
            })
        assert "知识图谱相关实体" in prompt
        assert "月球采样" in prompt

    def test_normalize_platform(self, agent):
        """平台名规范化"""
        a, _ = agent
        assert a._normalize_platform("抖音") == "短视频"
        assert a._normalize_platform("bilibili") == "B站"
        assert a._normalize_platform("B站") == "B站"
        assert a._normalize_platform("微信公众号") == "公众号"
        assert a._normalize_platform("小红书") == "小红书"
        assert a._normalize_platform("微博热搜") == "微博"

    def test_run_with_mock_llm(self, agent):
        """mock LLM 返回合法 JSON 时应成功解析为 schema"""
        a, mock_client = agent
        mock_client.chat_json.return_value = _valid_script_json()
        result = a.run({"topic": "嫦娥六号", "platform": "B站"})
        assert result["title"]
        assert result["opening_hook"]
        assert len(result["shots"]) == 2

    def test_get_agent_info(self, agent):
        """agent 信息应包含描述"""
        a, _ = agent
        info = a.get_agent_info()
        assert info["name"] == "science_script_agent"
        assert "分镜" in info["description"]
