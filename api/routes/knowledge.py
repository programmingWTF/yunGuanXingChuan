"""
知识库路由 - 四库分库检索

端点（/api/knowledge/*）：
- GET /libraries                    四库元数据与状态统计
- GET /search?library=&q=&top_k=    分库语义检索
- POST /seed                        触发种子数据入库（方法库/范文库等）
"""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Query

from src.knowledge.libraries import (
    LIBRARY_TYPES,
    is_valid_library,
    get_library_meta_list,
    search_library,
    get_library_stats,
    build_library_index,
)

router = APIRouter()


@router.get("/libraries")
def get_libraries():
    """四库元数据与状态统计"""
    return {"libraries": get_library_meta_list(), "stats": get_library_stats()}


@router.get("/search")
def search(
    library: str = Query(..., description="知识库名（journal_article/theory/top_journal_example/method）"),
    q: str = Query(..., description="查询关键词"),
    top_k: int = Query(5, ge=1, le=20),
):
    """分库语义检索（向量相似度）"""
    if not q.strip():
        raise HTTPException(status_code=400, detail="查询关键词不能为空")
    if not is_valid_library(library):
        raise HTTPException(status_code=400, detail=f"非法库名: {library}")
    try:
        results = search_library(q, library, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {e}")
    return {"library": library, "query": q, "count": len(results), "results": results}


@router.post("/seed")
def seed(library: Optional[str] = None):
    """触发种子数据入库（四库或指定库）"""
    if library is not None and not is_valid_library(library):
        raise HTTPException(status_code=400, detail=f"非法库名: {library}")
    libs = [library] if library else sorted(LIBRARY_TYPES.keys())
    summary = {}
    for lib in libs:
        try:
            summary[lib] = build_library_index(lib)
        except Exception as e:
            summary[lib] = f"失败: {e}"
    return {"seeded": summary}
