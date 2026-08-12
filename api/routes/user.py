"""
云观星传 - 用户模型配置路由（/api/user/*）

多租户"自带钥匙"模式：每次推理使用用户自己的 LLM API（不用平台 key）。
- GET /api/user/llm-config      查看（key 掩码，不回传明文）
- PUT /api/user/llm-config      保存（自动验证：LLM 必填且连通；Embedding 可选，填了才验证）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import (
    get_user_llm_config,
    require_user,
    set_user_llm_config,
)
from src.llm_client import LLMClient

router = APIRouter()


class LLMItem(BaseModel):
    api_key: str = Field("", max_length=500)
    base_url: str = Field("", max_length=300)
    model: str = Field("", max_length=100)


class LlmConfigRequest(BaseModel):
    llm: LLMItem
    embedding: LLMItem | None = None


def _mask(key: str) -> str:
    """掩码显示：sk-abc***xyz（仅前端展示用）"""
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}***{key[-4:]}"


def _validate_llm(item: LLMItem) -> None:
    """验证 LLM 配置：用该 key 发一次 ping，失败抛 400（保存前拦截）"""
    cfg = {"llm": {"api_key": item.api_key, "base_url": item.base_url, "model": item.model},
           "embedding": None}
    try:
        client = LLMClient.from_config(cfg)
        reply = client.chat(
            system_prompt="你是连通性测试助手。",
            user_prompt="回复 PONG",
            json_mode=False,
            max_tokens=128,  # DeepSeek 等模型思考链会消耗 token，太小会返回空
        )
        if not reply:
            raise ValueError("空响应")
    except Exception as e:  # noqa: BLE001
        detail = str(e)[:200]
        raise HTTPException(status_code=400, detail=f"LLM 连接验证失败：{detail}")


def _validate_embedding(item: LLMItem) -> None:
    """验证 Embedding 配置（可选）：调一次 embedding，失败抛 400"""
    cfg = {"llm": {"api_key": "ping", "base_url": "http://127.0.0.1:1", "model": "ping"},
           "embedding": {"api_key": item.api_key, "base_url": item.base_url, "model": item.model}}
    try:
        client = LLMClient.from_config(cfg)
        vec = client.get_embedding("连通性测试")
        if vec is None:
            raise ValueError("未返回向量")
    except Exception as e:  # noqa: BLE001
        detail = str(e)[:200]
        raise HTTPException(status_code=400, detail=f"Embedding 验证失败：{detail}")


@router.get("/llm-config")
def get_llm_config(request: Request):
    """查看当前用户模型配置（key 掩码）"""
    user = require_user(request)
    cfg = get_user_llm_config(user["id"])
    llm, emb = cfg.get("llm") or {}, cfg.get("embedding") or {}
    return {
        "llm": {
            "api_key_masked": _mask(llm.get("api_key") or ""),
            "configured": bool(llm.get("api_key") and llm.get("base_url") and llm.get("model")),
            "base_url": llm.get("base_url") or "",
            "model": llm.get("model") or "",
        },
        "embedding": {
            "api_key_masked": _mask(emb.get("api_key") or ""),
            "configured": bool(emb.get("api_key") and emb.get("base_url") and emb.get("model")),
            "base_url": emb.get("base_url") or "",
            "model": emb.get("model") or "",
        },
    }


@router.put("/llm-config")
def put_llm_config(req: LlmConfigRequest, request: Request):
    """保存模型配置。LLM 必填并验证连通；Embedding 可选（留空=清除/降级）。"""
    user = require_user(request)

    llm = req.llm
    if not (llm.api_key.strip() and llm.base_url.strip() and llm.model.strip()):
        raise HTTPException(status_code=400, detail="LLM 的 API Key / BaseURL / 模型ID 均为必填")
    _validate_llm(llm)

    emb = req.embedding
    embedding_cfg = None
    if emb and (emb.api_key.strip() or emb.base_url.strip() or emb.model.strip()):
        if not (emb.api_key.strip() and emb.base_url.strip() and emb.model.strip()):
            raise HTTPException(status_code=400, detail="Embedding 三项需一起填写（或全部留空）")
        _validate_embedding(emb)
        embedding_cfg = {"api_key": emb.api_key, "base_url": emb.base_url, "model": emb.model}

    set_user_llm_config(user["id"], {
        "llm": {"api_key": llm.api_key, "base_url": llm.base_url, "model": llm.model},
        "embedding": embedding_cfg,
    })
    return {"success": True, "message": "模型配置已保存（LLM 必填，Embedding 可选）"}
