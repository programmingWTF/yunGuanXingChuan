"""安全回归测试：SPA 静态文件服务路径穿越防护

背景：api/main.py 的 SPA fallback 路由曾允许 /../../.env 穿越读取
敏感文件（泄露 API Key）。本测试验证解析后的路径必须仍位于
frontend_dist 内，否则回退 index.html。
"""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def spa_app(monkeypatch, tmp_path):
    """构造带可控 frontend_dist 的应用（不依赖真实构建产物）"""
    import api.main as main
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA index</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log('app');", encoding="utf-8")
    # 敏感文件放在 frontend_dist 之外（上一级），验证无法被穿越读取
    (tmp_path / ".env").write_text("API_KEY=super_secret_123", encoding="utf-8")
    monkeypatch.setattr(main, "frontend_dist", dist)
    return main.app


class TestSpaStaticService:
    """SPA 静态服务正常行为"""

    def test_normal_asset_served(self, spa_app):
        """存在的文件应原样返回"""
        client = TestClient(spa_app)
        resp = client.get("/app.js")
        assert resp.status_code == 200
        assert "console.log('app')" in resp.text

    def test_spa_fallback_for_unknown_route(self, spa_app):
        """未知前端路由应回退 index.html"""
        client = TestClient(spa_app)
        resp = client.get("/some/client/route")
        assert resp.status_code == 200
        assert "<html>SPA index</html>" in resp.text


class TestPathTraversal:
    """路径穿越防护"""

    def test_http_traversal_does_not_leak_env(self, spa_app):
        """HTTP 层：/../../.env 不应返回敏感文件内容"""
        client = TestClient(spa_app)
        resp = client.get("/../../.env")
        assert resp.status_code == 200
        assert "super_secret_123" not in resp.text
        assert "<html>SPA index</html>" in resp.text

    def test_func_level_traversal_blocked(self, monkeypatch, tmp_path):
        """函数级：直接调用 serve_frontend 传 ../../.env，应回退 index.html"""
        import api.main as main
        from starlette.requests import Request

        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("INDEX-MARKER", encoding="utf-8")
        (tmp_path / ".env").write_text("SECRET-MARKER", encoding="utf-8")
        monkeypatch.setattr(main, "frontend_dist", dist)

        scope = {
            "type": "http", "method": "GET", "path": "/../../.env",
            "headers": [], "query_string": b"", "server": None,
            "client": None, "scheme": "http", "root_path": "",
            "app": main.app, "state": {},
        }
        request = Request(scope)
        resp = asyncio.run(main.serve_frontend(request, "../../.env"))
        # FileResponse 不直接暴露 body，其 path 应指向 dist 内的 index.html（而非被穿越的 .env）
        assert resp.path.name == "index.html"
        assert resp.path != (tmp_path / ".env")
