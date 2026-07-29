"""
云观星传 - 策略转译 Agent
职责：将分析结果转化为面向不同受众的传播策略
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import StrategySet
from src.knowledge.data_loader import get_data_loader


class StrategyAgent(BaseAgent):
    """策略转译 Agent：生成面向不同受众的传播策略"""

    agent_name = "strategy_agent"
    prompt_file = "strategy_agent.txt"
    output_schema = StrategySet
    enable_search = True  # 新闻时效性强，所有Agent均需联网搜索
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_news", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建策略转译任务的 user prompt"""
        task_type = input_data.get("task_type", "")
        if task_type == "debate_speech":
            return self._build_debate_prompt(input_data)
        if task_type == "vote":
            return self._build_vote_prompt(input_data)

        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts", {})
        context_analysis = input_data.get("context_analysis", {})
        hypotheses = input_data.get("hypotheses", [])
        verification_report = input_data.get("verification_report", [])

        # 加载受众画像
        audience_profiles = self.data_loader.load_audience_profiles()

        prompt = f"""基于以下分析结果，为不同受众群体生成国际传播策略。

## 议题
{topic}

## 科学事实
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:1500]}

## 语境分析
{json.dumps(context_analysis, ensure_ascii=False, indent=2)[:1500]}

## 已验证假设
{json.dumps(hypotheses, ensure_ascii=False, indent=2)[:1500]}

## 受众画像
{json.dumps(audience_profiles, ensure_ascii=False, indent=2)}

## 四种叙事人设
| 人设 | 风格 | 适用受众 | 语调 |
|------|------|----------|------|
| scientist | Nature/Science 期刊 | 国际科学共同体 | 严谨、数据驱动 |
| collaborator | 联合国报告 | 全球南方公众 | 包容、务实、共赢 |
| storyteller | 国家地理/纪录片 | 发达国家大众 | 故事化、有画面感 |
| communicator | 智库/政策分析 | 美国政策精英 | 理性、平衡、承认竞争 |

## 文化适配规则
- 面向美国：承认竞争但强调对话空间，忌"碾压""遥遥领先"
- 面向法国：突出中法航天合作（SVOM卫星），忌忽视合作历史
- 面向巴西/全球南方：强调普惠发展，忌"大国博弈"叙事
- 面向国内青年：有梗有料，忌新华社通稿体

## 叙事语感参考

面向美国政策精英（communicator）：
"China's Chang'e-6 mission represents a significant technical achievement in lunar exploration. While it inevitably intensifies the strategic competition in space, the scientific returns offer potential avenues for international scientific collaboration even amid geopolitical tensions."

面向全球南方（collaborator）：
"A mostra lunar trazida pela Chang'e-6 não pertence apenas à China - ela pertence à humanidade."

面向国内青年（storyteller）：
"你知道吗？月球背面永远看不到地球——这意味着那里是宇宙中最安静的地方。嫦娥六号去的就是这片宇宙净土，带回了1935.3克宇宙快递。"

## 输出要求
请严格按照以下 JSON 格式输出（为每个受众群体生成一条策略）：
{{
  "topic": "{topic}",
  "strategies": [
    {{
      "strategy_id": "S001",
      "target_audience": "美国政策精英",
      "narrative_persona": "communicator",
      "narrative_angle": "叙事角度",
      "key_messages": ["核心信息1", "核心信息2"],
      "channel_recommendation": ["渠道1", "渠道2"],
      "cultural_adaptations": ["文化适配点1"],
      "sample_text": "100-200字示例文本",
      "expected_effect": "预期效果",
      "risks": ["风险1"]
    }}
  ],
  "audience_coverage": ["美国政策精英", "全球南方公众", "国内青年"],
  "cultural_notes": ["文化适配说明"]
}}

注意：
- 每条策略的 sample_text 必须是 100-200 字的完整示例文本
- 必须覆盖至少 3 个不同受众群体
- narrative_persona 必须是 scientist/collaborator/storyteller/communicator 之一"""

        return prompt

    def _build_debate_prompt(self, input_data: Dict[str, Any]) -> str:
        """辩论发言 prompt — 从策略可行性和渠道适配角度评价动议"""
        topic = input_data.get("topic", "")
        current_motion = input_data.get("current_motion", {})
        previous_speeches = input_data.get("previous_speeches", [])
        round_num = input_data.get("round_num", 1)
        search_context = input_data.get("search_context", "")
        speeches_text = "\\n".join(
            f"【{s.get('speaker', '?')}】({s.get('stance', '?')}): {s.get('content', '')[:200]}"
            for s in previous_speeches
        )
        prompt = f"""你是 AI Scientist 工作流中的传播策略师（Communicator）。从策略可操作性、渠道匹配、受众覆盖角度发言。第 {round_num} 轮。
议题: {topic}
动议: {json.dumps(current_motion, ensure_ascii=False)[:600]}
已有发言:{speeches_text or "（你是第一位）"}
"""
        if search_context:
            prompt += f"""
{search_context}
"""
        prompt += """## 输出（严格 JSON）
{{"stance": "support/amend/question/oppose", "content": "发言内容（150-300字）", "references": ["引用"]}}"""
        return prompt

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
            "description": "策略转译 Agent：将分析结果转化为面向不同受众的传播策略",
            "input": "ScienceFacts + ContextAnalysis + Hypotheses + 受众画像",
            "output": "StrategySet (JSON)",
            "prompt_file": self.prompt_file,
        }
