"""
云观星传 - 交叉验证模块
结合 RAG 和 KG 校验结果进行综合判定
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.verification.rag_checker import RAGChecker
from src.verification.kg_checker import KGChecker
from src.schemas import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class CrossValidator:
    """交叉验证器：结合 RAG + KG 双校验结果"""

    def __init__(self):
        self.rag_checker = RAGChecker()
        self.kg_checker = KGChecker()

    def cross_validate_claim(self, claim: str, entities: Optional[List[str]] = None) -> VerificationResult:
        """
        对单条断言进行交叉验证

        判定表：
        | RAG结果 | KG结果 | 最终判定 | 处理 |
        |---------|--------|----------|------|
        | 支持 | 支持 | VERIFIED | 高置信度通过 |
        | 支持 | 无数据 | PARTIAL | 中置信度 |
        | 无数据 | 支持 | PARTIAL | 中置信度 |
        | 反对 | 反对 | CONFLICTING | 触发修正 |
        | 支持 | 反对 | CONFLICTING | 人工审查标记 |

        Args:
            claim: 待验证的断言
            entities: 相关实体列表（用于 KG 校验）

        Returns:
            VerificationResult
        """
        # RAG 校验
        rag_result = self.rag_checker.verify_claim(claim)
        rag_status = rag_result["status"]
        rag_confidence = rag_result["confidence"]
        rag_evidence = rag_result.get("evidence", "")

        # KG 校验（如果有相关实体）
        kg_status = "unverified"
        kg_match = ""
        kg_confidence = 0.0

        if entities:
            for entity in entities:
                related = self.kg_checker.get_related_context(entity, depth=1)
                if related:
                    kg_status = "partial"
                    kg_match = f"找到相关实体: {entity}"
                    kg_confidence = 0.5
                    break

        # 交叉判定
        final_status, final_confidence = self._determine_status(
            rag_status, rag_confidence, kg_status, kg_confidence
        )

        return VerificationResult(
            claim=claim,
            status=final_status,
            rag_evidence=rag_evidence if rag_evidence else None,
            kg_match=kg_match if kg_match else None,
            cross_source_agreement=(rag_status == "supported" and kg_status in ["verified", "partial"]),
            confidence=final_confidence,
            notes=f"RAG: {rag_status} ({rag_confidence:.2f}), KG: {kg_status} ({kg_confidence:.2f})",
        )

    def _determine_status(
        self,
        rag_status: str,
        rag_confidence: float,
        kg_status: str,
        kg_confidence: float,
    ) -> tuple:
        """
        根据 RAG 和 KG 结果确定最终状态

        Returns:
            (status, confidence) 元组
        """
        # 双方都支持
        if rag_status == "supported" and kg_status in ["verified", "partial"]:
            confidence = min(0.95, (rag_confidence + kg_confidence) / 2 + 0.1)
            return VerificationStatus.VERIFIED, confidence

        # 只有一方支持
        if rag_status == "supported" and kg_status == "unverified":
            return VerificationStatus.PARTIALLY_VERIFIED, rag_confidence * 0.8

        if rag_status in ["partial", "unverified"] and kg_status in ["verified", "partial"]:
            return VerificationStatus.PARTIALLY_VERIFIED, kg_confidence * 0.8

        # 部分支持
        if rag_status == "partial":
            return VerificationStatus.PARTIALLY_VERIFIED, rag_confidence * 0.7

        # 冲突情况
        if rag_status == "conflicting" or kg_status == "conflicting":
            return VerificationStatus.CONFLICTING, 0.3

        # 都无法验证
        return VerificationStatus.UNVERIFIED, max(rag_confidence, kg_confidence) * 0.5

    def validate_science_facts(self, science_facts: Dict) -> List[VerificationResult]:
        """
        校验科学事实数据

        Args:
            science_facts: 科学事实数据

        Returns:
            校验结果列表
        """
        results = []

        # 校验 key_facts
        key_facts = science_facts.get("key_facts", [])
        entities = [e.get("name", "") for e in science_facts.get("entities", [])]

        for fact in key_facts:
            result = self.cross_validate_claim(fact, entities=entities)
            results.append(result)

        # 校验关系三元组
        relations = science_facts.get("relations", [])
        for rel in relations:
            claim = f"{rel.get('subject', '')} {rel.get('predicate', '')} {rel.get('object', '')}"
            rel_entities = [rel.get("subject", ""), rel.get("object", "")]
            result = self.cross_validate_claim(claim, entities=rel_entities)
            results.append(result)

        return results

    def validate_hypotheses(self, hypotheses: List[Dict]) -> List[VerificationResult]:
        """
        校验假设中的证据链

        Args:
            hypotheses: 假设列表

        Returns:
            校验结果列表
        """
        results = []

        for hyp in hypotheses:
            statement = hyp.get("statement", "")
            kg_entities = hyp.get("kg_entities_involved", [])

            # 校验假设陈述
            result = self.cross_validate_claim(statement, entities=kg_entities)
            results.append(result)

            # 校验证据链
            for evidence in hyp.get("evidence_chain", []):
                quote = evidence.get("quote", "")
                if quote:
                    ev_result = self.cross_validate_claim(quote, entities=kg_entities)
                    results.append(ev_result)

        return results

    def get_validation_summary(self, results: List[VerificationResult]) -> Dict:
        """
        获取校验结果摘要

        Args:
            results: 校验结果列表

        Returns:
            摘要字典
        """
        if not results:
            return {"total": 0, "verified": 0, "partial": 0, "conflicting": 0, "unverified": 0}

        verified = sum(1 for r in results if r.status == VerificationStatus.VERIFIED)
        partial = sum(1 for r in results if r.status == VerificationStatus.PARTIALLY_VERIFIED)
        conflicting = sum(1 for r in results if r.status == VerificationStatus.CONFLICTING)
        unverified = sum(1 for r in results if r.status == VerificationStatus.UNVERIFIED)

        return {
            "total": len(results),
            "verified": verified,
            "partial": partial,
            "conflicting": conflicting,
            "unverified": unverified,
            "verification_rate": (verified + partial) / len(results) if results else 0,
            "avg_confidence": sum(r.confidence for r in results) / len(results),
            "needs_attention": conflicting > 0,
        }
