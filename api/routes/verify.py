"""
校验路由 - 事实校验和报告
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from src.verification.cross_validator import CrossValidator
from src.verification.report_generator import ReportGenerator

router = APIRouter()


class VerifyClaimRequest(BaseModel):
    claim: str
    entities: Optional[List[str]] = None


class VerifyBatchRequest(BaseModel):
    claims: List[str]


@router.post("/claim")
async def verify_claim(request: VerifyClaimRequest):
    """校验单条断言"""
    validator = CrossValidator()
    result = validator.cross_validate_claim(request.claim, entities=request.entities)
    return result.model_dump()


@router.post("/batch")
async def verify_batch(request: VerifyBatchRequest):
    """批量校验断言"""
    validator = CrossValidator()
    results = []
    for claim in request.claims:
        result = validator.cross_validate_claim(claim)
        results.append(result.model_dump())

    # 生成摘要
    from src.schemas import VerificationResult
    parsed_results = [VerificationResult(**r) for r in results]
    summary = validator.get_validation_summary(parsed_results)

    return {"results": results, "summary": summary}


@router.get("/report")
async def get_verification_report():
    """获取校验报告"""
    # 从文件加载或返回空报告
    report_path = Path(__file__).parent.parent.parent / "data" / "kg" / "verification_report.json"
    if report_path.exists():
        import json
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"message": "暂无校验报告，请先运行分析任务"}


@router.get("/status")
async def get_verification_status():
    """获取校验系统状态"""
    from src.knowledge.vector_store import get_vector_store
    from src.knowledge.kg_builder import get_knowledge_graph

    vs = get_vector_store()
    kg = get_knowledge_graph()

    return {
        "vector_store": {
            "initialized": vs.index is not None,
            "vector_count": vs.index.ntotal if vs.index else 0,
        },
        "knowledge_graph": {
            "initialized": kg.G.number_of_nodes() > 0,
            "entity_count": kg.G.number_of_nodes(),
            "relation_count": kg.G.number_of_edges(),
        },
    }
