"""
云观星传 - 管理后台路由（/api/admin/*，仅 admin 角色）

- GET /api/admin/users       用户列表（含各自项目数）
- GET /api/admin/projects    全部项目 + 归属人（邮箱/昵称），按创建时间倒序
- GET /api/admin/projects/{id}  项目详情（与前台 /api/workflow/projects/{id} 同构，
                                 前端复用同一套渲染组件）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request

from api.auth import get_user_by_id, init_db, list_users, require_admin
from src.workflow import get_workflow_engine

router = APIRouter()


def _owner_info(owner_id):
    if not owner_id:
        return None
    u = get_user_by_id(owner_id)
    if u is None:
        return {"id": owner_id, "email": "(已删除用户)", "name": "未知"}
    return {"id": u["id"], "email": u["email"], "name": u["name"]}


@router.get("/users")
def admin_users(request: Request):
    """用户列表（admin）：每个用户的注册信息 + 项目数"""
    require_admin(request)
    init_db()
    engine = get_workflow_engine()
    projects = engine.list_projects()  # 全量（admin 视角）
    counts: dict = {}
    for p in projects:
        counts[p.owner_id] = counts.get(p.owner_id, 0) + 1
    users = []
    for u in list_users():
        users.append({
            "id": u["id"],
            "email": u["email"],
            "name": u["name"],
            "role": u["role"],
            "created_at": u["created_at"],
            "project_count": counts.get(u["id"], 0),
        })
    return {"users": users, "total_projects": len(projects)}


@router.get("/projects")
def admin_projects(request: Request):
    """全部项目 + 归属人（admin）；含无主（legacy）项目"""
    require_admin(request)
    init_db()
    engine = get_workflow_engine()
    projects = engine.list_projects()
    items = []
    for p in projects:
        d = p.model_dump()
        d["owner"] = _owner_info(p.owner_id)
        items.append(d)
    return {"projects": items, "count": len(items)}


@router.get("/projects/{project_id}")
def admin_project_detail(request: Request, project_id: str):
    """项目详情（admin 视角，与前台同构）"""
    require_admin(request)
    init_db()
    project = get_workflow_engine().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    d = project.model_dump()
    d["owner"] = _owner_info(project.owner_id)
    return {"project": d}
