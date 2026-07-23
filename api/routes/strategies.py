"""
策略路由 - 获取传播策略
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query
from typing import Optional

from src.knowledge.data_loader import get_data_loader

router = APIRouter()


@router.get("/")
async def get_strategies(
    audience: Optional[str] = Query(None, description="按受众筛选"),
    persona: Optional[str] = Query(None, description="按叙事人设筛选"),
):
    """获取策略列表"""
    return {
        "strategies": [],
        "filters": {"audience": audience, "persona": persona},
        "message": "请先运行分析任务"
    }


@router.get("/personas")
async def get_personas():
    """获取所有叙事人设"""
    return {
        "personas": [
            {"id": "scientist", "name": "科学家", "style": "Nature/Science 期刊风格", "audience": "国际科学共同体"},
            {"id": "collaborator", "name": "合作者", "style": "联合国报告风格", "audience": "全球南方公众"},
            {"id": "storyteller", "name": "讲述者", "style": "国家地理/纪录片风格", "audience": "发达国家大众"},
            {"id": "communicator", "name": "沟通者", "style": "智库/政策分析风格", "audience": "美国政策精英"},
        ]
    }


@router.get("/audiences")
async def get_audiences():
    """获取所有受众画像"""
    data_loader = get_data_loader()
    profiles = data_loader.load_audience_profiles()
    return {"audiences": profiles}
