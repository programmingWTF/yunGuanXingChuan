"""
云观星传 - 论文大纲 Agent
职责：基于三库证据（科学事实库 / 知识图谱 / 媒体传播库），生成论文大纲（Outline，助研而非代写）
增强：集成知识图谱实体关联 + 已有假设作为研究切入点参考
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import PaperOutline
from src.knowledge.data_loader import get_data_loader
from src.knowledge.kg_builder import get_knowledge_graph


class PaperOutlineAgent(BaseAgent):
    """论文大纲 Agent：生成结构完整的论文大纲"""

    agent_name = "paper_outline_agent"
    prompt_file = "paper_outline_agent.txt"
    output_schema = PaperOutline
    enable_search = True  # 科研需联网补充最新研究动态
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建论文大纲任务的 user prompt（含知识图谱实体 + 已有假设）"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts") or self._load_science_material(topic)
        hypotheses = input_data.get("hypotheses", [])
        verification_report = input_data.get("verification_report", [])

        # 知识图谱相关实体（增强上下文）
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下三库证据，为研究者生成一份论文大纲（助研定位，只给框架与要点，不写正文）。

## 研究主题
{topic}

## 科学事实（三库之一）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:3000]}

## 知识图谱相关实体
{json.dumps(kg_entities, ensure_ascii=False)}

## 已有传播假设（如有，可作研究切入点参考）
{json.dumps(hypotheses, ensure_ascii=False, indent=2)[:1500]}

## 校验报告（如有）
{json.dumps(verification_report, ensure_ascii=False, indent=2)[:1500]}

## 生成要求
按 system prompt 中的字段生成，注意：
1. 固定 8 段结构：Title/Abstract/Introduction/Literature Review/Method/Result/Discussion/Future Work
2. 每个 framework 字段给"框架 + 编号要点提示"，不含正文
3. paper_title 一句话体现研究问题与创新点
4. research_questions 给出 3-5 条可检验的研究问题
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
            "description": "论文大纲 Agent：基于三库证据+知识图谱生成论文写作框架（助研）",
            "input": "topic + 三库科学事实 + 可选假设/校验结果",
            "output": "PaperOutline (JSON)",
            "prompt_file": self.prompt_file,
        }
