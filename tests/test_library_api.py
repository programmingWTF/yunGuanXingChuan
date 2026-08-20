"""
云观星传 - 个人论文库 API 测试

覆盖 /api/library/*：
- 鉴权（未登录 401）
- health（R2 配置状态）
- upload-url（扩展名校验 / R2 未配置 503 / 正常签发）
- confirm（404 / 409 重复 / 成功处理并置 ready）
- list / get / delete / search / style

不依赖真实 R2 与 LLM：monkeypatch R2 操作与向量存储。
"""
import json
import sys
import secrets as _secrets
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from api.auth import SESSION_COOKIE, create_user, issue_token


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    """隔离用户论文库数据目录"""
    import src.knowledge.user_library as ul
    monkeypatch.setattr(ul, "USER_LIBRARY_ROOT", tmp_path / "user_libraries")
    monkeypatch.setattr(ul, "LIBRARY_DB_PATH", tmp_path / "library.db")


@pytest.fixture
def r2_configured(monkeypatch):
    """让 R2 处于已配置状态（mock 真实凭据检查与 S3 调用）"""
    import src.knowledge.user_library as ul
    monkeypatch.setattr(ul, "get_r2_config", lambda: {
        "account_id": "test-account",
        "access_key_id": "test-ak",
        "secret_access_key": "test-sk",
        "bucket": "test-bucket",
        "endpoint": "https://test.r2.cloudflarestorage.com",
    })
    monkeypatch.setattr(ul, "create_presigned_put_url", lambda *a, **kw: "https://presigned.test/upload?token=fake")
    monkeypatch.setattr(ul, "fetch_object", lambda key: ("这是测试论文内容" * 50).encode("utf-8"))
    monkeypatch.setattr(ul, "delete_object", lambda key: None)
    # API 测试不依赖真实 PDF/DOCX 解析（解析细节由单元测试覆盖），
    # 统一 mock 为可索引、可提取风格的纯文本
    monkeypatch.setattr(ul, "parse_document", lambda content, ext: ("深度学习模型在医学影像诊断中展现出优异性能。" * 30))
    # api/routes/library.py 用 `from src.knowledge.user_library import create_presigned_put_url`
    # 模块级绑定 —— 若 api.main 已被其他测试文件 import，路由绑定的是真实函数，
    # 单独 patch ul 模块无效。这里同步 patch 路由模块里绑定的名字，保证全量运行稳定。
    import api.routes.library as lib_routes
    monkeypatch.setattr(lib_routes, "create_presigned_put_url", lambda *a, **kw: "https://presigned.test/upload?token=fake")
    return ul


@pytest.fixture
def r2_not_configured(monkeypatch):
    """R2 未配置状态"""
    import src.knowledge.user_library as ul
    monkeypatch.setattr(ul, "get_r2_config", lambda: {})
    return ul


@pytest.fixture
def auth_client():
    """带登录 cookie 的 TestClient"""
    from api.main import app
    email = f"t{_secrets.token_hex(6)}@test.local"
    user = create_user(email, "测试用户", "Test@123456")
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, issue_token(user["id"]))
    return client, user


def _fake_vector(monkeypatch, add_result=5, search_results=None):
    """Mock 用户级向量库（避免 LLM embedding 调用）"""
    import src.knowledge.user_library as ul
    search_results = search_results or [{
        "text": "深度学习模型在医学影像中应用广泛。",
        "score": 0.85,
        "metadata": {"user_id": "u", "paper_id": 1, "title": "测试"},
    }]
    monkeypatch.setattr(
        ul.UserVectorStore, "add_document",
        lambda self, text, paper_id, title: add_result,
    )
    monkeypatch.setattr(
        ul.UserVectorStore, "search",
        lambda self, query, top_k=5: search_results,
    )
    monkeypatch.setattr(
        ul.UserVectorStore, "remove_paper",
        lambda self, paper_id: None,
    )


class TestLibraryAuth:
    def test_requires_login(self, r2_configured):
        client = TestClient(__import__("api.main", fromlist=["app"]).app)
        r = client.get("/api/library")
        assert r.status_code == 401
        r2 = client.post("/api/library/upload-url", json={"file_name": "a.pdf"})
        assert r2.status_code == 401


class TestLibraryHealth:
    def test_health_configured(self, r2_configured, auth_client):
        client, _ = auth_client
        r = client.get("/api/library/health")
        assert r.status_code == 200
        assert r.json()["r2_configured"] is True
        assert ".pdf" in r.json()["supported_extensions"]

    def test_health_not_configured(self, r2_not_configured, auth_client):
        client, _ = auth_client
        r = client.get("/api/library/health")
        assert r.status_code == 200
        assert r.json()["r2_configured"] is False


class TestUploadUrl:
    def test_upload_url_success(self, r2_configured, auth_client):
        client, _ = auth_client
        r = client.post("/api/library/upload-url", json={
            "file_name": "我的论文.pdf", "content_type": "application/pdf",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["upload_url"].startswith("https://presigned.test/")
        assert data["paper_id"] > 0
        assert data["file_key"].startswith("_") or "/" in data["file_key"]  # {user_id}/... 或含分隔符

    def test_upload_url_rejects_zip(self, r2_configured, auth_client):
        client, _ = auth_client
        r = client.post("/api/library/upload-url", json={"file_name": "archive.zip"})
        assert r.status_code == 400
        assert "不支持的文件类型" in r.json()["detail"]

    def test_upload_url_rejects_no_ext(self, r2_configured, auth_client):
        client, _ = auth_client
        r = client.post("/api/library/upload-url", json={"file_name": "README"})
        assert r.status_code == 400

    def test_upload_url_accepts_all_supported(self, r2_configured, auth_client):
        client, _ = auth_client
        for name in ["a.pdf", "b.docx", "c.md", "d.txt"]:
            r = client.post("/api/library/upload-url", json={"file_name": name})
            assert r.status_code == 200, f"{name} 应被接受"

    def test_upload_url_r2_not_configured(self, r2_not_configured, auth_client):
        client, _ = auth_client
        r = client.post("/api/library/upload-url", json={"file_name": "a.pdf"})
        assert r.status_code == 503
        assert "R2" in r.json()["detail"]


class TestConfirmUpload:
    def test_confirm_success(self, r2_configured, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        # 先建一条
        r = client.post("/api/library/upload-url", json={"file_name": "a.pdf"})
        pid = r.json()["paper_id"]
        # 确认
        r2 = client.post("/api/library/confirm", json={"paper_id": pid})
        assert r2.status_code == 200
        data = r2.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] == 5
        # 列表里应有 ready 状态
        lst = client.get("/api/library").json()
        assert len(lst) == 1
        assert lst[0]["status"] == "ready"

    def test_confirm_missing_paper(self, r2_configured, auth_client):
        client, _ = auth_client
        r = client.post("/api/library/confirm", json={"paper_id": 999})
        assert r.status_code == 404

    def test_confirm_already_ready_conflict(self, r2_configured, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        r = client.post("/api/library/upload-url", json={"file_name": "a.pdf"})
        pid = r.json()["paper_id"]
        assert client.post("/api/library/confirm", json={"paper_id": pid}).status_code == 200
        # 重复 confirm → 409（已 ready）
        r2 = client.post("/api/library/confirm", json={"paper_id": pid})
        assert r2.status_code == 409

    def test_confirm_user_isolation(self, r2_configured, monkeypatch):
        """用户 B 不能 confirm 用户 A 的论文"""
        from api.main import app
        email_a = f"ta{_secrets.token_hex(6)}@test.local"
        email_b = f"tb{_secrets.token_hex(6)}@test.local"
        user_a = create_user(email_a, "A", "Test@123456")
        create_user(email_b, "B", "Test@123456")

        ca = TestClient(app)
        ca.cookies.set(SESSION_COOKIE, issue_token(user_a["id"]))
        with ca:
            r = ca.post("/api/library/upload-url", json={"file_name": "a.pdf"})
            pid = r.json()["paper_id"]

        cb = TestClient(app)
        # B 登录
        cb.post("/api/auth/login", json={"email": email_b, "password": "Test@123456"})
        with cb:
            assert cb.get(f"/api/library/{pid}").status_code == 404
            assert cb.post("/api/library/confirm", json={"paper_id": pid}).status_code == 404
            assert cb.delete(f"/api/library/{pid}").status_code == 404


class TestListGetDelete:
    def test_list_empty(self, r2_configured, auth_client):
        client, _ = auth_client
        assert client.get("/api/library").json() == []

    def test_get_detail(self, r2_configured, auth_client):
        client, _ = auth_client
        pid = client.post("/api/library/upload-url", json={"file_name": "a.pdf"}).json()["paper_id"]
        r = client.get(f"/api/library/{pid}")
        assert r.status_code == 200
        assert r.json()["title"] == "a"
        assert r.json()["status"] == "uploaded"

    def test_get_missing(self, r2_configured, auth_client):
        client, _ = auth_client
        assert client.get("/api/library/999").status_code == 404

    def test_delete(self, r2_configured, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        pid = client.post("/api/library/upload-url", json={"file_name": "a.pdf"}).json()["paper_id"]
        assert client.delete(f"/api/library/{pid}").json()["ok"] is True
        assert client.get("/api/library").json() == []
        assert client.delete(f"/api/library/{pid}").status_code == 404


class TestSearchAndStyle:
    def test_search(self, r2_configured, auth_client, monkeypatch):
        _fake_vector(monkeypatch, search_results=[{
            "text": "命中内容", "score": 0.9, "metadata": {"paper_id": 1},
        }])
        client, _ = auth_client
        r = client.post("/api/library/search", json={"query": "深度学习"})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1
        assert r.json()["results"][0]["score"] == 0.9

    def test_search_requires_query(self, r2_configured, auth_client):
        client, _ = auth_client
        assert client.post("/api/library/search", json={"query": ""}).status_code == 422

    def test_style_empty_404(self, r2_configured, auth_client):
        client, _ = auth_client
        assert client.get("/api/library/style").status_code == 404

    def test_style_after_upload(self, r2_configured, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        pid = client.post("/api/library/upload-url", json={"file_name": "a.pdf"}).json()["paper_id"]
        client.post("/api/library/confirm", json={"paper_id": pid})
        r = client.get("/api/library/style")
        assert r.status_code == 200
        body = r.json()
        # 风格三件套至少包含一个 key
        assert any(k in body for k in ("terms", "structure", "few_shot"))


class TestLibraryRouterRegistered:
    def test_router_in_main_app(self):
        """/api/library 路由已注册（未登录时应 401 而非 404）"""
        from api.main import app
        client = TestClient(app)
        r = client.get("/api/library")
        assert r.status_code == 401  # 注册了路由才会 401（未注册是 404）