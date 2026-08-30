"""
科研流程工作流路由 - 7 智能体编排 API

端点（/api/workflow/*）：
- GET    /stages                     阶段元数据（前端 Research Pipeline 渲染）
- POST   /projects                   创建研究项目
- GET    /projects                   项目列表
- GET    /projects/{id}              项目详情（阶段进度/产出物摘要）
- DELETE /projects/{id}              删除项目（物理移除产出物）
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

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field

from api.auth import get_user_llm_config, require_user, user_llm_configured
from src.workflow import get_workflow_engine

router = APIRouter()


def _require_llm_config(request: Request) -> dict:
    """取当前用户的模型配置；未配置 LLM 时 400 引导去设置页（多租户自带钥匙模式）"""
    user = require_user(request)
    if not user_llm_configured(user["id"]):
        raise HTTPException(
            status_code=400,
            detail="请先在「模型设置」中配置你的 LLM API（Key/BaseURL/模型ID）再生成",
        )
    return get_user_llm_config(user["id"])


def _require_owned_project(project_id: str, user: dict):
    """
    校验项目存在且当前用户可访问。
    - admin：可访问全部项目（含无主 legacy 项目）
    - 普通用户：仅自己的项目（owner_id 匹配）
    他人/无主项目一律 404，不泄露存在性。
    """
    project = get_workflow_engine().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if user.get("role") != "admin" and project.owner_id != user.get("id"):
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


class CreateProjectRequest(BaseModel):
    title: str = Field("", max_length=100, description="项目名称")
    interest: str = Field(..., max_length=500, description="初始研究兴趣/议题")


class RunStageRequest(BaseModel):
    inputs: Dict = Field(default_factory=dict, max_length=100, description="阶段输入（如 direction/materials/style_sample）")
    use_user_style: bool = Field(default=True, description="是否注入用户论文库写作风格（issue #115，默认 True 保持现状）")


class RunAllRequest(BaseModel):
    """一键全流程请求（全部可选，缺省用项目兴趣/规范风格/框架性分析）"""
    materials: Optional[list] = Field(default=None, description="数据分析素材列表（[{name, content}]）")
    style_sample: Optional[str] = Field(default=None, max_length=5000, description="论文写作风格蒸馏样本")
    topic: Optional[str] = Field(default=None, max_length=200, description="研究主题覆盖（默认项目兴趣）")
    use_user_style: bool = Field(default=True, description="是否注入用户论文库写作风格（issue #115，默认 True 保持现状）")


class RQItem(BaseModel):
    """研究问题条目（issue #129 闭环迭代：保存设计编辑入参校验）"""
    id: str = Field(..., min_length=1, max_length=32, description="问题编号（如 RQ1）")
    text: str = Field(..., min_length=1, max_length=2000, description="研究问题文本")


class HypothesisItem(BaseModel):
    """假设条目（issue #129 闭环迭代：保存设计编辑入参校验）"""
    id: str = Field(..., min_length=1, max_length=32, description="假设编号（如 H1）")
    statement: str = Field(..., min_length=1, max_length=3000, description="假设陈述")
    hypothesis_type: str = Field(default="qualitative", description="假设类型（quantitative/qualitative）")


class SaveDesignRequest(BaseModel):
    """保存研究设计编辑（issue #129 闭环迭代：按 AI 诊断建议修改 RQ/H 后保存，design_version +1）"""
    research_questions: List[RQItem] = Field(default_factory=list, description="修改后的 RQ 列表 [{id, text}]")
    hypotheses: List[HypothesisItem] = Field(default_factory=list, description="修改后的 H 列表 [{id, statement, hypothesis_type}]")
    suggestion: str = Field(default="", max_length=2000, description="触发本次修改的 AI 诊断建议（溯源用）")


@router.get("/stages")
def get_stages():
    """阶段元数据（前端 Research Pipeline 渲染）"""
    return {"stages": get_workflow_engine().get_stage_meta()}


@router.post("/projects")
def create_project(req: CreateProjectRequest, request: Request):
    """创建研究项目（归属当前登录用户）"""
    user = require_user(request)
    project = get_workflow_engine().create_project(title=req.title, interest=req.interest, owner_id=user["id"])
    return {"project": project.model_dump()}


@router.get("/projects")
def list_projects(request: Request):
    """项目列表（按创建时间倒序；普通用户仅自己的，admin 全部）"""
    user = require_user(request)
    owner_id = None if user.get("role") == "admin" else user["id"]
    projects = get_workflow_engine().list_projects(owner_id=owner_id)
    return {"projects": [p.model_dump() for p in projects]}


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request):
    """项目详情（含各阶段状态与产出物）"""
    user = require_user(request)
    project = _require_owned_project(project_id, user)
    return {"project": project.model_dump()}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, request: Request):
    """删除项目（物理移除项目文件与其阶段产出物）"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    deleted = get_workflow_engine().delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"status": "deleted", "project_id": project_id}


@router.post("/projects/{project_id}/stages/{stage}/run")
def run_stage(project_id: str, stage: int, req: RunStageRequest, request: Request):
    """执行阶段智能体（同步）；产出物落盘为 awaiting_review"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    llm_config = _require_llm_config(request)
    try:
        record = get_workflow_engine().run_stage(
            project_id, stage, req.inputs,
            llm_config=llm_config, owner_id=user["id"],
            use_user_style=req.use_user_style,
        )
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


@router.post("/projects/{project_id}/stages/3/save")
def save_design_stage(project_id: str, req: SaveDesignRequest, request: Request):
    """保存研究设计编辑（issue #129 闭环迭代）：更新 RQ/H 产出物，design_version +1"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    try:
        project = get_workflow_engine().save_design(
            project_id,
            research_questions=[q.model_dump() for q in req.research_questions],
            hypotheses=[h.model_dump() for h in req.hypotheses],
            suggestion=req.suggestion,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        import logging
        logging.getLogger(__name__).exception(f"设计保存异常（项目 {project_id}）")
        raise HTTPException(status_code=500, detail="设计保存失败，请稍后重试")
    return {"project": project.model_dump(), "design_version": project.design_version}


@router.get("/projects/{project_id}/stages/{stage}/result")
def get_stage_result(project_id: str, stage: int, request: Request):
    """获取阶段产出物"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    output = get_workflow_engine().get_stage_result(project_id, stage)
    if output is None:
        raise HTTPException(status_code=404, detail="该阶段暂无产出物")
    return {"stage": stage, "output": output}


@router.post("/projects/{project_id}/stages/{stage}/approve")
def approve_stage(project_id: str, stage: int, request: Request):
    """研究者确认阶段产出物，推进到下一阶段"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    try:
        project = get_workflow_engine().approve_stage(project_id, stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"project": project.model_dump()}


@router.post("/projects/{project_id}/run-all")
def run_all(project_id: str, req: RunAllRequest, request: Request, background_tasks: BackgroundTasks):
    """
    一键全流程：后台串行执行全部 7 个阶段（选题→文献→设计→方法→数据→写作→评审），
    每阶段自动完成。进度通过 GET /projects/{id} 轮询各阶段状态（running/completed/failed）。
    """
    user = require_user(request)
    project = _require_owned_project(project_id, user)
    llm_config = _require_llm_config(request)
    if project.status == "completed" and all(
        (project.stages.get(str(s)) or {}).status.value == "completed" for s in range(1, 8)
    ):
        raise HTTPException(status_code=400, detail="该项目已全部生成完成，可到各阶段页重新运行")

    background_tasks.add_task(
        get_workflow_engine().run_all, project_id,
        materials=req.materials, style_sample=req.style_sample, topic=req.topic,
        llm_config=llm_config, owner_id=user["id"],
        use_user_style=req.use_user_style,
    )
    return {"status": "running", "message": "全流程生成已启动，请通过 GET /projects/{id} 查看各阶段进度"}


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, request: Request, fmt: str = "md"):
    """汇总导出（fmt: md/json/word/pdf）"""
    user = require_user(request)
    _require_owned_project(project_id, user)
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
def polish_stage_section(project_id: str, stage: int, req: PolishSectionRequest, request: Request):
    """AI 润色论文章节：返回润色后正文，不修改已确认产出物"""
    user = require_user(request)
    _require_owned_project(project_id, user)
    llm_config = _require_llm_config(request)
    if stage != 6:
        raise HTTPException(status_code=400, detail="仅论文写作（⑥）阶段支持章节润色")
    try:
        polished = get_workflow_engine().polish_section(req.section, req.content, req.instruction, llm_config=llm_config)
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
