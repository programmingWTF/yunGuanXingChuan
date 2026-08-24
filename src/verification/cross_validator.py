"""
云观星传 - 交叉验证模块
结合 RAG、KG、Wikidata、Wikipedia 四路校验结果进行综合判定

Issue #116 修复：
- Bug 1: 投票判定改为按实际参与路数自适应（不再固定 >=3 才 VERIFIED）
- Bug 2: KG 路仅凭实体存在不再计为 partial 支持，改为 entity_found（参与但不支持）
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.verification.rag_checker import RAGChecker
from src.verification.kg_checker import KGChecker
from src.verification.external_validator import get_external_validator
from src.schemas import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class CrossValidator:
    """交叉验证器：结合 RAG + KG + Wikidata + Wikipedia 四路校验结果"""

    def __init__(self, llm_client=None):
        self.rag_checker = RAGChecker(llm_client=llm_client)
        self.kg_checker = KGChecker()
        self.external_validator = get_external_validator()

    def cross_validate_claim(self, claim: str, entities: Optional[List[str]] = None) -> VerificationResult:
        """
        对单条断言进行四路交叉验证

        自适应判定表（按实际参与路数动态调整阈值，Issue #116 修复）：
        | 参与路数 | 全部支持 | 多数支持(>=半) | 少数支持 | 无支持 |
        |----------|----------|---------------|----------|--------|
        | 3        | VERIFIED | PARTIAL       | UNVERIFIED | UNVERIFIED |
        | 2        | VERIFIED | PARTIAL       | -        | UNVERIFIED |
        | 1        | PARTIAL  | -             | -        | UNVERIFIED |
        | 0        | UNVERIFIED | -           | -        | UNVERIFIED |

        冲突：支持+反对各 >=1 -> CONFLICTING

        KG entity_found：实体在图中存在但断言未验证 -> 计为参与但不计为支持

        Args:
            claim: 待验证的断言
            entities: 相关实体列表（用于 KG 校验）

        Returns:
            VerificationResult
        """
        # 路径 1: RAG 校验
        rag_result = self.rag_checker.verify_claim(claim)
        rag_status = rag_result["status"]
        rag_confidence = rag_result["confidence"]
        rag_evidence = rag_result.get("evidence", "")

        # 路径 2: KG 校验（如果有相关实体）
        # Bug fix (#116): 仅凭实体存在不等于断言被验证
        # entity_found = 实体在图中存在但断言未验证 -> 计为参与但不计为支持
        kg_status = "unverified"
        kg_match = ""
        kg_confidence = 0.0

        if entities:
            try:
                for entity in entities:
                    related = self.kg_checker.get_related_context(entity, depth=1)
                    if related:
                        kg_status = "entity_found"
                        kg_match = f"找到相关实体: {entity}"
                        kg_confidence = 0.3
                        break
            except Exception as e:
                logger.debug(f"[交叉验证] KG 校验异常（已降级）: {e}")

        # 路径 3+4: 外部校验（Wikidata + Wikipedia）
        ext_status = "unverified"
        ext_confidence = 0.0
        ext_evidence = ""
        try:
            ext_result = self.external_validator.validate(claim, entities=entities or [])
            ext_status = ext_result.get("status", "unverified")
            ext_confidence = ext_result.get("confidence", 0.0)
            ext_evidence = ext_result.get("evidence", "")
        except Exception as e:
            logger.debug(f"[交叉验证] 外部校验器异常（已降级）: {e}")

        # 四路投票判定
        final_status, final_confidence = self._four_way_vote(
            rag_status, rag_confidence,
            kg_status, kg_confidence,
            ext_status, ext_confidence,
        )

        # 组装 notes
        notes_parts = [
            f"RAG: {rag_status} ({rag_confidence:.2f})",
            f"KG: {kg_status} ({kg_confidence:.2f})",
            f"External: {ext_status} ({ext_confidence:.2f})",
        ]

        return VerificationResult(
            claim=claim,
            status=final_status,
            rag_evidence=rag_evidence if rag_evidence else None,
            kg_match=kg_match if kg_match else None,
            cross_source_agreement=(
                sum(1 for s in [rag_status, kg_status, ext_status]
                    if s in ["supported", "verified", "partial"]) >= 2
            ),
            confidence=final_confidence,
            notes=" | ".join(notes_parts),
        )

    def _four_way_vote(
        self,
        rag_status: str,
        rag_confidence: float,
        kg_status: str,
        kg_confidence: float,
        ext_status: str,
        ext_confidence: float,
    ) -> tuple:
        """
        自适应投票判定（RAG + KG + Wikidata + Wikipedia）

        按实际参与路数动态调整阈值（Issue #116 修复）：
        - 参与路数 = 给出非 unverified 结果的校验路数
        - entity_found 计为参与但不计为支持
        - 全部参与路支持且 >=2 路 -> VERIFIED
        - 多数(>=半)参与路支持 -> PARTIALLY_VERIFIED
        - 少数支持 -> UNVERIFIED
        - 支持+反对各 >=1 -> CONFLICTING

        Returns:
            (status, confidence) 元组
        """
        # 统计支持/反对
        support_signals = []  # (source, confidence)
        conflict_signals = []

        # RAG
        if rag_status == "supported":
            support_signals.append(("rag", rag_confidence))
        elif rag_status == "conflicting":
            conflict_signals.append(("rag", rag_confidence))

        # KG: verified/partial 计为支持; entity_found 仅参与不支持; conflicting 计为反对
        if kg_status in ["verified", "partial"]:
            support_signals.append(("kg", kg_confidence))
        elif kg_status == "conflicting":
            conflict_signals.append(("kg", kg_confidence))

        # External (Wikidata + Wikipedia 综合)
        if ext_status in ["verified", "partial"]:
            support_signals.append(("external", ext_confidence))
        elif ext_status == "conflicting":
            conflict_signals.append(("external", ext_confidence))

        num_support = len(support_signals)
        num_conflict = len(conflict_signals)

        # 统计实际参与路数（非 unverified 的路；entity_found 计为参与）
        participating = 0
        if rag_status != "unverified":
            participating += 1
        if kg_status not in ("unverified",):
            participating += 1
        if ext_status != "unverified":
            participating += 1

        # 冲突判定：支持+反对各 >=1
        if num_support >= 1 and num_conflict >= 1:
            return VerificationStatus.CONFLICTING, 0.3

        # 无支持
        if num_support == 0:
            max_conf = max(rag_confidence, kg_confidence, ext_confidence)
            return VerificationStatus.UNVERIFIED, max_conf * 0.3

        # 全部参与路都支持
        if num_support == participating:
            if participating >= 2:
                avg_conf = sum(c for _, c in support_signals) / num_support
                return VerificationStatus.VERIFIED, min(0.95, avg_conf + 0.1)
            else:
                _, conf = support_signals[0]
                return VerificationStatus.PARTIALLY_VERIFIED, min(0.7, conf * 0.8)

        # 多数支持（>=半数参与路支持）-> PARTIALLY_VERIFIED
        if num_support >= (participating + 1) // 2:
            avg_conf = sum(c for _, c in support_signals) / num_support
            return VerificationStatus.PARTIALLY_VERIFIED, min(0.8, avg_conf)

        # 少数支持 -> UNVERIFIED
        _, conf = support_signals[0]
        return VerificationStatus.UNVERIFIED, conf * 0.5

    def _determine_status(
        self,
        rag_status: str,
        rag_confidence: float,
        kg_status: str,
        kg_confidence: float,
    ) -> tuple:
        """
        兼容旧版双路判定（保留向后兼容）

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
            try:
                result = self.cross_validate_claim(fact, entities=entities)
                results.append(result)
            except Exception as e:
                logger.warning(f"[校验] 事实校验异常，已跳过: {e}")
                results.append(VerificationResult(
                    claim=fact, status=VerificationStatus.UNVERIFIED,
                    confidence=0.0, notes=f"校验异常: {e}"
                ))

        # 校验关系三元组
        relations = science_facts.get("relations", [])
        for rel in relations:
            try:
                claim = f"{rel.get('subject', '')} {rel.get('predicate', '')} {rel.get('object', '')}"
                rel_entities = [rel.get("subject", ""), rel.get("object", "")]
                result = self.cross_validate_claim(claim, entities=rel_entities)
                results.append(result)
            except Exception as e:
                logger.warning(f"[校验] 关系校验异常，已跳过: {e}")

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
            try:
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
            except Exception as e:
                logger.warning(f"[校验] 假设校验异常，已跳过: {e}")
                results.append(VerificationResult(
                    claim=hyp.get("statement", ""), status=VerificationStatus.UNVERIFIED,
                    confidence=0.0, notes=f"校验异常: {e}"
                ))

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