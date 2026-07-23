"""
云观星传 - 假设生成 Agent
职责：基于分析结果自动生成可验证的传播假设
核心原则："深沉的假设已经变得廉价了，只有被验证的假设才是有价值的。"
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import HypothesisSet
from src.knowledge.kg_builder import get_knowledge_graph


class HypothesisAgent(BaseAgent):
    """假设生成 Agent：生成可验证的传播假设"""

    agent_name = "hypothesis_agent"
    prompt_file = "hypothesis_agent.txt"
    output_schema = HypothesisSet

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建假设生成任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts", {})
        context_analysis = input_data.get("context_analysis", {})

        # 获取知识图谱中的相关实体
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下科学事实和语境分析结果，生成可验证的国际传播假设。

## 议题
{topic}

## 科学事实
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:2000]}

## 语境分析结果
{json.dumps(context_analysis, ensure_ascii=False, indent=2)[:2000]}

## 知识图谱相关实体
{json.dumps(kg_entities, ensure_ascii=False)}

## 假设生成要求
每条假设必须包含：
1. 假设陈述（明确、可验证）
2. 证据链（3条以上证据，每条标注来源和相关性）
3. 可验证路径（具体可执行的验证方法）
4. 可证伪标准（什么情况下假设不成立）
5. 置信度（基于证据充分度，0-1）
6. 涉及的知识图谱实体

## 假设示例
"法国媒体对嫦娥六号报道的竞争框架占比（约60%）显著高于巴西媒体（约20%），
推测受欧洲航天局与中国在月球探测领域的竞合关系影响。
验证路径：对比报道时间线与中欧航天合作/竞争事件时间线的相关性。
可证伪标准：若法国媒体报道中合作框架占比超过40%，则该假设不成立。"

## 输出要求
请严格按照以下 JSON 格式输出（生成 3-5 条假设）：
{{
  "topic": "{topic}",
  "hypotheses": [
    {{
      "hypothesis_id": "H001",
      "statement": "假设陈述",
      "framework": "competition/cooperation/progress/threat/development",
      "target_countries": ["美国", "法国"],
      "evidence_chain": [
        {{"source": "来源", "quote": "引用", "relevance": 0.8, "evidence_type": "media_report"}}
      ],
      "verification_path": "验证方法",
      "confidence": 0.75,
      "kg_entities_involved": ["嫦娥六号", "ESA"],
      "falsification_criteria": "可证伪标准"
    }}
  ],
  "reasoning_chain": "Chain-of-Thought 推理过程",
  "hypothesis_count": 4
}}

注意：
- 假设间要有逻辑关联
- 使用 Chain-of-Thought 展示推理过程
- 每条假设必须有明确的可证伪标准
- evidence_type 可选：media_report/scientific_data/policy_document"""

        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "假设生成 Agent：基于分析结果生成可验证的传播假设",
            "input": "ScienceFacts + ContextAnalysis",
            "output": "HypothesisSet (JSON)",
            "prompt_file": self.prompt_file,
        }
