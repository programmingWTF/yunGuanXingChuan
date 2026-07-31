"""
云观星传 - 人文学者 Agent（AI Scientist 工作流成员）
职责：跨文化传播审查、受众心理分析、国际关系风险评估、文化适配建议
"""
import json
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent


class HumanistAgent(BaseAgent):
    """人文学者 Agent：跨文化传播审查与文化适配建议"""

    agent_name = "humanist"
    prompt_file = "humanist.txt"
    output_schema = None  # 辩论模式下输出自由格式 JSON
    enable_search = True  # 新闻时效性强，所有Agent均需联网搜索
    agent_tools = ["search_wikipedia", "search_news", "search_web"]

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建人文学者分析任务的 user prompt"""
        topic = input_data.get("topic", "")
        task_type = input_data.get("task_type", "cultural_review")

        if task_type == "opening_report":
            return self._build_opening_prompt(input_data)
        elif task_type == "debate_speech":
            return self._build_debate_prompt(input_data)
        elif task_type == "vote":
            return self._build_vote_prompt(input_data)
        else:
            return self._build_cultural_review_prompt(input_data)

    def _build_opening_prompt(self, input_data: Dict[str, Any]) -> str:
        """开幕报告 prompt"""
        topic = input_data.get("topic", "")
        science_facts = input_data.get("science_facts", {})
        context_analysis = input_data.get("context_analysis", {})

        return f"""作为 AI Scientist 工作流的人文学者（Reasoner），请对以下科技议题进行开场文化敏感性分析。

## 议题
{topic}

## 科学事实摘要
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:1200]}

## 国际媒体语境
{json.dumps(context_analysis, ensure_ascii=False, indent=2)[:1200]}

## 输出要求
请输出 JSON 格式：
{{
  "cultural_risk_level": "high/medium/low",
  "key_cultural_concerns": ["关注点1", "关注点2", "..."],
  "sensitive_narratives": ["敏感叙事1", "..."],
  "recommended_approaches": ["建议方向1", "..."],
  "motions": [
    {{
      "motion_id": "M_H001",
      "motion_type": "hypothesis",
      "content": "关于文化适配的假设/建议",
      "supporting_evidence": ["证据1"],
      "confidence": 0.7
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

        speeches_text = ""
        for s in previous_speeches:
            speeches_text += f"\n【{s.get('speaker', '?')}】({s.get('stance', '?')}): {s.get('content', '')[:300]}"

        prompt = f"""你是 AI Scientist 工作流中的人文学者（Reasoner），现在进入第 {round_num} 轮辩论。

## 当前议题
{topic}

## 当前动议
{json.dumps(current_motion, ensure_ascii=False, indent=2)[:800]}

## 本轮已有发言
{speeches_text if speeches_text else "（你是本轮第一位发言者）"}
"""
        if search_context:
            prompt += f"""
{search_context}
"""
        prompt += """## 你的任务
从跨文化传播、受众心理、国际关系角度对该动议发表意见。

## 输出要求
请输出 JSON 格式：
{{
  "stance": "support/oppose/amend/question/clarify",
  "content": "你的发言内容（200-400字）",
  "cultural_risks": ["识别到的文化风险"],
  "suggestions": ["具体修改建议"],
  "references": ["引用的证据或发言"]
}}"""
        return prompt

    def _build_vote_prompt(self, input_data: Dict[str, Any]) -> str:
        """投票 prompt - 人文视角"""
        motion = input_data.get("current_motion", {})
        debate_summary = input_data.get("debate_summary", "")

        return f"""你是人文学者（Reasoner），正在投票表决。

## 你的投票标准（严格执行）
- 投 yes：动议尊重文化多样性、无伦理风险、价值导向正面、不会引发国际争议
- 投 no：动议存在文化冒犯风险、伦理边界模糊、可能加剧偏见、或忽视弱势群体视角
- 投 abstain：动议纯粹是技术/数据问题，与人文价值无关

注意：你是人文守护者。即使动议在科学上正确，如果传播方式可能引发文化冲突或伦理争议，你也应该投 no。不要因为是"共识"就放弃审视。

## 待表决动议
{json.dumps(motion, ensure_ascii=False, indent=2)[:600]}

## 辩论摘要
{debate_summary[:800]}

## 输出格式（严格 JSON）
{{"vote": "yes/no/abstain", "reason": "一句话理由"}}"""

    def _build_cultural_review_prompt(self, input_data: Dict[str, Any]) -> str:
        """通用文化审查 prompt"""
        topic = input_data.get("topic", "")
        strategies = input_data.get("strategies", [])

        return f"""请对以下传播策略进行文化敏感性审查。

## 议题
{topic}

## 待审查策略
{json.dumps(strategies, ensure_ascii=False, indent=2)[:2000]}

## 输出要求
请输出 JSON 格式：
{{
  "overall_risk": "high/medium/low",
  "reviews": [
    {{
      "strategy_id": "S001",
      "cultural_risks": ["风险点"],
      "offensive_elements": ["可能冒犯的表达"],
      "suggestions": ["修改建议"],
      "adapted_sample": "修改后的示例文本（100字内）"
    }}
  ],
  "cross_cultural_notes": ["跨文化注意事项"]
}}"""

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "人文学者 Agent：跨文化传播审查、受众心理分析、文化适配建议",
            "input": "策略/假设 + 文化语境",
            "output": "文化审查报告 (JSON)",
            "prompt_file": self.prompt_file,
        }


if __name__ == "__main__":
    agent = HumanistAgent()
    print(json.dumps(agent.get_agent_info(), ensure_ascii=False, indent=2))
