"""
云观星传 - Pipeline 编排逻辑单元测试
验证 Pipeline 结果构建、迭代控制（Mock LLM，不依赖网络）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def mock_pipeline():
    """创建带完整 Mock 的 Pipeline 实例"""
    with patch('src.pipeline.ScienceAgent') as MockSci, \
         patch('src.pipeline.ContextAgent') as MockCtx, \
         patch('src.pipeline.HypothesisAgent') as MockHyp, \
         patch('src.pipeline.StrategyAgent') as MockStr, \
         patch('src.pipeline.EvaluatorAgent') as MockEval, \
         patch('src.pipeline.CrossValidator') as MockCV, \
         patch('src.pipeline.ReportGenerator') as MockRG, \
         patch('src.pipeline.EvaluationEngine') as MockEE, \
         patch('src.pipeline.get_unified_search_service') as MockSearch:

        # 配置搜索 mock
        mock_search = MockSearch.return_value
        mock_search.search_for_topic.return_value = []
        mock_search.format_search_context.return_value = ""

        # 配置评测引擎 mock
        mock_ee = MockEE.return_value
        mock_ee.calculate_weighted_total.return_value = 78.6
        mock_ee.generate_feedback.return_value = []

        from src.pipeline import Pipeline
        pipeline = Pipeline(max_iterations=2, pass_threshold=75)
        yield pipeline


class TestBuildResult:
    """_build_result 结果构建测试"""

    def test_minimal_result(self, mock_pipeline):
        """最小结果构建"""
        from src.schemas import EvaluationScores
        result = mock_pipeline._build_result(
            topic="嫦娥六号",
            science_facts={"topic": "嫦娥六号", "key_facts": ["事实1"]},
            context_analysis={"topic": "嫦娥六号"},
            hypotheses=[],
            verification_results=[],
            strategies=[],
            evaluation_scores=EvaluationScores(
                factual_accuracy=80, strategic_actionability=75,
                audience_fit=78, cultural_sensitivity=82, narrative_fluency=76,
            ),
            iteration_feedback=[],
            iteration_count=1,
            final_status="completed",
        )
        assert result.topic == "嫦娥六号"
        assert result.iteration_count == 1
        assert result.final_status == "completed"
        assert result.evaluation.factual_accuracy == 80

    def test_result_with_hypotheses(self, mock_pipeline, sample_hypotheses):
        """包含假设的结果"""
        from src.schemas import EvaluationScores
        result = mock_pipeline._build_result(
            topic="测试",
            science_facts={},
            context_analysis={},
            hypotheses=sample_hypotheses,
            verification_results=[],
            strategies=[],
            evaluation_scores=EvaluationScores(
                factual_accuracy=70, strategic_actionability=70,
                audience_fit=70, cultural_sensitivity=70, narrative_fluency=70,
            ),
            iteration_feedback=[],
            iteration_count=1,
            final_status="completed",
        )
        assert len(result.hypotheses) == 2
        assert result.hypotheses[0].hypothesis_id == "H001"

    def test_result_with_search_sources(self, mock_pipeline):
        """包含搜索来源的结果"""
        from src.schemas import EvaluationScores
        sources = [
            {"url": "https://example.com", "title": "测试", "content": "内容", "score": 0.9, "source": "TavilySearch"}
        ]
        result = mock_pipeline._build_result(
            topic="测试",
            science_facts={},
            context_analysis={},
            hypotheses=[],
            verification_results=[],
            strategies=[],
            evaluation_scores=EvaluationScores(
                factual_accuracy=70, strategic_actionability=70,
                audience_fit=70, cultural_sensitivity=70, narrative_fluency=70,
            ),
            iteration_feedback=[],
            iteration_count=1,
            final_status="completed",
            search_sources=sources,
        )
        assert len(result.search_sources) == 1
        assert result.search_sources[0]["url"] == "https://example.com"

    def test_error_result(self, mock_pipeline):
        """错误结果构建"""
        result = mock_pipeline._build_error_result("测试议题", "LLM 调用超时")
        assert "error" in result.final_status
        assert result.iteration_count == 0
        assert result.evaluation.factual_accuracy == 0


class TestRunWithMotions:
    """run_with_motions 议会接驳测试"""

    def test_returns_search_sources(self, mock_pipeline):
        """返回值应包含 search_sources 字段"""
        from src.schemas import VerificationResult, VerificationStatus

        # Mock 校验层
        mock_pipeline.cross_validator.validate_science_facts.return_value = []
        mock_pipeline.cross_validator.validate_hypotheses.return_value = []
        mock_pipeline.report_generator.generate_verification_report.return_value = {}

        # Mock 策略 agent
        mock_pipeline.strategy_agent.run_with_tools.return_value = {
            "topic": "测试", "strategies": [{"strategy_id": "S001"}]
        }
        mock_pipeline.strategy_agent.run.return_value = {
            "topic": "测试", "strategies": [{"strategy_id": "S001"}]
        }

        # Mock 评测 agent
        mock_pipeline.evaluator_agent.run_with_tools.return_value = {
            "scores": {"factual_accuracy": 80, "strategic_actionability": 80,
                       "audience_fit": 80, "cultural_sensitivity": 80, "narrative_fluency": 80},
            "weighted_total": 80, "passed": True, "feedback": []
        }
        mock_pipeline.evaluator_agent.run.return_value = {
            "scores": {"factual_accuracy": 80, "strategic_actionability": 80,
                       "audience_fit": 80, "cultural_sensitivity": 80, "narrative_fluency": 80},
            "weighted_total": 80, "passed": True, "feedback": []
        }

        motions = [{"motion_id": "M1", "content": "测试动议", "supporting_evidence": [], "confidence": 0.8}]

        with patch('src.pipeline.ENABLE_AGENT_TOOLS', False):
            result = mock_pipeline.run_with_motions(
                topic="测试",
                motions=motions,
                minority_opinions=[],
                debate_transcript=[],
            )

        assert "search_sources" in result
        assert "verification_results" in result
        assert "strategies" in result
        assert "evaluation" in result

    def test_empty_motions(self, mock_pipeline):
        """空动议列表"""
        mock_pipeline.cross_validator.validate_science_facts.return_value = []
        mock_pipeline.cross_validator.validate_hypotheses.return_value = []
        mock_pipeline.report_generator.generate_verification_report.return_value = {}
        mock_pipeline.strategy_agent.run.return_value = {"topic": "测试", "strategies": []}
        mock_pipeline.evaluator_agent.run.return_value = {
            "scores": {"factual_accuracy": 70, "strategic_actionability": 70,
                       "audience_fit": 70, "cultural_sensitivity": 70, "narrative_fluency": 70},
            "weighted_total": 70, "passed": False, "feedback": []
        }

        with patch('src.pipeline.ENABLE_AGENT_TOOLS', False):
            result = mock_pipeline.run_with_motions(
                topic="测试", motions=[], minority_opinions=[], debate_transcript=[],
            )
        assert result["strategies"] is not None


class TestProgressCallback:
    """进度回调测试"""

    def test_callback_invoked(self):
        """进度回调应被调用"""
        calls = []

        def callback(step, status, message="", *args):
            calls.append((step, status, message))

        with patch('src.pipeline.ScienceAgent'), \
             patch('src.pipeline.ContextAgent'), \
             patch('src.pipeline.HypothesisAgent'), \
             patch('src.pipeline.StrategyAgent'), \
             patch('src.pipeline.EvaluatorAgent'), \
             patch('src.pipeline.CrossValidator'), \
             patch('src.pipeline.ReportGenerator'), \
             patch('src.pipeline.EvaluationEngine'), \
             patch('src.pipeline.get_unified_search_service') as MockSearch:

            mock_search = MockSearch.return_value
            mock_search.search_for_topic.return_value = []
            mock_search.format_search_context.return_value = ""

            from src.pipeline import Pipeline
            pipeline = Pipeline(progress_callback=callback)
            pipeline._report("test_step", "running", "测试消息")

        assert len(calls) == 1
        assert calls[0] == ("test_step", "running", "测试消息")

    def test_no_callback_no_error(self):
        """无回调时不报错"""
        with patch('src.pipeline.ScienceAgent'), \
             patch('src.pipeline.ContextAgent'), \
             patch('src.pipeline.HypothesisAgent'), \
             patch('src.pipeline.StrategyAgent'), \
             patch('src.pipeline.EvaluatorAgent'), \
             patch('src.pipeline.CrossValidator'), \
             patch('src.pipeline.ReportGenerator'), \
             patch('src.pipeline.EvaluationEngine'), \
             patch('src.pipeline.get_unified_search_service'):

            from src.pipeline import Pipeline
            pipeline = Pipeline(progress_callback=None)
            # 不应抛异常
            pipeline._report("test", "completed", "ok")
