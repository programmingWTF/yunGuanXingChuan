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
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.workflow import get_workflow_engine

router = APIRouter()


class CreateProjectRequest(BaseModel):
    title: str = Field("", max_length=100, description="项目名称")
    interest: str = Field(..., max_length=500, description="初始研究兴趣/议题")


class RunStageRequest(BaseModel):
    inputs: Dict = Field(default_factory=dict, max_length=100, description="阶段输入（如 direction/materials/style_sample）")


class RunAllRequest(BaseModel):
    """一键全流程请求（全部可选，缺省用项目兴趣/规范风格/框架性分析）"""
    materials: Optional[list] = Field(default=None, description="数据分析素材列表（[{name, content}]）")
    style_sample: Optional[str] = Field(default=None, max_length=5000, description="论文写作风格蒸馏样本")
    topic: Optional[str] = Field(default=None, max_length=200, description="研究主题覆盖（默认项目兴趣）")


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


@router.post("/projects/{project_id}/run-all")
def run_all(project_id: str, req: RunAllRequest, background_tasks: BackgroundTasks):
    """
    一键全流程：后台串行执行全部 7 个阶段（选题→文献→设计→方法→数据→写作→评审），
    每阶段自动完成。进度通过 GET /projects/{id} 轮询各阶段状态（running/completed/failed）。
    """
    engine = get_workflow_engine()
    project = engine.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "completed" and all(
        (project.stages.get(str(s)) or {}).status.value == "completed" for s in range(1, 8)
    ):
        raise HTTPException(status_code=400, detail="该项目已全部生成完成，可到各阶段页重新运行")

    background_tasks.add_task(
        engine.run_all, project_id,
        materials=req.materials, style_sample=req.style_sample, topic=req.topic,
    )
    return {"status": "running", "message": "全流程生成已启动，请通过 GET /projects/{id} 查看各阶段进度"}


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, fmt: str = "md"):
    """汇总导出（fmt: md/json/word/pdf）"""
    if fmt not in ("md", "json", "word", "pdf"):
        raise HTTPException(status_code=400, detail="fmt 仅支持 md/json/word/pdf")
    try:
        result = get_workflow_engine().export_project(project_id, fmt)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if fmt in ("word", "pdf"):
        # 二进制文件下载，直接返回文件流
        from fastapi.responses import Response
        from urllib.parse import quote
        title = (result.get("project") or {}).get("title", "云观星传科研项目")
        # 文件名净化：去除引号/换行/控制字符，防 Content-Disposition 头注入
        filename = re.sub(r'[\r\n"\x00-\x1f]', '', title).strip() or "云观星传科研项目"
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if fmt == "word" else "application/pdf"
        )
        # 中文文件名用 RFC 5987（filename*=UTF-8''%xx）编码，HTTP 头仅支持 latin-1
        ascii_ext = "docx" if fmt == "word" else fmt
        ascii_fallback = f"export.{ascii_ext}"
        encoded_name = quote(f"{filename}.{ascii_ext}", safe="")
        return Response(
            content=result["content_bytes"],
            media_type=media_type,
            headers={
                "Content-Disposition":
                    f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_name}",
            },
        )
    return result


class PolishSectionRequest(BaseModel):
    """论文章节润色请求（独立于阶段状态机，不落盘）"""
    section: str = Field(..., max_length=100, description="章节名（如 引言）")
    content: str = Field(..., max_length=12000, description="章节原文")
    instruction: str = Field("", max_length=500, description="润色指令（可选，缺省用规范润色要求）")


@router.post("/projects/{project_id}/stages/{stage}/polish")
def polish_stage_section(project_id: str, stage: int, req: PolishSectionRequest):
    """AI 润色论文章节：返回润色后正文，不修改已确认产出物"""
    if stage != 6:
        raise HTTPException(status_code=400, detail="仅论文写作（⑥）阶段支持章节润色")
    try:
        polished = get_workflow_engine().polish_section(req.section, req.content, req.instruction)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(f"章节润色失败（项目 {project_id}）")
        raise HTTPException(status_code=500, detail="润色失败，请稍后重试")
    return {"section": req.section, "content": polished}


@router.get("/hot-topics")
def hot_topics(limit: int = 6):
    """今日科技热点（统一搜索召回；后端不可用时降级为空列表）"""
    items = get_workflow_engine().get_hot_topics(limit=min(max(limit, 1), 10))
    return {"topics": items}
