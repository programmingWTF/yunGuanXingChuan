"""
云观星传 - ① 选题孵化器（Research Inspiration Agent）
对应科研环节：发现议题 → 确定选题方向
职责：输入模糊兴趣点，模拟"多学者讨论"，输出 3-5 个选题方向及评分
（研究价值 / 既有研究覆盖度 / 创新潜力）
依赖知识库：文献库、理论库（由 WorkflowEngine 注入检索上下文）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import InspirationResult


class ResearchInspirationAgent(BaseAgent):
    """①选题孵化器：选题方向推荐 + 创新潜力评估"""

    agent_name = "research_inspiration_agent"
    prompt_file = "research_inspiration_agent.txt"
    output_schema = InspirationResult
    enable_search = False  # 检索上下文由 WorkflowEngine 注入，保持输出可控

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        topic = input_data.get("topic", "")
        search_context = input_data.get("search_context", [])
        kg_entities = input_data.get("kg_entities", [])
        knowledge_hits = input_data.get("knowledge_hits", [])

        prompt = f"""用户研究兴趣：{topic}

## 联网检索到的相关信号（热点/报道，来自统一搜索）
{json.dumps(search_context, ensure_ascii=False, indent=2)[:2500]}

## 知识图谱关联实体
{json.dumps(kg_entities, ensure_ascii=False)[:800]}

## 知识库检索命中（文献/资料）
{json.dumps(knowledge_hits, ensure_ascii=False, indent=2)[:1500]}

## 要求
模拟 3-5 位学者围绕该兴趣点展开讨论（传播学/国际关系/科技政策/新闻学视角），
输出 3-5 个选题方向。每个方向给出：title（20 字内）、summary（50-100 字）、
research_value（研究价值 0-100）、existing_coverage（既有研究覆盖度 0-100，
越高说明已有人研究越多）、innovation_potential（创新潜力 0-100）、
reasons（3 条推荐理由）、keywords（3-5 个关键词）。
selected_direction 填评分综合最优的方向标题；discussion_summary 用 100-150 字总结学者讨论结论。"""
        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "选题孵化器：基于研究兴趣推荐选题方向并评估研究价值/创新潜力",
            "input": "interest/topic + 搜索与知识图谱上下文",
            "output": "InspirationResult (JSON)",
            "prompt_file": self.prompt_file,
        }
