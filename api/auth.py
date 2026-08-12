"""
云观星传 - 用户认证模块（用户系统设计完全对齐 liguiyu-home）

- SQLite: data/users.db（users + verification_codes 表）
- bcrypt 密码哈希（cost=12，与 liguiyu-home 一致）
- JWT httpOnly Cookie 会话（7 天有效；cookie 名仿 next-auth 风格）
- Resend 发送 6 位邮箱验证码（10 分钟有效，60 秒重发冷却）
- 角色：注册时按 ADMIN_EMAILS 环境变量自动授予 admin（照搬 liguiyu-home）

安全要点：
- 密码只存 bcrypt 哈希；验证码用后即删；
- 会话 cookie httpOnly + sameSite=lax（与 liguiyu-home 相同，未开 secure——
  部署为局域网 HTTP；若后续走 HTTPS 公网域名需改为 secure=true）；
- JWT 密钥优先环境变量 JWT_SECRET，否则持久化到 data/.jwt_secret（重启不失效）。
"""
import logging
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import bcrypt
import jwt
from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
USERS_DB = DATA_DIR / "users.db"

# ── 会话 / 验证码配置 ──
SESSION_COOKIE = "yunguanxingchuan.session"
JWT_ALGO = "HS256"
SESSION_DAYS = 7
CODE_TTL_SECONDS = 600        # 验证码 10 分钟有效（与 liguiyu-home 一致）
CODE_RESEND_COOLDOWN = 60     # 同一邮箱重发冷却 60 秒
CODE_MAX_ATTEMPTS = 10        # 验证码错误尝试上限（防爆破）

_lock = threading.RLock()
_secret: Optional[str] = None


def get_secret() -> str:
    """JWT 密钥：优先环境变量，否则持久化到 data/.jwt_secret"""
    global _secret
    if _secret:
        return _secret
    env = os.environ.get("JWT_SECRET", "").strip()
    if env:
        _secret = env
        return env
    with _lock:
        if _secret:
            return _secret
        secret_file = DATA_DIR / ".jwt_secret"
        if secret_file.exists():
            _secret = secret_file.read_text().strip()
        else:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _secret = secrets.token_hex(32)
            secret_file.write_text(_secret)
            os.chmod(secret_file, 0o600)
    return _secret


# ──────────────────────────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）。email_verified 恒为 1：注册即通过邮箱验证码完成验证。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id             TEXT PRIMARY KEY,
                email          TEXT NOT NULL UNIQUE,
                name           TEXT NOT NULL DEFAULT '',
                password_hash  TEXT NOT NULL,
                role           TEXT NOT NULL DEFAULT 'user',
                email_verified INTEGER NOT NULL DEFAULT 1,
                created_at     INTEGER NOT NULL,
                updated_at     INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS verification_codes (
                email         TEXT PRIMARY KEY,
                code          TEXT NOT NULL,
                expires_at    INTEGER NOT NULL,
                last_sent_at  INTEGER NOT NULL DEFAULT 0,
                attempts      INTEGER NOT NULL DEFAULT 0
            );
            """
        )


# ──────────────────────────────────────────────────────────────────
# 用户
# ──────────────────────────────────────────────────────────────────

def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _admin_emails() -> set:
    return {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def create_user(email: str, name: str, password: str) -> dict:
    """创建用户。ADMIN_EMAILS 中的邮箱自动获得 admin 角色（照搬 liguiyu-home）。"""
    now = _now()
    user_id = str(uuid4())
    role = "admin" if email.lower() in _admin_emails() else "user"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, password_hash, role, email_verified, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (user_id, email, name, hash_password(password), role, now, now),
        )
    return {"id": user_id, "email": email, "name": name, "role": role}


def get_user_by_email(email: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, email, name, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────
# 会话（JWT httpOnly Cookie）
# ──────────────────────────────────────────────────────────────────

def issue_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=SESSION_DAYS),
    }
    return jwt.encode(payload, get_secret(), algorithm=JWT_ALGO)


def set_session_cookie(response: Response, token: str) -> None:
    """httpOnly + sameSite=lax + path=/（对齐 liguiyu-home 的 next-auth cookie 配置）"""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,  # 局域网 HTTP 部署；走 HTTPS 时改为 True
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_current_user(request: Request) -> Optional[dict]:
    """从 Cookie 解析会话；无效/过期返回 None（不抛错，由路由决定 401）。"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, get_secret(), algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None
    return get_user_by_id(payload.get("sub", ""))


def require_user(request: Request) -> dict:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ──────────────────────────────────────────────────────────────────
# 邮箱验证码
# ──────────────────────────────────────────────────────────────────

def generate_code() -> str:
    """6 位数字验证码（与 liguiyu-home 的 randomInt(100000, 999999) 一致）"""
    return f"{secrets.randbelow(900000) + 100000}"


def save_verification_code(email: str, code: str) -> int:
    """写入验证码（覆盖旧码），返回过期时间戳"""
    now = _now()
    expires = now + CODE_TTL_SECONDS
    with _connect() as conn:
        conn.execute(
            "INSERT INTO verification_codes (email, code, expires_at, last_sent_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(email) DO UPDATE SET"
            " code=excluded.code, expires_at=excluded.expires_at, last_sent_at=excluded.last_sent_at, attempts=0",
            (email.lower(), code, expires, now),
        )
    return expires


def can_resend_code(email: str) -> tuple[bool, int]:
    """是否允许重发；返回 (允许, 还需等待秒数)"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT last_sent_at FROM verification_codes WHERE email = ?", (email.lower(),)
        ).fetchone()
    if row is None:
        return True, 0
    wait = CODE_RESEND_COOLDOWN - (_now() - row["last_sent_at"])
    return (wait <= 0, max(wait, 0))


def verify_code(email: str, code: str) -> str:
    """
    校验验证码。返回 "" 表示通过；否则返回错误文案（中文，直接给前端展示）。
    连续错误超过 CODE_MAX_ATTEMPTS 后锁定该验证码（需重新获取）。
    """
    email = email.lower().strip()
    with _connect() as conn:
        row = conn.execute(
            "SELECT code, expires_at, attempts FROM verification_codes WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            return "请先获取邮箱验证码"
        if row["expires_at"] < _now():
            return "验证码已过期，请重新获取"
        if row["attempts"] >= CODE_MAX_ATTEMPTS:
            return "验证码尝试次数过多，请重新获取"
        if row["code"] != code:
            conn.execute(
                "UPDATE verification_codes SET attempts = attempts + 1 WHERE email = ?", (email,)
            )
            return "验证码错误"
        conn.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
    return ""
