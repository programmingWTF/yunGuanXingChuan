"""
云观星传 - 评测迭代 Agent
职责：对策略输出进行五维评分，驱动迭代改进
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import EvaluationResult
from src.knowledge.data_loader import get_data_loader
from config.settings import PASS_THRESHOLD


class EvaluatorAgent(BaseAgent):
    """评测迭代 Agent：五维评分 + 四步自迭代闭环"""

    agent_name = "evaluator_agent"
    prompt_file = "evaluator_agent.txt"
    output_schema = EvaluationResult
    enable_search = True  # 新闻时效性强，所有Agent均需联网搜索
    agent_tools = ["verify_claim_external", "query_knowledge_graph", "search_news", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建评测任务的 user prompt"""
        task_type = input_data.get("task_type", "")
        if task_type == "debate_speech":
            return self._build_debate_prompt(input_data)
        if task_type == "vote":
            return self._build_vote_prompt(input_data)

        topic = input_data.get("topic", "嫦娥六号")
        strategies = input_data.get("strategies", [])
        science_facts = input_data.get("science_facts", {})
        hypotheses = input_data.get("hypotheses", [])
        verification_report = input_data.get("verification_report", [])
        iteration_round = input_data.get("iteration_round", 1)
        previous_feedback = input_data.get("previous_feedback", [])

        # 加载受众画像用于受众模拟
        audience_profiles = self.data_loader.load_audience_profiles()

        prompt = f"""请对以下传播策略进行五维评分，并给出改进建议。

## 议题
{topic}

## 当前迭代轮次
第 {iteration_round} 轮

## 待评测策略
{json.dumps(strategies, ensure_ascii=False, indent=2)[:3000]}

## 科学事实（用于校验事实准确度）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:1000]}

## 校验报告
{json.dumps(verification_report, ensure_ascii=False, indent=2)[:1000]}

## 五维评分标准
| 维度 | 权重 | 90分标准 | 60分标准 |
|------|------|----------|----------|
| factual_accuracy | 30% | 所有事实与RAG/KG完全一致 | 大部分准确，1-2处错误 |
| strategic_actionability | 25% | 具体可执行，有渠道和时间 | 较笼统，缺执行路径 |
| audience_fit | 20% | 语调渠道完全匹配 | 部分匹配，有偏差 |
| cultural_sensitivity | 15% | 完全避开禁忌 | 1-2处敏感表述 |
| narrative_fluency | 10% | 自然有人味 | AI痕迹明显但通顺 |

## 受众画像（用于受众模拟评估）
{json.dumps(audience_profiles, ensure_ascii=False, indent=2)[:1500]}

"""
        if previous_feedback:
            prompt += f"""## 上一轮反馈（请检查是否已改进）
{json.dumps(previous_feedback, ensure_ascii=False, indent=2)}

"""

        prompt += f"""## 输出要求
请严格按照以下 JSON 格式输出：
{{
  "scores": {{
    "factual_accuracy": 85,
    "strategic_actionability": 80,
    "audience_fit": 78,
    "cultural_sensitivity": 82,
    "narrative_fluency": 75
  }},
  "weighted_total": 81.5,
  "passed": true,
  "feedback": [
    {{
      "dimension": "narrative_fluency",
      "current_score": 75,
      "issue": "问题描述",
      "suggestion": "改进建议",
      "target_agent": "strategy_agent"
    }}
  ],
  "experience_log": "本轮评测经验总结",
  "audience_simulation": [
    {{
      "audience": "美国政策精英",
      "persuasion_score": 7,
      "credibility": "可信度评价",
      "uncomfortable_points": ["不适点"],
      "willingness_to_share": true,
      "comments": "总体评价"
    }}
  ]
}}

## 迭代规则
- 通过阈值：加权总分 >= {PASS_THRESHOLD}
- 某维度 < 60 必须触发针对性改进
- 每轮只改最弱的 1-2 个维度，避免全面重写
- feedback 中的 target_agent 指定由哪个 Agent 改进

## 受众模拟
请扮演目标受众评估策略说服力：
1. 这段内容让你有什么感受？（1-10分）
2. 你觉得它可信吗？为什么？
3. 有没有让你不舒服或反感的表述？
4. 你愿意分享给朋友吗？为什么？"""

        return prompt

    def _build_debate_prompt(self, input_data: Dict[str, Any]) -> str:
        """辩论发言 prompt — 从五维评分角度独立评估动议质量"""
        topic = input_data.get("topic", "")
        current_motion = input_data.get("current_motion", {})
        previous_speeches = input_data.get("previous_speeches", [])
        round_num = input_data.get("round_num", 1)
        search_context = input_data.get("search_context", "")
        speeches_text = "\\n".join(
            f"【{s.get('speaker', '?')}】({s.get('stance', '?')}): {s.get('content', '')[:200]}"
            for s in previous_speeches
        )
        prompt = f"""你是 AI Scientist 工作流中的研究规划者（Planner）。从事实准确度、策略可操作性、受众适配度等五维标准发言。第 {round_num} 轮。
议题: {topic}
动议: {json.dumps(current_motion, ensure_ascii=False)[:600]}
已有发言:{speeches_text or "（你是第一位）"}
"""
        if search_context:
            prompt += f"""
{search_context}
"""
        prompt += """## 输出（严格 JSON）
{{"stance": "support/amend/question/oppose", "content": "评估意见（150-300字）", "references": ["引用"]}}"""
        return prompt

    def _build_vote_prompt(self, input_data: Dict[str, Any]) -> str:
        motion = input_data.get("current_motion", {})
        debate_summary = input_data.get("debate_summary", "")
        return f"""你是研究规划者（Planner），正在投票表决。

## 你的投票标准（严格执行）
- 投 yes：动议目标明确可衡量、与整体研究规划一致、资源分配合理、有清晰的迭代路径
- 投 no：动议目标模糊、与已有研究重复、优先级不合理、或缺乏评估指标
- 投 abstain：动议不涉及研究规划或资源分配问题

注意：你关注的是"这个动议在整体研究框架中是否值得投入"。即使动议本身正确，如果优先级不高或与已有工作重复，应投 no 或 abstain。

## 待表决动议
{json.dumps(motion, ensure_ascii=False)[:500]}
## 辩论摘要
{debate_summary[:500]}
## 严格 JSON: {{"vote": "yes/no/abstain", "reason": "一句话理由"}}"""

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "评测迭代 Agent：五维评分 + 四步自迭代闭环",
            "input": "Strategies + ScienceFacts + VerificationReport",
            "output": "EvaluationResult (JSON)",
            "prompt_file": self.prompt_file,
        }
