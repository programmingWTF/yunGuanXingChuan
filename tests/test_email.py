"""
云观星传 - 邮件验证码发送单元测试（Mock Resend HTTP，不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock


class TestSendVerificationCode:
    """send_verification_code 测试"""

    def test_no_api_key_returns_false(self, monkeypatch):
        """RESEND_API_KEY 未配置应返回 False 不抛异常"""
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from api.email import send_verification_code
        assert send_verification_code("user@test.com", "123456") is False

    def test_blank_api_key_returns_false(self, monkeypatch):
        """Key 为空白字符串也应返回 False"""
        monkeypatch.setenv("RESEND_API_KEY", "   ")
        from api.email import send_verification_code
        assert send_verification_code("user@test.com", "123456") is False

    @patch('api.email.httpx.post')
    def test_success_returns_true(self, mock_post, monkeypatch):
        """2xx 响应应返回 True"""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp
        from api.email import send_verification_code
        assert send_verification_code("user@test.com", "887766") is True
        # 请求体校验
        kwargs = mock_post.call_args.kwargs
        assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
        body = kwargs["json"]
        assert body["to"] == ["user@test.com"]
        assert "887766" in body["subject"]
        assert "887766" in body["html"]  # 验证码渲染进邮件正文

    @patch('api.email.httpx.post')
    def test_error_status_returns_false(self, mock_post, monkeypatch):
        """3xx/4xx/5xx 响应应返回 False"""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        resp = MagicMock()
        resp.status_code = 422
        resp.text = '{"error": "invalid"}'
        mock_post.return_value = resp
        from api.email import send_verification_code
        assert send_verification_code("bad@test.com", "123456") is False

    @patch('api.email.httpx.post')
    def test_network_error_returns_false(self, mock_post, monkeypatch):
        """网络异常应捕获并返回 False"""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        mock_post.side_effect = ConnectionError("dns fail")
        from api.email import send_verification_code
        assert send_verification_code("user@test.com", "123456") is False

    @patch('api.email.httpx.post')
    def test_sender_is_brand_domain(self, mock_post, monkeypatch):
        """发件人应为比赛正式域名"""
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        resp = MagicMock()
        resp.status_code = 200
        mock_post.return_value = resp
        from api.email import send_verification_code, FROM_EMAIL
        send_verification_code("user@test.com", "112233")
        body = mock_post.call_args.kwargs["json"]
        assert body["from"] == FROM_EMAIL
        assert "yunguanxingchuan.xyz" in FROM_EMAIL
