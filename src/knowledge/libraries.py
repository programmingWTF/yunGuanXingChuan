"""
知识库四库化（Issue #49）

对应《智能体.docx》中 7 个智能体依赖的四类知识库：
- journal_article     文献库（①选题孵化 / ②文献综述）
- theory              理论库（①选题孵化 / ②文献综述）
- top_journal_example 顶刊论文库·范文库（③研究设计 / ④方法顾问 / ⑥论文写手 / ⑦评审模拟）
- method              方法库（④方法顾问 / ⑤数据分析）

设计：复用单一 FAISS 索引（vector_store），通过 metadata["library"] 路由；
分库检索 = 检索候选池 + library 过滤（vector_store.search(library=...)）。
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge.vector_store import get_vector_store

logger = logging.getLogger(__name__)

# 数据目录：data/libraries/{library}/**/*.md（可 git 跟踪的种子数据）
LIBRARIES_DIR = Path(__file__).parent.parent.parent / "data" / "libraries"

# 四库定义（key / 中文名 / 描述 / 服务阶段）
LIBRARY_TYPES: Dict[str, Dict] = {
    "journal_article": {
        "name": "文献库",
        "description": "期刊论文、会议论文与学术资料（选题孵化、文献综述）",
        "stages": [1, 2],
    },
    "theory": {
        "name": "理论库",
        "description": "传播学/社会学理论（框架理论、议程设置、沉默螺旋等）",
        "stages": [1, 2],
    },
    "top_journal_example": {
        "name": "顶刊论文库（范文库）",
        "description": "顶刊论文范文（研究问题范式、写作风格、评审标准参考）",
        "stages": [3, 4, 6, 7],
    },
    "method": {
        "name": "方法库",
        "description": "研究方法操作指南（内容分析、框架分析、扎根理论等）",
        "stages": [4, 5],
    },
}

VALID_LIBRARIES = set(LIBRARY_TYPES.keys())


def is_valid_library(library: str) -> bool:
    """校验库名合法性（防任意路径/字段注入）"""
    return library in VALID_LIBRARIES


def get_library_meta_list() -> list:
    """四库元数据列表（前端知识库管理/检索页渲染）"""
    return [
        {"key": k, "name": v["name"], "description": v["description"], "stages": v["stages"]}
        for k, v in LIBRARY_TYPES.items()
    ]


def get_library_documents(library: str) -> List[Dict]:
    """读取指定库的种子文档（data/libraries/{library}/**/*.md），带 library 元数据"""
    if not is_valid_library(library):
        return []
    lib_dir = LIBRARIES_DIR / library
    if not lib_dir.exists():
        return []
    documents = []
    for path in sorted(lib_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".md", ".txt"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[libraries] 跳过 {path.name}: {e}")
            continue
        if not text.strip():
            continue
        documents.append({
            "text": text,
            "source": str(path.relative_to(lib_dir)),
            "title": path.stem,
            "type": "library",
            "library": library,
        })
    return documents


def build_library_index(library: str, preserve_existing: bool = True) -> int:
    """
    构建指定库的索引（并入现有索引，不覆盖其他库）。

    说明：单索引架构下，build_index(documents) 只索引传入文档；
    为保证其他库不丢，合并现有 documents 后重建。
    返回该库入库块数。
    """
    if not is_valid_library(library):
        raise ValueError(f"非法库名: {library}（可选 {sorted(VALID_LIBRARIES)}）")
    docs = get_library_documents(library)
    if not docs:
        logger.warning(f"[libraries] 库 {library} 无种子文档")
        return 0

    vs = get_vector_store()
    existing = list(vs.documents) if preserve_existing else []
    if preserve_existing and not existing:
        # 新进程单例初始为空：先从磁盘加载现有索引（含 science_fact / media_report
        # / entity 等非四库文档），避免增量入库时把其他类型文档覆盖丢失。
        try:
            vs._load_index()
            existing = list(vs.documents)
        except Exception as e:
            logger.warning(f"[libraries] 加载现有索引失败（将只入库本库）: {e}")
    # 合并：已有块（去重，避免重复入库同源） + 新库文档
    seen = set()
    merged_documents = []
    for chunk in existing:
        key = (chunk.get("metadata", {}).get("source", ""), chunk.get("text", "")[:50])
        if key in seen:
            continue
        seen.add(key)
        merged_documents.append({
            "text": chunk["text"],
            "source": chunk.get("metadata", {}).get("source", ""),
            "title": chunk.get("metadata", {}).get("title", ""),
            "date": chunk.get("metadata", {}).get("date", ""),
            "type": chunk.get("metadata", {}).get("type", ""),
            "library": chunk.get("metadata", {}).get("library", ""),
        })
    merged_documents.extend(docs)

    vs.build_index(merged_documents)
    count = len(docs)
    logger.info(f"[libraries] 库 {library} 入库 {count} 个文档块（索引总量 {vs.index.ntotal if vs.index else 0}）")
    return count


def search_library(query: str, library: str, top_k: int = 5) -> List[Dict]:
    """分库语义检索（校验库名；命中为空时降级提示）"""
    if not is_valid_library(library):
        raise ValueError(f"非法库名: {library}（可选 {sorted(VALID_LIBRARIES)}）")
    vs = get_vector_store()
    return vs.search(query, top_k=top_k, library=library)


def get_library_stats() -> List[Dict]:
    """四库状态统计（文档数/入库块数，供前端知识库页）"""
    stats = []
    vs = get_vector_store()
    # 确保索引与元数据已从磁盘加载（新进程单例为空）
    if not vs.documents:
        try:
            vs._load_index()
        except Exception:
            pass
    for key, meta in LIBRARY_TYPES.items():
        lib_dir = LIBRARIES_DIR / key
        file_count = len([p for p in lib_dir.rglob("*") if p.is_file()]) if lib_dir.exists() else 0
        chunk_count = sum(
            1 for d in vs.documents
            if d.get("metadata", {}).get("library") == key
        )
        stats.append({
            "key": key,
            "name": meta["name"],
            "description": meta["description"],
            "stages": meta["stages"],
            "file_count": file_count,
            "chunk_count": chunk_count,
        })
    return stats
