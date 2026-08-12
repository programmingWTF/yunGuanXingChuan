"""
云观星传 - 管理后台路由（/api/admin/*）

两种模式：
- 正常模式（主站 tzb.liguiyu.com）：仅 admin 角色可访问（require_admin）
- ADMIN_MODE=true（独立管理容器 tzb-admin.liguiyu.com）：**不校验登录/角色**，
  身份认证完全依赖 Cloudflare Access（模仿 liguiyu-home 的 admin.liguiyu.com 架构）

接口：
- GET    /api/admin/users                    用户列表（含各自项目数）
- POST   /api/admin/users/{id}/role          设置/取消管理员（{role: admin|user}）
- DELETE /api/admin/users/{id}               删除用户（级联删除其全部项目）
- GET    /api/admin/projects                 全部项目 + 归属人（含无主 legacy）
- GET    /api/admin/projects/{id}            项目详情（与前台同构）
- DELETE /api/admin/projects/{id}            删除项目（物理移除文件）
"""
import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import (
    USERS_DB,
    _connect,
    get_user_by_id,
    init_db,
    list_users,
    require_admin,
    user_llm_configured,
)
from src.workflow import get_workflow_engine

router = APIRouter()


def _is_admin_mode() -> bool:
    return os.environ.get("ADMIN_MODE", "").strip().lower() == "true"


def _admin_guard(request: Request) -> dict:
    """ADMIN_MODE 下跳过鉴权（身份认证交给 Cloudflare Access）；否则要求 admin 角色"""
    if _is_admin_mode():
        return {"id": "admin-console", "role": "admin"}
    return require_admin(request)


def _owner_info(owner_id):
    if not owner_id:
        return None
    u = get_user_by_id(owner_id)
    if u is None:
        return {"id": owner_id, "email": "(已删除用户)", "name": "未知"}
    return {"id": u["id"], "email": u["email"], "name": u["name"]}


class RoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$", description="admin 或 user")


@router.get("/users")
def admin_users(request: Request):
    """用户列表（admin）：每个用户的注册信息 + 项目数"""
    _admin_guard(request)
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
            "llm_configured": user_llm_configured(u["id"]),
        })
    return {"users": users, "total_projects": len(projects)}


@router.post("/users/{user_id}/role")
def set_user_role(request: Request, user_id: str, req: RoleRequest):
    """设置/取消管理员角色"""
    _admin_guard(request)
    init_db()
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    now = __import__("time").time()
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (req.role, int(now), user_id),
        )
    return {"success": True, "user_id": user_id, "role": req.role}


@router.delete("/users/{user_id}")
def delete_user(request: Request, user_id: str):
    """删除用户（级联删除其全部项目文件）"""
    _admin_guard(request)
    init_db()
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    engine = get_workflow_engine()
    deleted_projects = engine.delete_projects_by_owner(user_id)
    with _connect() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.execute("DELETE FROM verification_codes WHERE email = ?", (user["email"],))
    return {
        "success": True,
        "deleted_user": user["email"],
        "deleted_projects": deleted_projects,
    }


@router.get("/projects")
def admin_projects(request: Request):
    """全部项目 + 归属人（admin）；含无主（legacy）项目"""
    _admin_guard(request)
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
    _admin_guard(request)
    init_db()
    project = get_workflow_engine().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    d = project.model_dump()
    d["owner"] = _owner_info(project.owner_id)
    return {"project": d}


@router.delete("/projects/{project_id}")
def admin_delete_project(request: Request, project_id: str):
    """删除项目（物理移除项目文件与其阶段产出物）"""
    _admin_guard(request)
    deleted = get_workflow_engine().delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"status": "deleted", "project_id": project_id}
