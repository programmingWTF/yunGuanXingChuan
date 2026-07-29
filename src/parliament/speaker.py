"""
云观星传 - Speaker（议长）Agent
职责：主持辩论、分配发言权、动态调整投票权重、裁定争议、记录辩论过程
"""
import json
import logging
from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 预设权重模板（Speaker 决策的参考基准）
WEIGHT_TEMPLATES = {
    "fact": {
        "scientist": 0.40, "skeptic": 0.25, "humanist": 0.10,
        "strategist": 0.10, "evaluator": 0.15,
    },
    "culture": {
        "humanist": 0.40, "skeptic": 0.15, "scientist": 0.10,
        "strategist": 0.20, "evaluator": 0.15,
    },
    "strategy": {
        "strategist": 0.35, "evaluator": 0.25, "scientist": 0.10,
        "skeptic": 0.15, "humanist": 0.15,
    },
    "methodology": {
        "skeptic": 0.35, "scientist": 0.25, "evaluator": 0.20,
        "strategist": 0.10, "humanist": 0.10,
    },
}

SPEAKER_SYSTEM_PROMPT = """你是云观星传 AI Scientist 工作流的议长（Speaker）。

## 你的身份
你是一群AI科学家的主持人。你的参与者包括：
- scientist (Retriever): 知识检索专家（强项：三库数据检索、实验验证、事实准确性）
- skeptic (Verifier): 证据校验者（强项：挑逻辑漏洞、找反例、检验可证伪性）
- humanist (Reasoner): 人文学者（强项：文化敏感性、价值判断、受众心理、国际关系）
- strategist (Communicator): 传播策略师（强项：渠道推荐、受众适配、叙事设计）
- evaluator (Planner): 研究规划者（强项：五维评分、迭代反馈）

## 你的职责
1. **主持辩论**：宣布议题，分配发言权，确保每个视角都被听到
2. **动态权重**：根据当前辩论主题调整投票权重
   - 讨论科学事实时：scientist 0.40, skeptic 0.25, humanist 0.10, strategist 0.10, evaluator 0.15
   - 讨论文化适配时：humanist 0.40, skeptic 0.15, scientist 0.10, strategist 0.20, evaluator 0.15
   - 讨论策略可行性时：strategist 0.35, evaluator 0.25, scientist 0.10, skeptic 0.15, humanist 0.15
   - 讨论方法论设计时：skeptic 0.35, scientist 0.25, evaluator 0.20, strategist 0.10, humanist 0.10
   - 每次调整权重必须在 weight_rationale 字段中解释原因
3. **裁定争议**：当投票僵持（yes和no的加权差 < 0.15），做出最终裁定并记录理由
4. **记录过程**：完整记录所有发言、投票、少数派意见

## 辩论协议
- 每轮至少让2个Agent发言，但不超过4个（避免冗余）
- 同一Agent不能连续两轮都发言（避免一人独霸讨论）
- 每轮结束后进行投票表决当前动议
- 被否决的动议可以被修正后重新提案（修正次数最多1次）
- 辩论轮次上限：5轮
- 如果连续2轮评分无提升，宣布进入闭幕阶段

## 输出格式
你需要输出以下格式的JSON来控制辩论流程：

辩论阶段（phase: "debate"）：
{
  "phase": "debate",
  "round_num": 1,
  "current_topic": "当前辩论主题",
  "next_speakers": ["scientist", "humanist"],
  "speaker_weights": {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1, "strategist": 0.1, "evaluator": 0.15},
  "weight_rationale": "为什么这样设置权重的理由",
  "motion_to_vote": "M001"
}

闭幕阶段（phase: "closing"）：
{
  "phase": "closing",
  "summary": "辩论总结",
  "final_recommendation": "最终建议",
  "minority_concerns": ["少数派关注点"]
}"""


class SpeakerAgent(BaseAgent):
    """
    议长 Agent：主持认知议会辩论

    核心能力：
    - 决定每轮谁发言
    - 动态调整投票权重
    - 裁定僵持争议
    - 生成闭幕总结
    """

    agent_name = "speaker"
    prompt_file = ""  # 使用内置 prompt
    output_schema = None
    enable_search = True  # 议长也需联网感知最新舆情（新闻时效性）
    agent_tools = ["search_news", "search_web"]

    def _get_default_prompt(self) -> str:
        return SPEAKER_SYSTEM_PROMPT

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建议长决策 prompt"""
        task = input_data.get("task", "plan_round")

        if task == "plan_round":
            return self._build_plan_round_prompt(input_data)
        elif task == "rule_deadlock":
            return self._build_deadlock_prompt(input_data)
        elif task == "closing":
            return self._build_closing_prompt(input_data)
        else:
            return json.dumps(input_data, ensure_ascii=False, indent=2)

    def _build_plan_round_prompt(self, input_data: Dict[str, Any]) -> str:
        """规划下一轮辩论"""
        topic = input_data.get("topic", "")
        round_num = input_data.get("round_num", 1)
        motions = input_data.get("motions", [])
        previous_speakers = input_data.get("previous_speakers", [])
        debate_history = input_data.get("debate_history", [])
        motion_results = input_data.get("motion_results", [])

        history_text = ""
        for r in debate_history[-3:]:
            history_text += f"\n第{r.get('round_id', '?')}轮 [{r.get('topic', '')}]: "
            for s in r.get("speeches", [])[:2]:
                history_text += f"{s.get('speaker', '?')}({s.get('stance', '?')}) "

        results_text = ""
        for mr in motion_results[-5:]:
            results_text += f"\n{mr.get('motion_id', '?')}: {mr.get('result', '?')} (yes={mr.get('weighted_yes', 0):.2f})"

        return f"""请规划第 {round_num} 轮辩论。

## 总议题
{topic}

## 待讨论动议
{json.dumps(motions, ensure_ascii=False, indent=2)[:1000]}

## 上轮发言者（本轮应避免重复）
{previous_speakers}

## 辩论历史
{history_text if history_text else "（首轮辩论）"}

## 已表决结果
{results_text if results_text else "（尚无表决）"}

## 请输出本轮规划（严格 JSON）
{{
  "phase": "debate",
  "round_num": {round_num},
  "current_topic": "本轮核心讨论主题",
  "next_speakers": ["agent1", "agent2"],
  "speaker_weights": {{"scientist": 0.0, "skeptic": 0.0, "humanist": 0.0, "strategist": 0.0, "evaluator": 0.0}},
  "weight_rationale": "权重设置理由",
  "motion_to_vote": "M001"
}}

注意：
- next_speakers 中 2-4 个 Agent
- 避免与上轮发言者完全重复
- speaker_weights 五项之和必须为 1.0
- weight_rationale 不能为空"""

    def _build_deadlock_prompt(self, input_data: Dict[str, Any]) -> str:
        """裁定僵持"""
        motion = input_data.get("motion", {})
        votes = input_data.get("votes", {})
        weighted_yes = input_data.get("weighted_yes", 0)
        weighted_no = input_data.get("weighted_no", 0)
        debate_summary = input_data.get("debate_summary", "")

        return f"""投票出现僵持，请你作为议长做出最终裁定。

## 待裁定动议
{json.dumps(motion, ensure_ascii=False, indent=2)[:600]}

## 投票结果
加权赞成: {weighted_yes:.3f}, 加权反对: {weighted_no:.3f}
各Agent投票: {json.dumps(votes, ensure_ascii=False)}

## 辩论摘要
{debate_summary[:800]}

## 请输出裁定（严格 JSON）
{{
  "ruling": "passed/rejected/amended",
  "ruling_rationale": "裁定理由（100-200字）",
  "conditions": ["如果通过，附加条件"],
  "minority_acknowledgment": "对少数派意见的回应"
}}"""

    def _build_closing_prompt(self, input_data: Dict[str, Any]) -> str:
        """闭幕总结"""
        topic = input_data.get("topic", "")
        all_motions = input_data.get("motions", [])
        all_votes = input_data.get("votes", [])
        minority_opinions = input_data.get("minority_opinions", [])
        total_rounds = input_data.get("total_rounds", 0)

        return f"""请为本次 AI Scientist 工作流做闭幕总结。

## 议题
{topic}

## 辩论轮次
共 {total_rounds} 轮

## 所有动议及表决结果
{json.dumps(all_votes, ensure_ascii=False, indent=2)[:1500]}

## 少数派意见
{json.dumps(minority_opinions, ensure_ascii=False, indent=2)[:800]}

## 请输出闭幕总结（严格 JSON）
{{
  "phase": "closing",
  "summary": "辩论总结（200-400字）",
  "passed_motions": ["通过的动议ID"],
  "rejected_motions": ["否决的动议ID"],
  "final_recommendation": "最终策略建议",
  "minority_concerns": ["需要关注的少数派意见"],
  "key_insights": ["辩论中的关键洞察"]
}}"""

    def plan_round(self, topic: str, round_num: int, motions: List[Dict],
                   previous_speakers: List[str], debate_history: List[Dict],
                   motion_results: List[Dict]) -> Dict[str, Any]:
        """规划一轮辩论"""
        input_data = {
            "task": "plan_round",
            "topic": topic,
            "round_num": round_num,
            "motions": motions,
            "previous_speakers": previous_speakers,
            "debate_history": debate_history,
            "motion_results": motion_results,
        }
        try:
            result = self.run(input_data)
            # 确保权重合法
            weights = result.get("speaker_weights", {})
            if not weights or abs(sum(weights.values()) - 1.0) > 0.05:
                # 回退到预设模板
                result["speaker_weights"] = WEIGHT_TEMPLATES["fact"].copy()
                result["weight_rationale"] = "权重异常，回退到事实讨论模板"
            return result
        except Exception as e:
            logger.error(f"[Speaker] 规划失败: {e}")
            return self._fallback_plan(round_num, motions)

    def rule_deadlock(self, motion: Dict, votes: Dict, weighted_yes: float,
                      weighted_no: float, debate_summary: str) -> Dict[str, Any]:
        """裁定僵持"""
        input_data = {
            "task": "rule_deadlock",
            "motion": motion,
            "votes": votes,
            "weighted_yes": weighted_yes,
            "weighted_no": weighted_no,
            "debate_summary": debate_summary,
        }
        try:
            return self.run(input_data)
        except Exception as e:
            logger.error(f"[Speaker] 裁定失败: {e}")
            # 僵持时默认通过（附带条件）
            return {
                "ruling": "amended",
                "ruling_rationale": "议长裁定：僵持情况下默认附条件通过，需进一步验证。",
                "conditions": ["需补充更多证据支持"],
                "minority_acknowledgment": "少数派意见已记录，将在后续迭代中考虑。",
            }

    def close_parliament(self, topic: str, motions: List[Dict], votes: List[Dict],
                         minority_opinions: List[Dict], total_rounds: int) -> Dict[str, Any]:
        """闭幕总结"""
        input_data = {
            "task": "closing",
            "topic": topic,
            "motions": motions,
            "votes": votes,
            "minority_opinions": minority_opinions,
            "total_rounds": total_rounds,
        }
        try:
            return self.run(input_data)
        except Exception as e:
            logger.error(f"[Speaker] 闭幕总结失败: {e}")
            return {
                "phase": "closing",
                "summary": f"本次议会共进行 {total_rounds} 轮辩论。",
                "passed_motions": [v.get("motion_id") for v in votes if v.get("result") == "passed"],
                "rejected_motions": [v.get("motion_id") for v in votes if v.get("result") == "rejected"],
                "final_recommendation": "建议基于已通过动议制定传播策略。",
                "minority_concerns": [m.get("objection", "") for m in minority_opinions],
                "key_insights": [],
            }

    def _fallback_plan(self, round_num: int, motions: List[Dict]) -> Dict[str, Any]:
        """规划失败时的回退方案"""
        # 轮流使用不同权重模板
        templates = ["fact", "culture", "strategy", "methodology"]
        template_key = templates[(round_num - 1) % len(templates)]
        speakers_map = {
            "fact": ["scientist", "skeptic"],
            "culture": ["humanist", "strategist"],
            "strategy": ["strategist", "evaluator"],
            "methodology": ["skeptic", "scientist"],
        }
        motion_id = motions[0].get("motion_id", "M001") if motions else "M001"
        return {
            "phase": "debate",
            "round_num": round_num,
            "current_topic": f"第{round_num}轮讨论",
            "next_speakers": speakers_map[template_key],
            "speaker_weights": WEIGHT_TEMPLATES[template_key].copy(),
            "weight_rationale": f"回退方案：使用{template_key}模板",
            "motion_to_vote": motion_id,
        }

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "议长 Agent：主持辩论、分配发言权、动态权重、裁定争议",
            "input": "辩论状态",
            "output": "辩论控制指令 (JSON)",
            "prompt_file": "(内置)",
        }


if __name__ == "__main__":
    speaker = SpeakerAgent()
    print(json.dumps(speaker.get_agent_info(), ensure_ascii=False, indent=2))
