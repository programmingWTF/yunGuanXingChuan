"""
云观星传 - 科学理解 Agent
职责：摄入航天科学数据，提取结构化事实，构建实体和关系
"""
import json
from typing import Dict, Any, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ScienceFacts
from src.knowledge.data_loader import get_data_loader
from src.knowledge.vector_store import get_vector_store


class ScienceAgent(BaseAgent):
    """科学理解 Agent：提取结构化科学事实"""

    agent_name = "science_agent"
    prompt_file = "science_agent.txt"
    output_schema = ScienceFacts
    enable_search = False  # Step 0 已提供联网搜索上下文，无需重复搜索（提速）

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建科学理解任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        search_context = input_data.get("search_context", "")

        # 加载相关科学数据
        science_data = self.data_loader.load_science_facts(topic)

        # 如果有向量库，检索相关知识
        rag_context = ""
        try:
            vector_store = get_vector_store()
            if vector_store.index is not None and vector_store.index.ntotal > 0:
                results = vector_store.search(topic, top_k=5)
                if results:
                    rag_context = "\n".join([r["text"] for r in results])
        except Exception:
            pass

        prompt = f"""请分析以下科技议题，提取结构化科学事实。

## 议题名称
{topic}

## 已有科学数据
{json.dumps(science_data, ensure_ascii=False, indent=2)}

"""
        if search_context:
            prompt += f"""{search_context}

"""
        if rag_context:
            prompt += f"""## RAG 检索到的相关知识
{rag_context}

"""

        prompt += """## 输出要求
请严格按照以下 JSON 格式输出：
{
  "topic": "议题名称",
  "key_facts": ["事实1", "事实2", ...],
  "entities": [
    {"name": "实体名", "entity_type": "mission/body/technology/organization/person/event", "attributes": {}, "description": "描述"}
  ],
  "relations": [
    {"subject": "主体", "predicate": "关系", "object": "客体", "confidence": 0.9, "source": "来源"}
  ],
  "timeline": [{"date": "日期", "event": "事件"}],
  "data_sources": ["来源1", "来源2"]
}

注意：
- 只输出可验证的客观事实
- 每个事实必须标注来源
- 实体关系必须明确、可机器处理
- confidence 取值 0-1
- 【重要】JSON 字符串值内部禁止使用英文双引号(")，如需引用请改用中文引号「」或『』"""

        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "科学理解 Agent：从航天科学数据中提取结构化事实、实体和关系",
            "input": "科技议题名称 + 相关科学文献/数据",
            "output": "ScienceFacts (JSON)",
            "prompt_file": self.prompt_file,
        }
