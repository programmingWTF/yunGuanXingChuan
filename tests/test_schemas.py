"""
云观星传 - Schema 单元测试
验证核心数据模型的正确性
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from pydantic import ValidationError
from src.schemas import (
    EvaluationScores, Hypothesis, VerificationResult,
    VerificationStatus, PipelineResult, FrameworkType,
)


class TestEvaluationScores:
    """五维评分 Schema 测试"""

    def test_weighted_total_calculation(self):
        """验证加权总分计算公式正确"""
        scores = EvaluationScores(
            factual_accuracy=100,
            strategic_actionability=100,
            audience_fit=100,
            cultural_sensitivity=100,
            narrative_fluency=100,
        )
        # 全部满分时加权总分应为 100
        assert abs(scores.weighted_total - 100.0) < 0.01

    def test_weighted_total_partial(self):
        """验证部分分数时加权总分正确"""
        scores = EvaluationScores(
            factual_accuracy=80,
            strategic_actionability=70,
            audience_fit=60,
            cultural_sensitivity=90,
            narrative_fluency=50,
        )
        # 80*0.30 + 70*0.25 + 60*0.20 + 90*0.15 + 50*0.10 = 24+17.5+12+13.5+5 = 72
        assert abs(scores.weighted_total - 72.0) < 0.01

    def test_score_range_validation(self):
        """验证分数范围 [0, 100]"""
        with pytest.raises(ValidationError):
            EvaluationScores(
                factual_accuracy=101,  # 超出范围
                strategic_actionability=70,
                audience_fit=70,
                cultural_sensitivity=70,
                narrative_fluency=70,
            )

    def test_score_negative_rejected(self):
        """验证负分被拒绝"""
        with pytest.raises(ValidationError):
            EvaluationScores(
                factual_accuracy=-1,
                strategic_actionability=70,
                audience_fit=70,
                cultural_sensitivity=70,
                narrative_fluency=70,
            )


class TestHypothesis:
    """传播假设 Schema 测试"""

    def test_confidence_range(self, sample_hypotheses):
        """验证 confidence 在 [0,1] 范围内"""
        for h_data in sample_hypotheses:
            h = Hypothesis(**h_data)
            assert 0 <= h.confidence <= 1

    def test_confidence_out_of_range(self):
        """验证超出范围的 confidence 被拒绝"""
        with pytest.raises(ValidationError):
            Hypothesis(
                hypothesis_id="H999",
                statement="测试假设",
                framework="competition",
                target_countries=["美国"],
                evidence_chain=[],
                verification_path="测试",
                confidence=1.5,  # 超出范围
                kg_entities_involved=[],
                falsification_criteria="测试",
            )

    def test_framework_enum(self):
        """验证框架类型枚举"""
        h = Hypothesis(
            hypothesis_id="H001",
            statement="测试",
            framework=FrameworkType.PROGRESS,
            target_countries=["法国"],
            evidence_chain=[],
            verification_path="测试",
            confidence=0.8,
            kg_entities_involved=[],
            falsification_criteria="测试",
        )
        assert h.framework == FrameworkType.PROGRESS


class TestVerificationStatus:
    """校验状态枚举测试"""

    def test_enum_values(self):
        """验证 VerificationStatus 枚举值"""
        assert VerificationStatus.VERIFIED == "verified"
        assert VerificationStatus.PARTIALLY_VERIFIED == "partial"
        assert VerificationStatus.CONFLICTING == "conflicting"
        assert VerificationStatus.UNVERIFIED == "unverified"

    def test_all_statuses_count(self):
        """验证枚举有且仅有 4 个值"""
        assert len(VerificationStatus) == 4


class TestPipelineResult:
    """Pipeline 结果 Schema 测试"""

    def test_minimal_construction(self):
        """验证 PipelineResult 最小构造"""
        result = PipelineResult(
            topic="测试议题",
            timestamp="2026-01-01T00:00:00",
            science_facts={},
            context_analysis={},
            hypotheses=[],
            verification_report=[],
            strategies=[],
            evaluation=EvaluationScores(
                factual_accuracy=70,
                strategic_actionability=70,
                audience_fit=70,
                cultural_sensitivity=70,
                narrative_fluency=70,
            ),
            iteration_feedback=[],
            iteration_count=1,
            final_status="completed",
        )
        assert result.topic == "测试议题"
        assert result.iteration_count == 1
        assert result.search_sources == []  # 默认空列表
