"""
云观星传 - 校验报告生成模块
生成结构化的校验报告
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.schemas import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class ReportGenerator:
    """校验报告生成器"""

    def generate_verification_report(
        self,
        results: List[VerificationResult],
        topic: str = "",
        iteration_round: int = 1,
    ) -> Dict:
        """
        生成校验报告

        Args:
            results: 校验结果列表
            topic: 议题名称
            iteration_round: 迭代轮次

        Returns:
            报告字典
        """
        # 统计
        total = len(results)
        verified = sum(1 for r in results if r.status == VerificationStatus.VERIFIED)
        partial = sum(1 for r in results if r.status == VerificationStatus.PARTIALLY_VERIFIED)
        conflicting = sum(1 for r in results if r.status == VerificationStatus.CONFLICTING)
        unverified = sum(1 for r in results if r.status == VerificationStatus.UNVERIFIED)

        # 需要关注的问题
        issues = [r for r in results if r.status in [VerificationStatus.CONFLICTING, VerificationStatus.UNVERIFIED]]

        report = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "iteration_round": iteration_round,
            "summary": {
                "total_claims": total,
                "verified": verified,
                "partially_verified": partial,
                "conflicting": conflicting,
                "unverified": unverified,
                "verification_rate": (verified + partial) / total if total > 0 else 0,
                "avg_confidence": sum(r.confidence for r in results) / total if total > 0 else 0,
            },
            "issues": [
                {
                    "claim": r.claim,
                    "status": r.status.value,
                    "confidence": r.confidence,
                    "notes": r.notes,
                }
                for r in issues
            ],
            "details": [
                {
                    "claim": r.claim,
                    "status": r.status.value,
                    "confidence": r.confidence,
                    "rag_evidence": r.rag_evidence,
                    "kg_match": r.kg_match,
                    "cross_source_agreement": r.cross_source_agreement,
                    "notes": r.notes,
                }
                for r in results
            ],
            "recommendations": self._generate_recommendations(results),
        }

        return report

    def _generate_recommendations(self, results: List[VerificationResult]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        conflicting = [r for r in results if r.status == VerificationStatus.CONFLICTING]
        unverified = [r for r in results if r.status == VerificationStatus.UNVERIFIED]

        if conflicting:
            recommendations.append(
                f"发现 {len(conflicting)} 条冲突断言，需要人工审查或修正"
            )

        if unverified:
            recommendations.append(
                f"发现 {len(unverified)} 条无法验证的断言，建议补充数据源"
            )

        low_confidence = [r for r in results if r.confidence < 0.5]
        if low_confidence:
            recommendations.append(
                f"有 {len(low_confidence)} 条断言置信度较低（<0.5），建议加强证据支撑"
            )

        if not recommendations:
            recommendations.append("所有断言均已通过校验，质量良好")

        return recommendations

    def generate_iteration_comparison(
        self,
        history: List[Dict],
    ) -> Dict:
        """
        生成迭代对比报告

        Args:
            history: 迭代历史列表，每项包含 round 和 scores

        Returns:
            对比报告
        """
        if not history:
            return {"message": "没有迭代历史"}

        comparison = {
            "total_rounds": len(history),
            "rounds": [],
            "improvement": {},
        }

        for i, record in enumerate(history):
            comparison["rounds"].append({
                "round": record.get("round", i + 1),
                "scores": record.get("scores", {}),
                "weighted_total": record.get("weighted_total", 0),
                "passed": record.get("passed", False),
            })

        # 计算改进
        if len(history) >= 2:
            first = history[0].get("scores", {})
            last = history[-1].get("scores", {})

            for dim in first:
                if dim in last:
                    comparison["improvement"][dim] = last[dim] - first[dim]

        return comparison

    def save_report(self, report: Dict, output_path: Optional[Path] = None):
        """保存报告到文件"""
        if output_path is None:
            output_path = Path(__file__).parent.parent.parent / "data" / "kg" / "verification_report.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"校验报告已保存到 {output_path}")
