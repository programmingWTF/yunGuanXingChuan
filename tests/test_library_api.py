"""
云观星传 - 个人论文库 API 测试

覆盖 /api/library/*（本地直传方案，替代原 R2 presigned 链路）：
- 鉴权（未登录 401 / Bearer token 跨域鉴权）
- health（storage=local）
- upload（multipart：扩展名校验 / 空文件 / 超限 / 成功处理置 ready / 失败置 error）
- list / get / delete / search / style
- 用户隔离（文件与记录严格按 user_id）

不依赖真实 LLM 与向量嵌入：monkeypatch 解析与向量存储。
"""
import json
import sys
import secrets as _secrets
from pathlib import Path

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
def local_storage(monkeypatch):
    """本地存储链路：mock 解析（不依赖真实 PDF/DOCX 解析与外部服务）"""
    import src.knowledge.user_library as ul
    # API 测试不依赖真实 PDF/DOCX 解析（解析细节由单元测试覆盖），
    # 统一 mock 为可索引、可提取风格的纯文本
    monkeypatch.setattr(ul, "parse_document", lambda content, ext: ("深度学习模型在医学影像诊断中展现出优异性能。" * 30))
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


def _upload(client, name="a.pdf", content=b"fake pdf bytes", content_type="application/pdf"):
    return client.post("/api/library/upload", files={"file": (name, content, content_type)})


class TestLibraryAuth:
    def test_requires_login(self, local_storage):
        client = TestClient(__import__("api.main", fromlist=["app"]).app)
        assert client.get("/api/library").status_code == 401
        r = _upload(client)
        assert r.status_code == 401

    def test_bearer_token_auth(self, local_storage, auth_client):
        """跨域直传（upload3）：无 Cookie，仅 Authorization: Bearer <token> 也能上传"""
        client, user = auth_client
        token = issue_token(user["id"])
        bare = TestClient(__import__("api.main", fromlist=["app"]).app)
        bare.headers["Authorization"] = f"Bearer {token}"
        r = _upload(bare)
        # 文件保存/处理会走真实链路，这里只验证鉴权通过（能进入业务逻辑：400/200 而非 401）
        assert r.status_code in (200, 400, 422)


class TestLibraryHealth:
    def test_health_local(self, local_storage, auth_client):
        client, _ = auth_client
        r = client.get("/api/library/health")
        assert r.status_code == 200
        assert r.json()["storage"] == "local"
        assert ".pdf" in r.json()["supported_extensions"]


class TestUpload:
    def test_upload_success(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        r = _upload(client, "我的论文.pdf")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] == 5
        assert data["paper_id"] > 0
        # 列表里应有 ready 状态
        lst = client.get("/api/library").json()
        assert len(lst) == 1
        assert lst[0]["status"] == "ready"

    def test_upload_rejects_zip(self, local_storage, auth_client):
        client, _ = auth_client
        r = _upload(client, "archive.zip")
        assert r.status_code == 400
        assert "不支持的文件类型" in r.json()["detail"]

    def test_upload_rejects_no_ext(self, local_storage, auth_client):
        client, _ = auth_client
        r = _upload(client, "README")
        assert r.status_code == 400

    def test_upload_accepts_all_supported(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        for name, ct in [("a.pdf", "application/pdf"), ("b.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), ("c.md", "text/markdown"), ("d.txt", "text/plain")]:
            r = _upload(client, name, content=b"x" * 100, content_type=ct)
            assert r.status_code == 200, f"{name} 应被接受: {r.text}"

    def test_upload_empty_file(self, local_storage, auth_client):
        client, _ = auth_client
        r = _upload(client, "empty.pdf", content=b"")
        assert r.status_code == 400
        assert "文件内容为空" in r.json()["detail"]

    def test_upload_too_large(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        from api.routes import library as lib_routes
        # 缩小上限便于测试
        monkeypatch.setattr(lib_routes, "MAX_UPLOAD_BYTES", 1024)
        r = _upload(client, "big.pdf", content=b"x" * 2048)
        assert r.status_code == 413

    def test_upload_process_failure_keeps_error_record(self, local_storage, auth_client, monkeypatch):
        """解析失败 → 记录保留且状态为 error（前端可展示原因）"""
        import src.knowledge.user_library as ul
        def _bad_parse(content, ext):
            raise ValueError("解析失败: 扫描版 PDF")
        monkeypatch.setattr(ul, "parse_document", _bad_parse)
        client, _ = auth_client
        r = _upload(client, "scan.pdf")
        assert r.status_code == 422
        assert "解析失败" in r.json()["detail"]
        lst = client.get("/api/library").json()
        assert len(lst) == 1
        assert lst[0]["status"] == "error"
        assert "解析失败" in lst[0]["error_msg"]

    def test_upload_user_isolation(self, local_storage, monkeypatch):
        """用户 B 不能看到/操作用户 A 的论文（文件与记录隔离）"""
        _fake_vector(monkeypatch)
        from api.main import app
        email_a = f"ta{_secrets.token_hex(6)}@test.local"
        email_b = f"tb{_secrets.token_hex(6)}@test.local"
        user_a = create_user(email_a, "A", "Test@123456")
        create_user(email_b, "B", "Test@123456")

        ca = TestClient(app)
        ca.cookies.set(SESSION_COOKIE, issue_token(user_a["id"]))
        with ca:
            r = _upload(ca, "a.pdf")
            pid = r.json()["paper_id"]

        cb = TestClient(app)
        cb.post("/api/auth/login", json={"email": email_b, "password": "Test@123456"})
        with cb:
            assert cb.get(f"/api/library/{pid}").status_code == 404
            assert cb.delete(f"/api/library/{pid}").status_code == 404

        # A 的文件只存在于 A 的目录下
        import src.knowledge.user_library as ul
        files = list((ul.USER_LIBRARY_ROOT / user_a["id"] / "files").rglob("*"))
        assert len(files) == 1
        assert not (ul.USER_LIBRARY_ROOT / email_b).exists()


class TestListGetDelete:
    def test_list_empty(self, local_storage, auth_client):
        client, _ = auth_client
        assert client.get("/api/library").json() == []

    def test_get_detail(self, local_storage, auth_client):
        client, _ = auth_client
        pid = _upload(client).json()["paper_id"]
        r = client.get(f"/api/library/{pid}")
        assert r.status_code == 200
        assert r.json()["title"] == "a"
        assert r.json()["file_name"] == "a.pdf"

    def test_get_missing(self, local_storage, auth_client):
        client, _ = auth_client
        assert client.get("/api/library/999").status_code == 404

    def test_delete(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, user = auth_client
        pid = _upload(client).json()["paper_id"]
        import src.knowledge.user_library as ul
        files_before = list((ul.USER_LIBRARY_ROOT / user["id"] / "files").rglob("*"))
        assert len(files_before) == 1
        assert client.delete(f"/api/library/{pid}").json()["ok"] is True
        assert client.get("/api/library").json() == []
        # 本地文件同步删除
        assert list((ul.USER_LIBRARY_ROOT / user["id"] / "files").rglob("*")) == []
        assert client.delete(f"/api/library/{pid}").status_code == 404


class TestSearchAndStyle:
    def test_search(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch, search_results=[{
            "text": "命中内容", "score": 0.9, "metadata": {"paper_id": 1},
        }])
        client, _ = auth_client
        r = client.post("/api/library/search", json={"query": "深度学习"})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1
        assert r.json()["results"][0]["score"] == 0.9

    def test_search_requires_query(self, local_storage, auth_client):
        client, _ = auth_client
        assert client.post("/api/library/search", json={"query": ""}).status_code == 422

    def test_style_empty_404(self, local_storage, auth_client):
        client, _ = auth_client
        assert client.get("/api/library/style").status_code == 404

    def test_style_after_upload(self, local_storage, auth_client, monkeypatch):
        _fake_vector(monkeypatch)
        client, _ = auth_client
        _upload(client)
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
