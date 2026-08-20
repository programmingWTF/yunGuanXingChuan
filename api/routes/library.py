"""
云观星传 - 个人论文库 API（/api/library/*）

R2 直传链路（绕开 CF Tunnel 100MB/100s 限制）：
  1. POST /upload-url  → 后端签发 R2 presigned PUT URL + 建论文记录(uploaded)
  2. 前端 PUT 文件到 presigned URL（浏览器直传 R2，不经过后端）
  3. POST /confirm     → 确认传完，后端拉取 R2 → 解析 → 嵌入 → 风格提取 (ready/error)

所有接口 require_user（Cookie 会话），数据严格按 user_id 隔离。
"""
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import require_user
from src.knowledge.user_library import (
    SUPPORTED_EXTENSIONS,
    UserLibrary,
    create_presigned_put_url,
    file_key_for,
    get_user_library,
    init_db,
    r2_configured,
)

router = APIRouter()

MAX_FILE_NAME = 255


class UploadUrlRequest(BaseModel):
    file_name: str = Field(..., max_length=MAX_FILE_NAME)
    content_type: str = Field("application/octet-stream", max_length=200)


class UploadUrlResponse(BaseModel):
    upload_url: str
    file_key: str
    paper_id: int
    expires_in: int = 3600


class ConfirmRequest(BaseModel):
    paper_id: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)


def _validate_ext(file_name: str) -> str:
    """校验扩展名并返回小写 ext（含点）"""
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext or '(无扩展名)'}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    return ext


def _require_r2():
    if not r2_configured():
        raise HTTPException(status_code=503, detail="R2 存储未配置，请联系管理员")


@router.get("/health")
def library_health():
    """R2 配置状态（前端可用来提示）"""
    init_db()  # 幂等，首次访问建表（避免 import 副作用）
    return {"r2_configured": r2_configured(), "supported_extensions": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/upload-url", response_model=UploadUrlResponse)
def get_upload_url(req: UploadUrlRequest, request: Request):
    """① 签发 R2 presigned PUT URL（前端直传用）"""
    user = require_user(request)
    _require_r2()
    ext = _validate_ext(req.file_name)
    title = Path(req.file_name).stem[:200] or "未命名"

    lib = get_user_library(user["id"])
    file_key = file_key_for(user["id"], req.file_name)
    paper_id = lib.create_paper(title=title, file_key=file_key, file_name=req.file_name, file_ext=ext)

    try:
        upload_url = create_presigned_put_url(file_key, req.content_type or "application/octet-stream")
    except Exception as e:  # noqa: BLE001
        # 签发失败要回滚论文记录，避免脏数据
        lib.delete_paper(paper_id)
        raise HTTPException(status_code=502, detail=f"R2 签发失败: {e}") from e

    return UploadUrlResponse(upload_url=upload_url, file_key=file_key, paper_id=paper_id)


@router.post("/confirm")
def confirm_upload(req: ConfirmRequest, request: Request):
    """② 前端确认已传完 → 后端拉取解析嵌入（同步，返回处理结果）"""
    user = require_user(request)
    lib = get_user_library(user["id"])
    paper = lib.get_paper(req.paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    if paper["status"] not in ("uploaded", "error"):
        raise HTTPException(status_code=409, detail=f"论文当前状态为 {paper['status']}，不能重复处理")

    result = lib.process_paper(req.paper_id)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail=result.get("error", "处理失败"))
    return {
        "paper_id": req.paper_id,
        "status": "ready",
        "chunk_count": result.get("chunk_count", 0),
        "style": result.get("style", {}),
    }


@router.get("")
def list_papers(request: Request):
    """用户论文列表"""
    user = require_user(request)
    return get_user_library(user["id"]).list_papers()


@router.get("/style")
def get_style(request: Request):
    """用户全局风格三件套（术语表/结构模板/few-shot）"""
    user = require_user(request)
    style = get_user_library(user["id"]).global_style()
    if not style:
        # 空库返回 404 让前端提示"先上传论文"
        raise HTTPException(status_code=404, detail="论文库为空，暂无风格数据")
    return style


@router.post("/search")
def search_library(req: SearchRequest, request: Request):
    """在用户自己的论文库中语义检索"""
    user = require_user(request)
    lib = get_user_library(user["id"])
    results = lib.search(req.query, top_k=req.top_k)
    return {"query": req.query, "results": results}


@router.get("/{paper_id}")
def get_paper(paper_id: int, request: Request):
    """单篇论文详情（含状态与错误信息）"""
    user = require_user(request)
    paper = get_user_library(user["id"]).get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, request: Request):
    """删除论文（元数据 + R2 对象 + 向量块）"""
    user = require_user(request)
    ok = get_user_library(user["id"]).delete_paper(paper_id)
    if not ok:
        raise HTTPException(status_code=404, detail="论文不存在")
    return {"ok": True}

# 表结构懒初始化：UserLibrary 构造时会 init_db()（见 src/knowledge/user_library.py），
# 这里不写模块级 init_db()，避免 import 副作用创建 data/library.db