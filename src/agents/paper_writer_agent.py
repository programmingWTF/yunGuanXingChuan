"""
云观星传 - ⑥ 论文写手（Paper Writer Agent）
对应科研环节：写作 → 产出初稿
职责：整合前期所有产出（选题、文献综述、RQ、方法、分析结果），
按学术论文标准结构生成初稿，支持"风格蒸馏"（上传目标学者范文学习其学术话语）
依赖知识库：顶刊论文库（格式/风格参考）
"""
import json
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.base_agent import BaseAgent
from src.schemas import PaperDraft


class PaperWriterAgent(BaseAgent):
    """⑥论文写手：标准结构初稿生成 + 风格蒸馏"""

    agent_name = "paper_writer_agent"
    prompt_file = "paper_writer_agent.txt"
    output_schema = PaperDraft
    enable_search = False

    def _build_user_prompt(self, input_data: Dict[str, Any]) -> str:
        topic = input_data.get("topic", "")
        style_sample = input_data.get("style_sample") or ""
        if isinstance(style_sample, list):
            style_sample = "\n".join(str(s)[:500] for s in style_sample)[:2000]

        # 整合前期产出
        parts = []
        for key, label in [
            ("inspiration_result", "① 选题孵化"),
            ("literature_review", "② 文献综述与Gap"),
            ("research_design", "③ 研究设计（RQ/H）"),
            ("method_result", "④ 方法推荐"),
            ("analysis_result", "⑤ 数据分析"),
        ]:
            val = input_data.get(key)
            if val:
                parts.append(f"## {label}\n{json.dumps(val, ensure_ascii=False, indent=2)[:2000]}")

        prompt = f"""研究主题：{topic}

## 前期研究成果
{chr(10).join(parts) if parts else '（无前期产出，请基于主题给出论文框架与内容）'}

## 风格蒸馏样本（可选，用于学习学术话语体系、减少"AI味"）
{style_sample if style_sample else '（未提供风格样本，按规范学术写作风格输出）'}

## 要求
1. title：给出论文标题（不超过 30 字）
2. sections：按标准结构输出 7 个章节：摘要 / 引言 / 文献综述 / 方法 / 发现 / 讨论 / 结论，
   每章 content 80-300 字；摘要须概括背景/方法/结果/意义
3. 引用前期研究成果中的真实信息（选题、Gap、RQ、方法、分析发现），不得虚构数据
4. style_notes：若提供了风格样本，说明学习了哪些表达特征（2-4 条）"""
        return prompt

    def get_agent_info(self) -> Dict:
        return {
            "name": self.agent_name,
            "description": "论文写手：整合前期产出生成论文初稿（支持风格蒸馏）",
            "input": "topic + 前期各阶段产出 + style_sample(可选)",
            "output": "PaperDraft (JSON)",
            "prompt_file": self.prompt_file,
        }
