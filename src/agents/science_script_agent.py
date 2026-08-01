"""
云观星传 - 科普视频脚本 Agent（多平台脚本生成）
职责：基于三库证据，为指定平台（短视频/公众号/微博/B站/小红书）生成
适配平台风格的科普视频分镜脚本（镜头/字幕/旁白/配图/BGM）
定位为助传（Communication Assistant），体现新闻传播专业特色
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import ScienceScript
from src.knowledge.data_loader import get_data_loader
from src.knowledge.kg_builder import get_knowledge_graph


class ScienceScriptAgent(BaseAgent):
    """科普视频脚本 Agent：为指定平台生成科普分镜脚本"""

    agent_name = "science_script_agent"
    prompt_file = "science_script_agent.txt"
    output_schema = ScienceScript
    enable_search = True  # 需联网获取最新事实与平台热点趋势
    agent_tools = ["search_rag_knowledge", "search_wikipedia", "search_web"]

    PLATFORMS = ["短视频", "公众号", "微博", "B站", "小红书"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_loader = get_data_loader()

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        """构建科普视频脚本任务的 user prompt"""
        topic = input_data.get("topic", "嫦娥六号")
        platform = input_data.get("platform") or "短视频"
        # 规范化平台名（兼容别名，如"抖音"->"短视频"）
        platform = self._normalize_platform(platform)
        science_facts = input_data.get("science_facts") or self._load_science_material(topic)

        # 知识图谱相关实体（作画面/配图素材）
        kg_entities = []
        try:
            kg = get_knowledge_graph()
            related = kg.find_related_entities(topic, depth=2)
            kg_entities = [r["entity"] for r in related[:10]]
        except Exception:
            pass

        prompt = f"""基于以下三库证据，为一个科普视频生成适配「{platform}」平台风格的完整分镜脚本。

## 科普主题
{topic}

## 目标平台
{platform}

## 科学事实（三库之一）
{json.dumps(science_facts, ensure_ascii=False, indent=2)[:3000]}

## 知识图谱相关实体（可用于画面/配图素材）
{json.dumps(kg_entities, ensure_ascii=False)}

## 生成要求
按 system prompt 中的字段生成，注意：
1. 严格贴合「{platform}」平台的风格：时长、口吻、结构、标题都要对平台
2. shots 至少 2 个镜头（第一镜头、第二镜头…），每个镜头齐备 scene_description/duration_seconds/caption/narration/visual_suggestion
3. opening_hook 给出具体、抓人的开场（悬念/反常识/提问），不空泛
4. bgm_suggestion 贴合平台音乐气质；hashtags 3-5 个热搜向标签
5. evidence_sources 列出依据的三库证据来源，科学表述必须有据可依"""
        return prompt

    def _normalize_platform(self, platform: str) -> str:
        """规范化平台名到标准枚举之一"""
        p = platform.strip()
        aliases = {
            "抖音": "短视频", "快手": "短视频", "抖音/快手": "短视频", "短视频平台": "短视频",
            "微信公众号": "公众号", "公众号文章": "公众号", "微信": "公众号",
            "微博热搜": "微博", "weibo": "微博",
            "bilibili": "B站", "b站": "B站", "哔哩哔哩": "B站",
            "小红书笔记": "小红书", "red book": "小红书",
        }
        if p in self.PLATFORMS:
            return p
        return aliases.get(p.lower(), p)

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
            "description": "科普视频脚本 Agent：为短视频/公众号/微博/B站/小红书生成平台适配的分镜脚本",
            "input": "topic + platform + 三库科学事实",
            "output": "ScienceScript (JSON)",
            "prompt_file": self.prompt_file,
        }
