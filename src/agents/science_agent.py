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
    enable_search = True  # 新闻时效性强，所有Agent均需联网搜索
    agent_tools = ["query_knowledge_graph", "search_wikipedia", "search_news", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建科学理解任务的 user prompt"""
        task_type = input_data.get("task_type", "")
        if task_type == "debate_speech":
            return self._build_debate_prompt(input_data)
        if task_type == "vote":
            return self._build_vote_prompt(input_data)
        if task_type == "opening_report":
            return self._build_opening_prompt(input_data)

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

    def _build_opening_prompt(self, input_data: Dict[str, Any]) -> str:
        """开幕报告 prompt"""
        topic = input_data.get("topic", "")
        science_facts = input_data.get("science_facts", {})
        facts_json = json.dumps(science_facts, ensure_ascii=False)[:1500]
        return f"""你是 AI Scientist 工作流中的知识检索专家（Retriever）。请做开幕报告，提取关键科学事实并提出动议。

## 议题
{topic}

## 已有科学数据
{facts_json}

## 输出要求（严格 JSON）
{{
  "content": "你的开场报告（200-300字）",
  "motions": [
    {{
      "motion_id": "M_S001",
      "motion_type": "fact_claim",
      "content": "关于科学事实的断言",
      "supporting_evidence": ["证据"],
      "confidence": 0.8
    }}
  ]
}}"""

    def _build_debate_prompt(self, input_data: Dict[str, Any]) -> str:
        """辩论发言 prompt"""
        topic = input_data.get("topic", "")
        current_motion = input_data.get("current_motion", {})
        previous_speeches = input_data.get("previous_speeches", [])
        round_num = input_data.get("round_num", 1)
        search_context = input_data.get("search_context", "")
        speeches_text = "\n".join(
            f"【{s.get('speaker', '?')}】({s.get('stance', '?')}): {s.get('content', '')[:200]}"
            for s in previous_speeches
        )
        prompt = f"""你是 AI Scientist 工作流中的知识检索专家（Retriever）。现在进入第 {round_num} 轮辩论。

## 当前议题
{topic}

## 当前动议
{json.dumps(current_motion, ensure_ascii=False)[:800]}

## 本轮已有发言
{speeches_text if speeches_text else "（你是本轮第一位发言者）"}
"""
        if search_context:
            prompt += f"""
{search_context}
"""
        prompt += """## 你的任务
从科学事实和证据角度发言，核实动议中的科学主张是否准确、是否有来源支撑。
## 输出（严格 JSON）
{{"stance": "support/oppose/amend/question", "content": "发言内容（150-300字）", "references": ["引用"]}}"""
        return prompt

    def _build_vote_prompt(self, input_data: Dict[str, Any]) -> str:
        """投票 prompt - 科学视角"""
        motion = input_data.get("current_motion", {})
        debate_summary = input_data.get("debate_summary", "")
        return f"""你是科学检索专家（Retriever），正在投票表决。

## 你的投票标准（严格执行）
- 投 yes：动议中的科学事实准确、有可靠数据源支撑、不存在夸大或误导
- 投 no：存在未经验证的科学断言、数据源不可靠、因果关系不成立、或样本/证据不足
- 投 abstain：动议不涉及科学事实判断，超出你的专业范围

注意：你是科学家，对事实准确性零容忍。如果动议中有任何模糊表述（"可能"、"据说"、"大约"）作为确定性结论出现，应投 no。

## 待表决动议
{json.dumps(motion, ensure_ascii=False)[:600]}
## 辩论摘要
{debate_summary[:600]}
## 严格 JSON: {{"vote": "yes/no/abstain", "reason": "一句话理由"}}"""

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "科学理解 Agent：从航天科学数据中提取结构化事实、实体和关系",
            "input": "科技议题名称 + 相关科学文献/数据",
            "output": "ScienceFacts (JSON)",
            "prompt_file": self.prompt_file,
        }
