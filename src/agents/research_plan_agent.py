"""
云观星传 - 科研助研 Agent（科学假设与研究计划生成）
职责：基于三库证据，生成结构化的科学假设与研究计划（助研而非代写）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ResearchPlan
from src.knowledge.data_loader import get_data_loader
from src.knowledge.kg_builder import get_knowledge_graph


class ResearchPlanAgent(BaseAgent):
    """科研助研 Agent：生成科学假设与研究计划"""

    agent_name = "research_plan_agent"
    prompt_file = "research_plan_agent.txt"
    output_schema = ResearchPlan
    enable_search = True  # 科研需联网补充最新研究动态
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建科研助研任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts") or self._load_science_material(topic)
        hypotheses = input_data.get("hypotheses", [])
        verification_report = input_data.get("verification_report", [])

        # 知识图谱相关实体
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下三库证据，为研究者生成一份科学假设与研究计划（助研框架，不是代写）。

## 研究主题
{topic}

## 科学事实（三库之一）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:3000]}

## 知识图谱相关实体
{json.dumps(kg_entities, ensure_ascii=False)}

## 已有传播假设（如有，可作科研切入参考）
{json.dumps(hypotheses, ensure_ascii=False, indent=2)[:1500]}

## 校验报告（如有）
{json.dumps(verification_report, ensure_ascii=False, indent=2)[:1500]}

## 生成要求
按 system prompt 中的字段生成，注意：
1. 研究背景、已有研究、研究空白必须基于上方证据，可补充公开已知研究但需在 evidence_sources 标注
2. scientific_hypotheses 是科研层面的可检验假设（2-4条），与"传播假设"不同
3. 方法、数据来源、实验步骤要具体可执行
4. evidence_sources 列出本次依据的三库证据来源
5. note 字段提醒研究者：这是建议框架，需结合自身判断调整"""
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
            "description": "科研助研 Agent：生成科学假设与研究计划（AI Scientist 核心）",
            "input": "topic + 三库科学事实 + 可选已有假设/校验结果",
            "output": "ResearchPlan (JSON)",
            "prompt_file": self.prompt_file,
        }
