"""
假设路由 - 获取和筛选假设
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query
from typing import Optional, List

from src.knowledge.data_loader import get_data_loader

router = APIRouter()


@router.get("/")
async def get_hypotheses(
    framework: Optional[str] = Query(None, description="按框架筛选"),
    country: Optional[str] = Query(None, description="按国家筛选"),
    min_confidence: float = Query(0.0, description="最小置信度"),
):
    """获取假设列表（从最近的分析结果）"""
    # 这里返回示例数据，实际应从 pipeline 结果获取
    return {
        "hypotheses": [],
        "filters": {
            "framework": framework,
            "country": country,
            "min_confidence": min_confidence,
        },
        "message": "请先运行分析任务"
    }


@router.get("/frameworks")
async def get_frameworks():
    """获取所有框架类型"""
    return {
        "frameworks": [
            {"id": "competition", "name": "竞争框架", "description": "太空竞赛、对抗叙事"},
            {"id": "cooperation", "name": "合作框架", "description": "国际合作、共享叙事"},
            {"id": "progress", "name": "进步框架", "description": "科学突破、人类探索"},
            {"id": "threat", "name": "威胁框架", "description": "军事化、安全担忧"},
            {"id": "development", "name": "发展框架", "description": "普惠发展、共赢"},
        ]
    }
