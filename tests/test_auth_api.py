"""
云观星传 - 用户系统 API 测试（Issue #90 多租户自带钥匙模式）

覆盖：
- /api/auth/*：注册（验证码）、登录、登出、me、未登录 401
- /api/user/llm-config：查看（掩码）、保存（验证失败 400 / 成功 200）
- 多租户：未配置 LLM 时 run_stage 返回 400 引导
- /api/admin/*：非 admin 403、用户/项目列表、设管理员、删用户级联删项目
全部自包含：不调用真实邮件/LLM/网络（验证码直写 DB，LLM 验证 mock）。
"""
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.auth import (
    SESSION_COOKIE,
    create_user,
    get_user_by_email,
    get_user_llm_config,
    issue_token,
    save_verification_code,
    set_user_llm_config,
)


def _client_with_user(app, *, email=None, admin=False, with_llm=True):
    """创建已登录 TestClient（直连建用户 + 签发 JWT，绕开邮件验证码）"""
    if email is None:
        email = f"auth{secrets.token_hex(6)}@test.local"
    if admin:
        prev = os.environ.get("ADMIN_EMAILS")
        os.environ["ADMIN_EMAILS"] = email
        try:
            user = create_user(email, "管理员", "Test@123456")
        finally:
            if prev is None:
                os.environ.pop("ADMIN_EMAILS", None)
            else:
                os.environ["ADMIN_EMAILS"] = prev
    else:
        user = create_user(email, "测试用户", "Test@123456")
    if with_llm:
        set_user_llm_config(user["id"], {
            "llm": {"api_key": "test-key", "base_url": "http://llm.test/v1", "model": "test-model"},
            "embedding": None,
        })
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, issue_token(user["id"]))
    return user, client


@pytest.fixture(scope="module")
def app():
    """导入真实 FastAPI 应用（模块级，避免每测试重建）"""
    from api.main import app
    return app


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """每个测试用独立 users.db（防测试间数据串扰）"""
    from api import auth as auth_mod
    monkeypatch.setattr(auth_mod, "USERS_DB", tmp_path / "users.db")
    monkeypatch.setattr(auth_mod, "DATA_DIR", tmp_path)
    auth_mod.init_db()


# ──────────────────────────────────────────────────────────────
# /api/auth/*
# ──────────────────────────────────────────────────────────────

class TestAuthFlow:
    @pytest.fixture(autouse=True)
    def _no_email(self):
        """mock 邮件发送：测试不真发 Resend"""
        with patch("api.routes.auth.send_verification_code", return_value=True):
            yield

    def test_send_code_success_and_cooldown(self, app):
        """发送验证码成功；60s 冷却内重发 429"""
        with TestClient(app) as c:
            r = c.post("/api/auth/send-code", json={"email": "newuser@test.local"})
            assert r.status_code == 200, r.text
            r2 = c.post("/api/auth/send-code", json={"email": "newuser@test.local"})
            assert r2.status_code == 429  # 冷却

    def test_send_code_rejects_invalid_email(self, app):
        with TestClient(app) as c:
            assert c.post("/api/auth/send-code", json={"email": "not-an-email"}).status_code == 400

    def test_send_code_rejects_registered_email(self, app):
        create_user("taken@test.local", "已注册", "Test@123456")
        with TestClient(app) as c:
            assert c.post("/api/auth/send-code", json={"email": "taken@test.local"}).status_code == 409

    def test_register_success_flow(self, app):
        """完整注册：验证码 → 注册 → 登录 → me"""
        save_verification_code("fresh@test.local", "123456")
        with TestClient(app) as c:
            r = c.post("/api/auth/register", json={
                "name": "新同学", "email": "fresh@test.local",
                "password": "Test@123456", "code": "123456",
            })
            assert r.status_code == 201, r.text
            assert r.json()["user"]["email"] == "fresh@test.local"
            assert r.json()["user"]["role"] == "user"
            # 验证码用后即删：同码再注册应提示邮箱已注册
            assert c.post("/api/auth/register", json={
                "name": "新同学", "email": "fresh@test.local",
                "password": "Test@123456", "code": "123456",
            }).status_code == 409

    def test_register_rejects_bad_code(self, app):
        save_verification_code("badcode@test.local", "111111")
        with TestClient(app) as c:
            r = c.post("/api/auth/register", json={
                "name": "X", "email": "badcode@test.local",
                "password": "Test@123456", "code": "000000",
            })
            assert r.status_code == 400
            assert "验证码错误" in r.json()["detail"]

    def test_register_rejects_short_password(self, app):
        save_verification_code("short@test.local", "111111")
        with TestClient(app) as c:
            r = c.post("/api/auth/register", json={
                "name": "X", "email": "short@test.local",
                "password": "123", "code": "111111",
            })
            assert r.status_code in (400, 422)  # 422=Pydantic 校验层拦截
            if r.status_code == 422:
                assert "at least 6 characters" in r.json()["detail"][0]["msg"]
            else:
                assert "至少 6 位" in r.json()["detail"]

    def test_register_without_code(self, app):
        with TestClient(app) as c:
            r = c.post("/api/auth/register", json={
                "name": "X", "email": "nocode@test.local",
                "password": "Test@123456", "code": "",
            })
            assert r.status_code == 400
            assert "验证码" in r.json()["detail"]

    def test_login_wrong_password_and_missing_user(self, app):
        create_user("login@test.local", "登录用户", "Test@123456")
        with TestClient(app) as c:
            assert c.post("/api/auth/login", json={
                "email": "login@test.local", "password": "wrong-pass",
            }).status_code == 401
            assert c.post("/api/auth/login", json={
                "email": "nobody@test.local", "password": "Test@123456",
            }).status_code == 401

    def test_login_logout_me(self, app):
        create_user("me@test.local", "我", "Test@123456")
        with TestClient(app) as c:
            r = c.post("/api/auth/login", json={"email": "me@test.local", "password": "Test@123456"})
            assert r.status_code == 200
            assert r.json()["user"]["email"] == "me@test.local"
            # me：登录态
            r = c.get("/api/auth/me")
            assert r.status_code == 200
            assert r.json()["user"]["name"] == "我"
            assert "llm_configured" in r.json()["user"]
            # 登出后 me 401
            c.post("/api/auth/logout")
            assert c.get("/api/auth/me").status_code == 401

    def test_me_unauthenticated(self, app):
        with TestClient(app) as c:
            assert c.get("/api/auth/me").status_code == 401


# ──────────────────────────────────────────────────────────────
# /api/user/llm-config（多租户自带钥匙）
# ──────────────────────────────────────────────────────────────

class TestLlmConfig:
    def test_get_returns_masked(self, app):
        """已配置 → key 掩码返回；未配置 → configured=False"""
        _, client = _client_with_user(app)
        with client:
            r = client.get("/api/user/llm-config")
            assert r.status_code == 200
            assert r.json()["llm"]["configured"] is True
            # test-key 长度 8 → 全掩码 "***"
            assert r.json()["llm"]["api_key_masked"] == "***"

        _, client2 = _client_with_user(app, with_llm=False)
        with client2:
            r = client2.get("/api/user/llm-config")
            assert r.json()["llm"]["configured"] is False
            assert r.json()["llm"]["api_key_masked"] == ""

    def test_put_validates_and_saves(self, app):
        """保存：LLM 验证失败 400；成功 200 且 me 反映已配置"""
        user, client = _client_with_user(app, with_llm=False)
        with client:
            # 验证失败（mock LLM 抛错）
            with patch("api.routes.user.LLMClient.from_config", side_effect=Exception("bad key")):
                r = client.put("/api/user/llm-config", json={
                    "llm": {"api_key": "sk-bad", "base_url": "http://x/v1", "model": "m"},
                    "embedding": None,
                })
                assert r.status_code == 400
                assert "验证失败" in r.json()["detail"]
            # 验证成功
            fake = type("FakeLLM", (), {"chat": staticmethod(lambda **kw: "PONG")})()
            with patch("api.routes.user.LLMClient.from_config", return_value=fake):
                r = client.put("/api/user/llm-config", json={
                    "llm": {"api_key": "sk-real-12345", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen3.8-max"},
                    "embedding": None,
                })
                assert r.status_code == 200, r.text
            # me 反映已配置
            assert client.get("/api/auth/me").json()["user"]["llm_configured"] is True
            # 存储层：DB 中 llm_api_key 为 Fernet 密文（不含明文 key）
            from api import auth as auth_mod
            stored = auth_mod.get_user_llm_config(user["id"])
            assert stored["llm"]["api_key"] == "sk-real-12345"  # 解密回读正确
            with auth_mod._connect() as conn:
                row = conn.execute("SELECT llm_api_key FROM users WHERE id = ?", (user["id"],)).fetchone()
            assert "sk-real-12345" not in row["llm_api_key"]  # 密文存储
            assert row["llm_api_key"].startswith("gAAAAA")  # Fernet 前缀

    def test_put_requires_all_three(self, app):
        _, client = _client_with_user(app, with_llm=False)
        with client:
            r = client.put("/api/user/llm-config", json={
                "llm": {"api_key": "sk-x", "base_url": "", "model": "m"},
                "embedding": None,
            })
            assert r.status_code == 400

    def test_run_stage_requires_config(self, app):
        """多租户：未配置 LLM 时 run_stage 返回 400 引导（不调用任何 LLM）"""
        from api.main import app as main_app
        _, client = _client_with_user(main_app, with_llm=False)
        with client:
            pid = client.post("/api/workflow/projects", json={"interest": "朱雀2号"}).json()["project"]["id"]
            r = client.post(f"/api/workflow/projects/{pid}/stages/1/run", json={})
            assert r.status_code == 400
            assert "模型设置" in r.json()["detail"]

    def test_config_survives_decrypt(self, app):
        """保存后掩码回读不含明文 key"""
        user, client = _client_with_user(app, with_llm=False)
        with client:
            fake = type("FakeLLM", (), {"chat": staticmethod(lambda **kw: "PONG")})()
            with patch("api.routes.user.LLMClient.from_config", return_value=fake):
                client.put("/api/user/llm-config", json={
                    "llm": {"api_key": "sk-roundtrip-99", "base_url": "http://b/v1", "model": "m"},
                    "embedding": None,
                })
            r = client.get("/api/user/llm-config")
            assert r.status_code == 200
            assert "sk-roundtrip-99" not in r.json()["llm"]["api_key_masked"]
            assert r.json()["llm"]["configured"] is True


# ──────────────────────────────────────────────────────────────
# /api/admin/*（管理后台）
# ──────────────────────────────────────────────────────────────

class TestAdminAPI:
    def test_admin_requires_role(self, app):
        """普通用户访问 admin 接口 → 403"""
        from api.main import app as main_app
        _, client = _client_with_user(main_app, with_llm=False)
        with client:
            assert client.get("/api/admin/users").status_code == 403
            assert client.get("/api/admin/projects").status_code == 403
            assert client.delete("/api/admin/users/xxx").status_code == 403

    def test_admin_lists_users_and_projects(self, app):
        from api.main import app as main_app
        _, admin_client = _client_with_user(main_app, admin=True, with_llm=False)
        # 普通用户 + 项目
        _, user_client = _client_with_user(main_app, with_llm=False)
        pid = user_client.post("/api/workflow/projects", json={"interest": "朱雀2号"}).json()["project"]["id"]
        with admin_client:
            r = admin_client.get("/api/admin/users")
            assert r.status_code == 200
            emails = {u["email"] for u in r.json()["users"]}
            assert len(emails) >= 2
            r = admin_client.get("/api/admin/projects")
            assert r.status_code == 200
            pids = {p["id"] for p in r.json()["projects"]}
            assert pid in pids
            # 归属人信息
            proj = next(p for p in r.json()["projects"] if p["id"] == pid)
            assert proj["owner"] and proj["owner"]["email"].endswith("@test.local")

    def test_admin_set_role_and_delete_user(self, app):
        """设管理员 + 删用户"""
        from api.main import app as main_app
        _, admin_client = _client_with_user(main_app, admin=True, with_llm=False)
        victim, vclient = _client_with_user(main_app, with_llm=False)
        with vclient:
            vclient.post("/api/workflow/projects", json={"interest": "待删项目"})
        with admin_client:
            # 设管理员
            r = admin_client.post(f"/api/admin/users/{victim['id']}/role", json={"role": "admin"})
            assert r.status_code == 200
            assert r.json()["role"] == "admin"
            # 取消管理员
            r = admin_client.post(f"/api/admin/users/{victim['id']}/role", json={"role": "user"})
            assert r.status_code == 200
            # 删用户（级联删其 1 个项目）
            r = admin_client.delete(f"/api/admin/users/{victim['id']}")
            assert r.status_code == 200
            assert r.json()["deleted_projects"] == 1

    def test_admin_delete_user_cascades_projects(self, app):
        from api.main import app as main_app
        _, admin_client = _client_with_user(main_app, admin=True, with_llm=False)
        victim, vclient = _client_with_user(main_app, with_llm=False)
        with vclient:
            pid = vclient.post("/api/workflow/projects", json={"interest": "级联删除"}).json()["project"]["id"]
        with admin_client:
            r = admin_client.delete(f"/api/admin/users/{victim['id']}")
            assert r.status_code == 200
            assert r.json()["deleted_projects"] == 1
            # 项目文件已物理删除
            from src.workflow import get_workflow_engine
            assert get_workflow_engine().get_project(pid) is None

    def test_admin_delete_project(self, app):
        from api.main import app as main_app
        _, admin_client = _client_with_user(main_app, admin=True, with_llm=False)
        _, user_client = _client_with_user(main_app, with_llm=False)
        pid = user_client.post("/api/workflow/projects", json={"interest": "删项目"}).json()["project"]["id"]
        with admin_client:
            r = admin_client.delete(f"/api/admin/projects/{pid}")
            assert r.status_code == 200
            assert admin_client.get(f"/api/admin/projects/{pid}").status_code == 404
