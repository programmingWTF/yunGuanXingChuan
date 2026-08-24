"""
云观星传 - 用户认证路由（/api/auth/*）

流程完全对齐 liguiyu-home：
- POST /api/auth/send-code   注册前发送 6 位验证码（已注册邮箱拒绝；60s 冷却）
- POST /api/auth/register    昵称 + 邮箱 + 密码 + 验证码 → 创建用户（ADMIN_EMAILS 自动 admin）
- POST /api/auth/login       邮箱 + 密码 → 签发会话 Cookie
- POST /api/auth/logout      注销（清 Cookie）
- GET  /api/auth/me          当前登录用户
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from api.auth import (
    can_resend_code,
    clear_session_cookie,
    create_user,
    generate_code,
    get_current_user,
    get_user_by_email,
    init_db,
    issue_token,
    save_verification_code,
    set_session_cookie,
    user_llm_configured,
    verify_code,
    verify_password,
)
from api.email import send_verification_code
from src.workflow import get_workflow_engine

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SendCodeRequest(BaseModel):
    email: str = Field(..., max_length=200)


class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=50, description="昵称")
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=6, max_length=100)
    code: str = Field(..., max_length=10)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=100)


@router.post("/send-code")
def send_code(req: SendCodeRequest):
    """注册验证码：发送到指定邮箱（未注册才允许；60s 冷却）"""
    email = req.email.lower().strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    init_db()

    if get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    allowed, wait = can_resend_code(email)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"发送太频繁，请 {wait} 秒后重试")

    code = generate_code()
    save_verification_code(email, code)
    ok = send_verification_code(email, code)
    if not ok:
        # 发送失败：删除刚写入的验证码，避免用户拿到一个永远发不出的码
        import sqlite3
        from api.auth import USERS_DB, _connect
        try:
            with _connect() as conn:
                conn.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
        except sqlite3.Error:
            pass
        raise HTTPException(status_code=500, detail="验证码发送失败，请稍后重试")

    return {"success": True, "message": "验证码已发送，请查收邮件"}


@router.post("/register", status_code=201)
def register(req: RegisterRequest):
    """注册：昵称 + 邮箱 + 密码 + 验证码 → 创建用户（验证码校验通过即视为邮箱已验证）"""
    email = req.email.lower().strip()
    name = req.name.strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if not name:
        raise HTTPException(status_code=400, detail="请输入昵称")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    init_db()

    if get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    err = verify_code(email, req.code.strip())
    if err:
        raise HTTPException(status_code=400, detail=err)

    user = create_user(email, name, req.password)

    # 管理员注册时自动认领无主（legacy）项目（旧项目归管理员名下）
    if user["role"] == "admin":
        try:
            get_workflow_engine().claim_ownerless(user["id"])
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("管理员认领无主项目失败")

    return {"success": True, "message": "注册成功！请登录。", "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}


@router.post("/login")
def login(req: LoginRequest, response: Response):
    """登录：邮箱 + 密码 → 设置会话 Cookie"""
    email = req.email.lower().strip()
    user = get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=401, detail="邮箱未注册")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="密码错误")

    token = issue_token(user["id"])
    set_session_cookie(response, token)
    return {
        "success": True,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
        # 供跨域直传（upload3.liguiyu.com:10443）鉴权用：前端带 Authorization: Bearer <token>
        "token": token,
    }


@router.post("/logout")
def logout(response: Response):
    """注销：清除会话 Cookie"""
    clear_session_cookie(response)
    return {"success": True}


@router.get("/me")
def me(request: Request):
    """当前登录用户（未登录 401）"""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "created_at": user["created_at"],
            "llm_configured": user_llm_configured(user["id"]),
        },
        # 刷新页面后前端内存 token 丢失：me 重新下发一份供跨域上传使用
        "token": issue_token(user["id"]),
    }
