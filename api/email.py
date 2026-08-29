"""
云观星传 - 邮箱发送（Resend）

发件人用比赛正式域名：`云观星传 <noreply@yunguanxingchuan.xyz>`。
模板为星空主题的深色卡片设计语言，品牌为云观星传。
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

# ── 比赛正式域名发件人（桂鱼 2026-08-30 定）──
FROM_EMAIL = "云观星传 <noreply@yunguanxingchuan.xyz>"
RESEND_API_URL = "https://api.resend.com/emails"


def _resend_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip()


def send_verification_code(to: str, code: str) -> bool:
    """
    发送 6 位注册验证码。返回是否发送成功（失败不抛异常，记日志）。
    """
    key = _resend_key()
    if not key:
        logger.error("[email] RESEND_API_KEY 未配置，无法发送验证码")
        return False

    subject = f"{code} 是你的云观星传注册验证码"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
    <style>
      .email-box {{ background:linear-gradient(180deg,#0b1d3a 0%,#101f42 100%); border-radius:16px; }}
      .email-title {{ color:#fff; }}
      .email-star {{ color:#7dd3fc; }}
      .email-code-bg {{ background:rgba(14,165,233,0.12); border:1px solid rgba(125,211,252,0.35); white-space:nowrap; }}
      .email-code-label {{ color:rgba(255,255,255,0.55); }}
      .email-code {{ color:#fff; text-shadow:0 0 12px rgba(125,211,252,0.6); white-space:nowrap; }}
      .email-hint {{ color:rgba(255,255,255,0.38); }}
      @media (prefers-color-scheme: light) {{
        .email-box {{ background:#f8fafc; border:1px solid #e2e8f0; }}
        .email-title {{ color:#0f172a; }}
        .email-star {{ color:#0284c7; }}
        .email-code-bg {{ background:rgba(14,165,233,0.06); border:1px solid rgba(14,165,233,0.2); }}
        .email-code-label {{ color:rgba(15,23,42,0.5); }}
        .email-code {{ color:#0f172a; text-shadow:none; }}
        .email-hint {{ color:rgba(15,23,42,0.35); }}
      }}
    </style></head>
    <body style="margin:0;padding:0">
    <div style="max-width:480px;margin:0 auto;font-family:'Noto Serif SC','Source Han Serif SC','Source Han Serif',serif">
      <div class="email-box" style="padding:32px;text-align:center">
        <p class="email-star" style="font-size:13px;letter-spacing:0.5em;margin:0 0 8px">✦ ✦ ✦</p>
        <h1 class="email-title" style="font-size:22px;margin:0 0 20px;letter-spacing:0.12em">云观 · 星传</h1>
        <div class="email-code-bg" style="border-radius:12px;padding:24px;margin:0 0 24px">
          <p class="email-code-label" style="font-size:14px;margin:0 0 12px">✦ 你的注册验证码 ✦</p>
          <p class="email-code" style="font-size:36px;font-weight:700;letter-spacing:8px;margin:0;font-family:monospace">{code}</p>
        </div>
        <p class="email-hint" style="font-size:13px;margin:0 0 8px">
          验证码 10 分钟内有效，请勿泄露给他人。
        </p>
        <p class="email-star" style="font-size:13px;letter-spacing:0.5em;margin:0 0 8px">✦ ─── ✦</p>
        <p style="color:rgba(128,128,128,0.45);font-size:12px;margin:0">
          如果你没有注册云观星传，请忽略此邮件。
        </p>
      </div>
    </div>
    </body></html>
    """

    try:
        resp = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "from": FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=15,
        )
        if resp.status_code >= 300:
            logger.error(f"[email] Resend 返回 {resp.status_code}: {resp.text[:200]}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"[email] 发送验证码失败: {e}")
        return False
