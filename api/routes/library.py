"""
云观星传 - 个人论文库 API（/api/library/*）

上传链路（本地直传，走 upload3.liguiyu.com:10443 直连入口，不经过 CF 代理）：
  1. POST /upload  → 前端 multipart 直传后端 → 本地落盘 data/user_libraries/{user_id}/files/
                    → 建论文记录 → 同步解析/嵌入/风格提取（ready / error）

鉴权：require_user（Cookie 会话；跨域直传时支持 Authorization: Bearer <token>）。
数据严格按 user_id 隔离：文件按 {user_id}/ 分目录，SQLite 记录带 user_id 列。
"""
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field

from api.auth import require_user
from src.knowledge.user_library import (
    SUPPORTED_EXTENSIONS,
    UserLibrary,
    delete_upload,
    file_key_for,
    get_user_library,
    init_db,
    save_upload,
)

router = APIRouter()

MAX_FILE_NAME = 255
# 单文件上限 50MB（前端提示一致；本地磁盘存储，防止打爆 volume）
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)


def _validate_ext(file_name: str) -> str:
    """校验扩展名并返回小写 ext（含点）"""
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext or '(无扩展名)'}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    return ext


@router.get("/health")
def library_health():
    """存储模式状态（前端可用来提示）"""
    init_db()  # 幂等，首次访问建表（避免 import 副作用）
    return {"storage": "local", "supported_extensions": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/upload")
async def upload_paper(request: Request, file: UploadFile = File(...)):
    """① 上传论文（multipart）→ 落盘本地 → 解析/嵌入/风格提取（同步返回处理结果）"""
    user = require_user(request)
    file_name = (file.filename or "").strip()[:MAX_FILE_NAME]
    if not file_name:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    ext = _validate_ext(file_name)
    title = Path(file_name).stem[:200] or "未命名"

    # 读取并校验大小（流式读，超限即中断）
    chunks: List[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"文件超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 上限")
            chunks.append(chunk)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"读取上传内容失败: {e}") from e

    content = b"".join(chunks)
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    lib = get_user_library(user["id"])
    file_key = file_key_for(user["id"], file_name)
    paper_id = lib.create_paper(title=title, file_key=file_key, file_name=file_name, file_ext=ext)

    try:
        save_upload(file_key, content)
    except Exception as e:  # noqa: BLE001
        lib.delete_paper(paper_id)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}") from e

    # 同步处理：解析 → 分块嵌入 → 风格提取
    result = lib.process_paper(paper_id)
    if not result["ok"]:
        # 处理失败：保留记录（status=error）供前端展示原因，文件保留便于排查
        raise HTTPException(status_code=422, detail=result.get("error", "处理失败"))
    return {
        "paper_id": paper_id,
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
    """删除论文（元数据 + 本地文件 + 向量块）"""
    user = require_user(request)
    ok = get_user_library(user["id"]).delete_paper(paper_id)
    if not ok:
        raise HTTPException(status_code=404, detail="论文不存在")
    return {"ok": True}

# 表结构懒初始化：UserLibrary 构造时会 init_db()（见 src/knowledge/user_library.py），
# 这里不写模块级 init_db()，避免 import 副作用创建 data/library.db
