"""
云观星传 - ③ 研究问题设计师（Research Question Agent）
对应科研环节：确定研究问题 / 研究假设
职责：基于文献综述与研究 Gap 凝练 1-3 个规范研究问题（RQ），
量化研究附加研究假设（H1/H2），并输出"问题质量检验"报告
（对比顶刊论文研究问题范式：清晰度 / 可操作性 / 创新性）
依赖知识库：顶刊论文库（范文库）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ResearchDesignResult


class ResearchQuestionAgent(BaseAgent):
    """③研究问题设计师：RQ/Hypothesis 生成 + 问题质量检验"""

    agent_name = "research_question_agent"
    prompt_file = "research_question_agent.txt"
    output_schema = ResearchDesignResult
    enable_search = False

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        topic = input_data.get("topic", "")
        literature = input_data.get("literature_review") or {}

        prompt = f"""研究主题：{topic}

## 文献综述与 Gap
{json.dumps(literature, ensure_ascii=False, indent=2)[:3000]}

## 要求
1. research_questions：1-3 个规范表述的研究问题（id: RQ1...，text 需清晰、可操作、有研究价值）
2. hypotheses：若适合量化研究，附加 1-3 个研究假设（id: H1...，statement，hypothesis_type: quantitative/qualitative）
3. quality_report：对照顶刊论文研究问题范式，给出 clarity/innovativeness/operability 三项 0-100 评分
   （操作标准：清晰度=问题无歧义；可操作性=有具体数据/方法可回答；创新性=有增量贡献）
   comments 给出 2-4 条质量评语与改进建议"""
        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "研究问题设计师：RQ/Hypothesis 生成 + 问题质量检验",
            "input": "topic + literature_review（含 Gap）",
            "output": "ResearchDesignResult (JSON)",
            "prompt_file": self.prompt_file,
        }
