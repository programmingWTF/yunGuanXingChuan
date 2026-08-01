"""
云观星传 - 新闻传播建议稿 Agent
职责：基于科学事实与语境分析，生成可编辑的新闻传播建议稿（助传而非代写）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import PressReleaseDraft
from src.knowledge.data_loader import get_data_loader
from src.knowledge.kg_builder import get_knowledge_graph


class PressReleaseAgent(BaseAgent):
    """新闻传播建议稿 Agent：生成可编辑的新闻建议稿"""

    agent_name = "press_release_agent"
    prompt_file = "press_release_agent.txt"
    output_schema = PressReleaseDraft
    enable_search = True  # 媒体渠道/时效信息需联网
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_news", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建新闻传播建议稿任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts") or self._load_science_material(topic)
        strategies = input_data.get("strategies", [])
        final_report = input_data.get("final_report", {})

        # 知识图谱相关实体
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下素材，为传播者生成一份可编辑的新闻传播建议稿（助传定位，不代写新闻正文）。

## 议题
{topic}

## 科学事实（三库之一）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:2000]}

## 知识图谱相关实体
{json.dumps(kg_entities, ensure_ascii=False)}

## 已有传播策略（如有）
{json.dumps(strategies, ensure_ascii=False, indent=2)[:1500]}

## 已有议会总结（如有）
{json.dumps(final_report, ensure_ascii=False, indent=2)[:1500]}

## 生成要求
按 system prompt 中的字段生成，注意：
1. recommended_titles 中英兼顾，可直接借鉴
2. lead_suggestions 每条突出新闻点（如"首次""里程碑""国际合作"）
3. body_framework 给段落定位与要点，不代写完整正文
4. interview_subjects 每条给出具体人物/机构 + 身份 + 建议原因
5. evidence_sources 列出依据的三库证据"""
        return prompt

    def _load_science_material(self, topic: str) -> Dict[str, Any]:
        """从三库加载科学事实素材（无上游结果时的兜底）"""
        try:
            facts = self.data_loader.load_science_facts(topic)
            if facts:
                return facts[0] if isinstance(facts, list) else facts
        except Exception:
            pass
        return {"topic": topic, "key_facts": [], "entities": []}

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "新闻传播建议稿 Agent：生成可编辑的新闻建议稿（助传）",
            "input": "topic + 科学事实 + 知识图谱实体 + 可选策略/议会总结",
            "output": "PressReleaseDraft (JSON)",
            "prompt_file": self.prompt_file,
        }
