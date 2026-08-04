"""
科研流程工作流 - 阶段定义

7 个阶段对应《智能体.docx》的 7 个核心智能体，按科研流程顺序编排：
①选题孵化器 → ②文献综述助手 → ③研究问题设计师 → ④方法顾问
→ ⑤数据分析助手 → ⑥论文写手 → ⑦评审模拟器
"""
from enum import IntEnum
from typing import Dict, Any


class WorkflowStage(IntEnum):
    """科研流程 7 阶段（数值即执行顺序）"""
    INSPIRATION = 1       # ① 选题孵化器
    LITERATURE = 2        # ② 文献综述助手
    DESIGN = 3            # ③ 研究问题设计师
    METHOD = 4            # ④ 方法顾问
    DATA_ANALYSIS = 5     # ⑤ 数据分析助手
    WRITING = 6           # ⑥ 论文写手
    REVIEW = 7            # ⑦ 评审模拟器


# 阶段元数据：前端 Pipeline 渲染 + 后端编排共用
STAGE_META: Dict[WorkflowStage, Dict[str, Any]] = {
    WorkflowStage.INSPIRATION: {
        "key": "inspiration",
        "name": "选题孵化",
        "icon": "💡",
        "agent_name": "research_inspiration_agent",
        "output_schema": "InspirationResult",
        "description": "输入研究兴趣，推荐 3-5 个选题方向（研究价值/覆盖度/创新潜力）",
        "library": ["文献库", "理论库"],
    },
    WorkflowStage.LITERATURE: {
        "key": "literature",
        "name": "文献综述",
        "icon": "📚",
        "agent_name": "literature_review_agent",
        "output_schema": "LiteratureReview",
        "description": "文献归类梳理，识别研究 Gap（未覆盖的视角/方法/对象）",
        "library": ["文献库", "理论库"],
    },
    WorkflowStage.DESIGN: {
        "key": "design",
        "name": "研究设计",
        "icon": "🎯",
        "agent_name": "research_question_agent",
        "output_schema": "ResearchDesignResult",
        "description": "凝练研究问题 RQ 与假设 H，输出问题质量检验报告",
        "library": ["顶刊论文库（范文库）"],
    },
    WorkflowStage.METHOD: {
        "key": "method",
        "name": "方法推荐",
        "icon": "🧪",
        "agent_name": "method_advisor_agent",
        "output_schema": "MethodRecommendationResult",
        "description": "按研究问题性质推荐方法，输出适配度评分与操作步骤",
        "library": ["方法库", "顶刊论文库"],
    },
    WorkflowStage.DATA_ANALYSIS: {
        "key": "data-analysis",
        "name": "数据分析",
        "icon": "📊",
        "agent_name": "data_analysis_agent",
        "output_schema": "AnalysisResult",
        "description": "上传分析素材，执行内容/文本/框架分析并给出初步解读",
        "library": ["方法库"],
    },
    WorkflowStage.WRITING: {
        "key": "writing",
        "name": "学术写作",
        "icon": "✍️",
        "agent_name": "paper_writer_agent",
        "output_schema": "PaperDraft",
        "description": "整合前期产出，按标准论文结构生成初稿（支持风格蒸馏）",
        "library": ["顶刊论文库"],
    },
    WorkflowStage.REVIEW: {
        "key": "review",
        "name": "同行评审",
        "icon": "👨‍⚖️",
        "agent_name": "reviewer_simulator_agent",
        "output_schema": "ReviewerFeedback",
        "description": "模拟 2-3 个审稿人从多维度评审，生成修改建议与修改说明",
        "library": ["顶刊论文库"],
    },
}


def get_stage_meta_list() -> list:
    """返回按顺序排列的阶段元数据列表（前端 Pipeline 渲染用）"""
    return [
        {
            "stage": int(stage),
            "key": meta["key"],
            "name": meta["name"],
            "icon": meta["icon"],
            "description": meta["description"],
            "library": meta["library"],
        }
        for stage, meta in sorted(STAGE_META.items())
    ]
