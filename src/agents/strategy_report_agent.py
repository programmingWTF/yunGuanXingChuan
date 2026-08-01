"""
云观星传 - 国际传播策略 Agent（策略报告生成）
职责：基于科学事实、语境分析与受众画像，生成整份国际传播策略报告
复用 StrategyAgent 的受众画像加载与叙事人设素材拼接思路
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import CommunicationStrategyReport
from src.knowledge.data_loader import get_data_loader


class StrategyReportAgent(BaseAgent):
    """国际传播策略 Agent：生成完整策略报告"""

    agent_name = "strategy_report_agent"
    prompt_file = "strategy_report_agent.txt"
    output_schema = CommunicationStrategyReport
    enable_search = True  # 媒体渠道时效性强，需联网
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_news", "search_web"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建国际传播策略报告任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        science_facts = input_data.get("science_facts", {})
        context_analysis = input_data.get("context_analysis", {})
        strategies = input_data.get("strategies", [])
        final_report = input_data.get("final_report", {})

        # 受众画像（复用 StrategyAgent 的素材来源）
        audience_profiles = self.data_loader.load_audience_profiles()

        prompt = f"""基于以下科学事实、语境分析与受众画像，生成一份完整国际传播策略报告。

## 议题
{topic}

## 科学事实
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:1500]}

## 语境分析（含中外媒体框架差异）
{json.dumps(context_analysis, ensure_ascii=False, indent=2)[:2000]}

## 已有策略（如有）
{json.dumps(strategies, ensure_ascii=False, indent=2)[:1500]}

## 已有议会总结（如有）
{json.dumps(final_report, ensure_ascii=False, indent=2)[:1500]}

## 受众画像
{json.dumps(audience_profiles, ensure_ascii=False)[:2500]}

## 生成要求
按 system prompt 中的字段生成，注意：
1. china_media_differences 必须具体对比：中国媒体倾向哪种框架/语调 vs 目标国媒体倾向哪种
2. recommended_media 每条给出具体媒体名称 + 选择理由
3. recommended_titles 中英兼顾，可直接借鉴
4. risk_warnings 关注文化敏感与地缘政治风险
5. evidence_sources 列出依据的三库证据与媒体分析来源"""
        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "国际传播策略 Agent：生成完整策略报告（含中外媒体差异）",
            "input": "topic + 科学事实 + 语境分析 + 受众画像",
            "output": "CommunicationStrategyReport (JSON)",
            "prompt_file": self.prompt_file,
        }
