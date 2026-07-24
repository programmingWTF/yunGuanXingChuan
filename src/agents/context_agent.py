"""
云观星传 - 语境分析 Agent
职责：分析国际媒体对中国航天科技的报道框架和情感倾向
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ContextAnalysis
from src.knowledge.data_loader import get_data_loader


class ContextAgent(BaseAgent):
    """语境分析 Agent：分析国际媒体报道框架"""

    agent_name = "context_agent"
    prompt_file = "context_agent.txt"
    output_schema = ContextAnalysis
    enable_search = True  # 新闻时效性强，所有Agent均需联网搜索
    agent_tools = ["search_news", "search_web", "search_rag_knowledge"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建语境分析任务的 user prompt"""
        task_type = input_data.get("task_type", "")
        if task_type == "debate_speech":
            return self._build_debate_prompt(input_data)
        if task_type == "vote":
            return self._build_vote_prompt(input_data)

        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts", {})
        search_context = input_data.get("search_context", "")

        # 加载媒体数据
        media_reports = self.data_loader.load_media_reports()

        prompt = f"""请分析国际媒体对“{topic}”相关科技议题的报道框架和情感倾向。

## 科学事实背景
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:2000]}

## 媒体报道数据
{json.dumps(media_reports, ensure_ascii=False, indent=2)[:8000]}

"""
        if search_context:
            prompt += f"""{search_context}

"""
        prompt += """## 框架判别标准
1. 竞争框架(competition)：使用"race/competition/rival/challenge/太空竞赛/超越/对抗"
2. 合作框架(cooperation)：使用"collaboration/partnership/joint/shared/国际合作/共享"
3. 进步框架(progress)：使用"milestone/breakthrough/first-ever/humanity/人类探索/科学突破"
4. 威胁框架(threat)：使用"military/threat/concern/security/军事化/安全担忧"
5. 发展框架(development)：使用"development/opportunity/inclusive/benefit/普惠/共赢"

## 输出要求
请严格按照以下 JSON 格式输出：
{{
  "topic": "{topic}",
  "country_analysis": [
    {{
      "country": "国家名",
      "total_reports": 4,
      "framework_distribution": {{"competition": 0.5, "progress": 0.3, "cooperation": 0.2}},
      "dominant_framework": "competition",
      "sentiment_distribution": {{"positive": 0.5, "negative": 0.25, "neutral": 0.25}},
      "key_narratives": ["叙事点1", "叙事点2"],
      "representative_quotes": ["引用1", "引用2"]
    }}
  ],
  "framework_distribution": {{"competition": 0.4, "progress": 0.3, "cooperation": 0.2, "development": 0.1}},
  "sentiment_summary": {{"overall": "mixed", "by_country": {{}}}},
  "key_narratives": ["跨国家的关键叙事点"],
  "cross_cultural_differences": ["文化差异点1", "文化差异点2"]
}}

注意：
- 必须覆盖所有提供的媒体报道数据中的国家（至少分析 8 个国家/地区）
- 按国家分组统计，每个国家给出完整的框架分布和情感分布
- 给出框架分布百分比
- 识别关键叙事点和跨文化差异
- 所有比例用 0-1 的小数表示
- 如果某国数据较少，仍需单独列出分析结果"""

        return prompt

    def _build_debate_prompt(self, input_data: Dict[str, Any]) -> str:
        """辩论发言 prompt — 从国际媒体框架角度评价动议"""
        topic = input_data.get("topic", "")
        current_motion = input_data.get("current_motion", {})
        previous_speeches = input_data.get("previous_speeches", [])
        round_num = input_data.get("round_num", 1)
        speeches_text = "\\n".join(
            f"【{s.get('speaker', '?')}】({s.get('stance', '?')}): {s.get('content', '')[:200]}"
            for s in previous_speeches
        )
        return f"""你是认知议会中的语境分析专家。从国际媒体框架和受众角度发言。第 {round_num} 轮。
议题: {topic}
动议: {json.dumps(current_motion, ensure_ascii=False)[:600]}
已有发言:{speeches_text or "（你是第一位）"}
## 输出（严格 JSON）
{{"stance": "support/oppose/amend/question", "content": "发言内容（150-300字）", "references": ["引用"]}}"""

    def _build_vote_prompt(self, input_data: Dict[str, Any]) -> str:
        motion = input_data.get("current_motion", {})
        debate_summary = input_data.get("debate_summary", "")
        return f"""你现在是在投票表决，不是在辩论。请只输出 yes/no/abstain 加一行理由。
动议: {json.dumps(motion, ensure_ascii=False)[:500]}
摘要: {debate_summary[:500]}
## 严格 JSON: {{"vote": "yes/no/abstain", "reason": "理由"}}"""

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "语境分析 Agent：分析国际媒体报道框架和情感倾向",
            "input": "ScienceFacts + 媒体语料",
            "output": "ContextAnalysis (JSON)",
            "prompt_file": self.prompt_file,
        }
