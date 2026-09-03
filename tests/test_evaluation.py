"""
云观星传 - 评测引擎单元测试
验证五维评分计算、通过判定、迭代控制逻辑
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.schemas import EvaluationScores, IterationFeedback
from src.evaluation import EvaluationEngine


class TestWeightedTotal:
    """加权总分计算测试"""

    def test_calculation_correct(self, sample_evaluation_scores):
        """验证 calculate_weighted_total 与 Schema 属性一致"""
        engine = EvaluationEngine()
        total = engine.calculate_weighted_total(sample_evaluation_scores)
        # 85*0.30 + 72*0.25 + 78*0.20 + 80*0.15 + 75*0.10
        # = 25.5 + 18 + 15.6 + 12 + 7.5 = 78.6
        assert abs(total - 78.6) < 0.1

    def test_all_zero(self):
        """全零分时加权和为 0"""
        engine = EvaluationEngine()
        scores = EvaluationScores(
            factual_accuracy=0, strategic_actionability=0,
            audience_fit=0, cultural_sensitivity=0, narrative_fluency=0,
        )
        assert engine.calculate_weighted_total(scores) == 0.0

    def test_all_max(self):
        """全满分时加权和为 100"""
        engine = EvaluationEngine()
        scores = EvaluationScores(
            factual_accuracy=100, strategic_actionability=100,
            audience_fit=100, cultural_sensitivity=100, narrative_fluency=100,
        )
        assert abs(engine.calculate_weighted_total(scores) - 100.0) < 0.01


class TestPassThreshold:
    """通过阈值判定测试"""

    def test_above_threshold_passes(self):
        """75分以上通过"""
        engine = EvaluationEngine(pass_threshold=75)
        scores = EvaluationScores(
            factual_accuracy=80, strategic_actionability=80,
            audience_fit=80, cultural_sensitivity=80, narrative_fluency=80,
        )
        assert engine.check_passed(scores) is True

    def test_below_threshold_fails(self):
        """74分不通过"""
        engine = EvaluationEngine(pass_threshold=75)
        # 构造加权总分 < 75 的评分
        scores = EvaluationScores(
            factual_accuracy=70, strategic_actionability=70,
            audience_fit=70, cultural_sensitivity=70, narrative_fluency=70,
        )
        # 加权总分 = 70（全部相同分数时加权和等于该分数）
        assert engine.check_passed(scores) is False

    def test_exact_threshold_passes(self):
        """恰好等于阈值时通过"""
        engine = EvaluationEngine(pass_threshold=75)
        scores = EvaluationScores(
            factual_accuracy=75, strategic_actionability=75,
            audience_fit=75, cultural_sensitivity=75, narrative_fluency=75,
        )
        assert engine.check_passed(scores) is True


class TestWeakDimensions:
    """低分维度识别测试"""

    def test_identify_low_dimension(self, sample_low_scores):
        """某维度 < 60 应被识别"""
        engine = EvaluationEngine()
        weak = engine.identify_weak_dimensions(sample_low_scores, threshold=60)
        assert "factual_accuracy" in weak  # 55 < 60

    def test_no_weak_dimensions(self, sample_evaluation_scores):
        """所有维度 >= 60 时返回空"""
        engine = EvaluationEngine()
        weak = engine.identify_weak_dimensions(sample_evaluation_scores, threshold=60)
        assert len(weak) == 0

    def test_sorted_by_score(self):
        """低分维度按分数排序（最弱在前）"""
        engine = EvaluationEngine()
        scores = EvaluationScores(
            factual_accuracy=40, strategic_actionability=50,
            audience_fit=55, cultural_sensitivity=80, narrative_fluency=90,
        )
        weak = engine.identify_weak_dimensions(scores, threshold=60)
        assert weak[0] == "factual_accuracy"  # 40 最低
        assert weak[1] == "strategic_actionability"  # 50


class TestIterationControl:
    """迭代控制逻辑测试"""

    def test_max_rounds_stops(self, sample_low_scores):
        """达最大轮次应返回 False"""
        engine = EvaluationEngine(max_rounds=3)
        result = engine.should_continue_iteration(sample_low_scores, current_round=3)
        assert result is False

    def test_passed_stops(self, sample_evaluation_scores):
        """已通过阈值应返回 False"""
        engine = EvaluationEngine(pass_threshold=75)
        result = engine.should_continue_iteration(sample_evaluation_scores, current_round=1)
        assert result is False

    def test_low_score_continues(self, sample_low_scores):
        """未通过且有低分维度应继续"""
        engine = EvaluationEngine(pass_threshold=75, max_rounds=5)
        result = engine.should_continue_iteration(sample_low_scores, current_round=1)
        assert result is True


class TestExperiencePool:
    """经验池测试"""

    def test_experience_accumulates(self, sample_evaluation_scores):
        """多轮后经验池应有对应记录"""
        engine = EvaluationEngine()
        engine.log_experience(1, sample_evaluation_scores, [])
        engine.log_experience(2, sample_evaluation_scores, [])
        assert len(engine.experience_pool) == 2
        assert engine.experience_pool[0]["round"] == 1
        assert engine.experience_pool[1]["round"] == 2

    def test_iteration_summary(self, sample_evaluation_scores, sample_low_scores):
        """迭代总结应包含正确信息"""
        engine = EvaluationEngine()
        engine.log_experience(1, sample_low_scores, [])
        engine.log_experience(2, sample_evaluation_scores, [])
        summary = engine.get_iteration_summary()
        assert summary["total_rounds"] == 2
        assert summary["improvement"] > 0  # 分数应提升


# ══════════════════════════════════════════════════════════════
# 以下为补充测试：反馈生成 / 经验记录 / 历史加载降级 / 全局统计
# ══════════════════════════════════════════════════════════════
import pytest
from unittest.mock import patch, MagicMock
from src.schemas import EvaluationScores, IterationFeedback
from src.evaluation import EvaluationEngine


def _scores(**kw):
    """构造五维评分，缺省用 80"""
    defaults = {"factual_accuracy": 80, "strategic_actionability": 80,
                "audience_fit": 80, "cultural_sensitivity": 80, "narrative_fluency": 80}
    defaults.update(kw)
    return EvaluationScores(**defaults)


class TestGenerateFeedback:
    """迭代反馈生成测试"""

    def test_no_feedback_defaults(self):
        """无评测输出时应基于最低维生成默认反馈"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        scores = _scores(factual_accuracy=50, strategic_actionability=80,
                         audience_fit=80, cultural_sensitivity=80, narrative_fluency=80)
        feedback = eng.generate_feedback(scores, None)
        assert len(feedback) == 1  # 最低维
        assert feedback[0].dimension == "factual_accuracy"
        assert feedback[0].target_agent == "science_agent"
        assert feedback[0].current_score == 50

    def test_feedback_uses_eval_output(self):
        """评测输出的建议应被采纳"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        scores = _scores(audience_fit=45)
        result = {"feedback": [
            {"dimension": "audience_fit", "issue": "受众定位模糊", "suggestion": "细分受众画像"}
        ]}
        feedback = eng.generate_feedback(scores, result)
        target = next(f for f in feedback if f.dimension == "audience_fit")
        assert target.issue == "受众定位模糊"
        assert target.suggestion == "细分受众画像"

    def test_weak_dims_limited_to_two(self):
        """多个低分维度时应只取前 2 个"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        scores = _scores(factual_accuracy=40, strategic_actionability=45,
                         audience_fit=50, cultural_sensitivity=55, narrative_fluency=58)
        feedback = eng.generate_feedback(scores, None)
        assert len(feedback) == 2
        assert feedback[0].dimension == "factual_accuracy"
        assert feedback[1].dimension == "strategic_actionability"

    def test_no_low_dim_takes_min(self):
        """全维度 ≥60 时应取最低分维度"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        scores = _scores(factual_accuracy=70, narrative_fluency=62)  # fluency 最低
        feedback = eng.generate_feedback(scores, None)
        assert len(feedback) == 1
        assert feedback[0].dimension == "narrative_fluency"

    def test_all_dimensions_mapped_to_strategy_except_facts(self):
        """除事实准确度外其余维度都路由到 strategy_agent"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        for dim, agent in [
            ("strategic_actionability", "strategy_agent"),
            ("audience_fit", "strategy_agent"),
            ("cultural_sensitivity", "strategy_agent"),
            ("narrative_fluency", "strategy_agent"),
        ]:
            scores = _scores(**{dim: 40})
            fb = eng.generate_feedback(scores, None)
            assert fb[0].target_agent == agent


class TestShouldContinue:
    """继续迭代判断测试"""

    def test_max_rounds_reached_stops(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        assert eng.should_continue_iteration(_scores(factual_accuracy=30), 3) is False

    def test_passed_stops(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=5)
        assert eng.should_continue_iteration(_scores(factual_accuracy=90), 1) is False

    def test_weak_dim_continues(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=5)
        assert eng.should_continue_iteration(_scores(factual_accuracy=55), 1) is True


class TestLogExperience:
    """经验记录测试"""

    def test_accumulates_and_summary(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=5)
        eng.log_experience(1, _scores(factual_accuracy=60, strategic_actionability=60), [])
        eng.log_experience(2, _scores(factual_accuracy=90), [])
        summary = eng.get_iteration_summary()
        assert summary["total_rounds"] == 2
        assert summary["final_passed"] is True
        # factual 从 60 → 90
        assert summary["dimension_improvement"]["factual_accuracy"] == 30
        assert summary["initial_score"] < summary["final_score"]

    def test_persist_failure_not_fatal(self):
        """SQLite 持久化失败不影响主流程"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        with patch('src.evaluation.get_experience_store', side_effect=RuntimeError("db down")):
            eng.log_experience(1, _scores(), [], topic="嫦娥六号")
        # 内存经验仍在
        assert len(eng.experience_pool) == 1

    def test_no_topic_skips_persist(self):
        """无 topic 时跳过持久化"""
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        with patch('src.evaluation.get_experience_store') as mock_store:
            eng.log_experience(1, _scores(), [], topic="")
        mock_store.assert_not_called()

    def test_empty_summary_message(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        assert eng.get_iteration_summary() == {"message": "没有迭代记录"}


class TestLoadPastExperience:
    """历史经验加载测试"""

    def test_load_success(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        store = MagicMock()
        store.find_similar_topics.return_value = [{"topic": "嫦娥六号", "score": 0.9}]
        store.get_common_weaknesses.return_value = [{"dimension": "narrative"}]
        store.get_improvement_trend.return_value = {"trend": "up"}
        with patch('src.evaluation.get_experience_store', return_value=store):
            result = eng.load_past_experience("嫦娥六号")
        assert result["similar_topics"][0]["topic"] == "嫦娥六号"
        assert result["common_weaknesses"] == [{"dimension": "narrative"}]

    def test_load_failure_degrades(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        with patch('src.evaluation.get_experience_store', side_effect=RuntimeError("db down")):
            result = eng.load_past_experience("议题")
        assert result == {"similar_topics": [], "common_weaknesses": [], "global_insights": {}}

    def test_global_insights_success_and_failure(self):
        eng = EvaluationEngine(pass_threshold=75, max_rounds=3)
        store = MagicMock()
        store.get_improvement_trend.return_value = {"n": 3}
        store.get_common_weaknesses.return_value = []
        with patch('src.evaluation.get_experience_store', return_value=store):
            assert eng.get_global_insights()["trend"] == {"n": 3}
        with patch('src.evaluation.get_experience_store', side_effect=RuntimeError("down")):
            assert eng.get_global_insights() == {"trend": {}, "weaknesses": []}
