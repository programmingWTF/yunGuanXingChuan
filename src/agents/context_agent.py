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
    enable_search = False  # Step 0 已提供联网搜索上下文，无需重复搜索（提速）

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建语境分析任务的 user prompt"""
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

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "语境分析 Agent：分析国际媒体报道框架和情感倾向",
            "input": "ScienceFacts + 媒体语料",
            "output": "ContextAnalysis (JSON)",
            "prompt_file": self.prompt_file,
        }
