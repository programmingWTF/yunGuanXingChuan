"""
云观星传 - 表达适配 Agent（中英对照术语/隐喻/表达建议）
职责：基于三库证据，为科技议题的国际传播生成中英对照的术语、隐喻与场景化表达建议
定位为传播学特色差异化能力：跨文化传播适配，而非简单翻译
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ExpressionAdaptation
from src.knowledge.data_loader import get_data_loader
from src.knowledge.kg_builder import get_knowledge_graph


class ExpressionAdaptationAgent(BaseAgent):
    """表达适配 Agent：生成中英对照术语/隐喻/表达建议表"""

    agent_name = "expression_adaptation_agent"
    prompt_file = "expression_adaptation_agent.txt"
    output_schema = ExpressionAdaptation
    enable_search = True  # 需联网获取国际媒体实际用语与学术惯用表达
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建表达适配任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts") or self._load_science_material(topic)
        strategies = input_data.get("strategies", [])

        # 知识图谱相关实体（辅助术语提取）
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下三库证据，为科技议题「{topic}」的国际传播生成中英对照表达适配建议。

## 议题
{topic}

## 科学事实（术语来源）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:3000]}

## 知识图谱相关实体（辅助术语提取）
{json.dumps(kg_entities, ensure_ascii=False)}

## 已有传播策略（如有，参考其叙事框架）
{json.dumps(strategies, ensure_ascii=False, indent=2)[:1500]}

## 生成要求
按 system prompt 中的字段生成，注意：
1. terms 至少 5 对术语：从科学事实与知识图谱中提取关键科技术语，给出国际通用英文
2. metaphors 至少 3 对隐喻：提取中文科技传播中常见的修辞/隐喻，给出英文等效表达
3. suggestions 至少 3 条场景化建议：区分欧美媒体/学术期刊/社交平台等场景
4. 每条建议标注"推荐表达"与"不建议表达"，并说明原因（文化折扣/政治敏感/语义偏差）
5. evidence_sources 列出依据的三库证据来源"""
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
            "description": "表达适配 Agent：生成中英对照术语/隐喻/场景化表达建议（传播学特色）",
            "input": "topic + 三库科学事实 + 可选传播策略",
            "output": "ExpressionAdaptation (JSON)",
            "prompt_file": self.prompt_file,
        }
