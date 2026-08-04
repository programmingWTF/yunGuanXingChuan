"""
科研流程工作流路由 - 7 智能体编排 API

端点（/api/workflow/*）：
- GET    /stages                     阶段元数据（前端 Research Pipeline 渲染）
- POST   /projects                   创建研究项目
- GET    /projects                   项目列表
- GET    /projects/{id}              项目详情（阶段进度/产出物摘要）
- POST   /projects/{id}/stages/{s}/run      执行阶段 s（同步，产出物落盘为 awaiting_review）
- GET    /projects/{id}/stages/{s}/result   获取阶段产出物
- POST   /projects/{id}/stages/{s}/approve  研究者确认，推进到下一阶段
- GET    /projects/{id}/export?fmt=md|json  汇总导出
"""
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.workflow import get_workflow_engine

router = APIRouter()


class CreateProjectRequest(BaseModel):
    title: str = Field("", max_length=100, description="项目名称")
    interest: str = Field(..., max_length=500, description="初始研究兴趣/议题")


class RunStageRequest(BaseModel):
    inputs: Dict = Field(default_factory=dict, max_length=100, description="阶段输入（如 direction/materials/style_sample）")


@router.get("/stages")
def get_stages():
    """阶段元数据（前端 Research Pipeline 渲染）"""
    return {"stages": get_workflow_engine().get_stage_meta()}


@router.post("/projects")
def create_project(req: CreateProjectRequest):
    """创建研究项目"""
    project = get_workflow_engine().create_project(title=req.title, interest=req.interest)
    return {"project": project.model_dump()}


@router.get("/projects")
def list_projects():
    """项目列表（按创建时间倒序）"""
    projects = get_workflow_engine().list_projects()
    return {"projects": [p.model_dump() for p in projects]}


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    """项目详情（含各阶段状态与产出物）"""
    project = get_workflow_engine().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": project.model_dump()}


@router.post("/projects/{project_id}/stages/{stage}/run")
def run_stage(project_id: str, stage: int, req: RunStageRequest):
    """执行阶段智能体（同步）；产出物落盘为 awaiting_review"""
    try:
        record = get_workflow_engine().run_stage(project_id, stage, req.inputs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # 不回显内部异常细节（可能含文件路径/服务信息），只记日志
        import logging
        logging.getLogger(__name__).exception(f"阶段 {stage} 执行异常（项目 {project_id}）")
        raise HTTPException(status_code=500, detail="阶段执行失败，请稍后重试")
    return {
        "stage": stage,
        "status": record.status.value,
        "output": record.output,
        "error": record.error,
    }


@router.get("/projects/{project_id}/stages/{stage}/result")
def get_stage_result(project_id: str, stage: int):
    """获取阶段产出物"""
    output = get_workflow_engine().get_stage_result(project_id, stage)
    if output is None:
        raise HTTPException(status_code=404, detail="该阶段暂无产出物")
    return {"stage": stage, "output": output}


@router.post("/projects/{project_id}/stages/{stage}/approve")
def approve_stage(project_id: str, stage: int):
    """研究者确认阶段产出物，推进到下一阶段"""
    try:
        project = get_workflow_engine().approve_stage(project_id, stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"project": project.model_dump()}


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, fmt: str = "md"):
    """汇总导出（fmt: md/json）"""
    if fmt not in ("md", "json"):
        raise HTTPException(status_code=400, detail="fmt 仅支持 md/json")
    try:
        result = get_workflow_engine().export_project(project_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result
