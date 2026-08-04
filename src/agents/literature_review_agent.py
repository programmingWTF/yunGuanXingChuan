"""
云观星传 - ② 文献综述助手（Literature Review Agent）
对应科研环节：文献综述 → 识别研究空白
职责：对选定选题方向检索文献，按主题/时间/方法论归类生成综述初稿，
重点识别研究 Gap（既有研究未覆盖的视角、方法或对象）
依赖知识库：文献库、理论库（由 WorkflowEngine 注入检索上下文）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import LiteratureReview


class LiteratureReviewAgent(BaseAgent):
    """②文献综述助手：文献归类 + Research Gap 识别"""

    agent_name = "literature_review_agent"
    prompt_file = "literature_review_agent.txt"
    output_schema = LiteratureReview
    enable_search = False

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        topic = input_data.get("topic", "")
        direction = input_data.get("direction") or input_data.get("selected_direction") or topic
        search_context = input_data.get("search_context", [])
        knowledge_hits = input_data.get("knowledge_hits", [])

        prompt = f"""研究主题：{topic}
选定选题方向：{direction}

## 联网检索到的文献/报道线索
{json.dumps(search_context, ensure_ascii=False, indent=2)[:3000]}

## 知识库检索命中（文献库/理论库）
{json.dumps(knowledge_hits, ensure_ascii=False, indent=2)[:2500]}

## 要求
1. sections：按主题/时间/方法论维度归类，输出 3-5 个综述章节（theme + content，每章 150-300 字）
2. research_gap：通过对比分析识别既有研究未覆盖的视角/方法/对象，
   description（50-100 字）、missing_perspectives（2-4 条）、suggestion（深入研究建议）
3. references：列出 3-8 条本次依据的文献（title/source/year，可基于检索线索）"""
        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "文献综述助手：文献归类梳理并识别研究 Gap",
            "input": "topic + direction + 检索上下文",
            "output": "LiteratureReview (JSON)",
            "prompt_file": self.prompt_file,
        }
