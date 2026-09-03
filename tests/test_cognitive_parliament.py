"""
云观星传 - 认知议会（CognitiveParliament）编排单元测试
覆盖 convene 主流程（mock 辩论引擎）、最终总结报告生成/降级、
规则式兑底报告与策略整合异常路径
"""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


@pytest.fixture
def parliament():
    """构造带 mock 组件依赖的 CognitiveParliament

    注意：DebateEngine/SpeakerAgent/HumanistAgent 是在 CognitiveParliament.__init__
    方法内部导入的（不在 src.pipeline 模块顶层），patch 需打在源模块上。
    """
    with patch('src.pipeline.ScienceAgent'), \
         patch('src.pipeline.ContextAgent'), \
         patch('src.pipeline.HypothesisAgent'), \
         patch('src.pipeline.StrategyAgent'), \
         patch('src.pipeline.EvaluatorAgent'), \
         patch('src.pipeline.CrossValidator'), \
         patch('src.pipeline.ReportGenerator'), \
         patch('src.pipeline.EvaluationEngine'), \
         patch('src.parliament.debate_engine.DebateEngine') as MockDebate, \
         patch('src.parliament.speaker.SpeakerAgent') as MockSpeaker, \
         patch('src.agents.humanist_agent.HumanistAgent') as MockHumanist:
        from src.pipeline import CognitiveParliament
        p = CognitiveParliament(max_rounds=3, max_pipeline_rounds=1)
        # 用受控 mock 覆盖实例内部依赖
        p.debate_engine = MagicMock()
        p.speaker = MockSpeaker.return_value
        p.strategy_agent = MagicMock()
        yield p


def _motion(mid="M1", content="应发布国际联合科研站声明"):
    m = MagicMock()
    m.motion_id = mid
    m.content = content
    m.model_dump.return_value = {"motion_id": mid, "content": content}
    return m


def _vote(mid="M1", result="passed"):
    v = MagicMock()
    v.motion_id = mid
    v.result = result
    v.agent = "scientist"
    v.stance = "yes"
    v.objection = "暂无"
    v.round = 1
    v.model_dump.return_value = {"motion_id": mid, "result": result}
    return v


class TestConveneFlow:
    """convene 主流程测试"""

    def test_success_flow_with_passed_motions(self, parliament):
        """动议通过时：辩论 → Pipeline 接驳 → 策略整合 → 闭幕"""
        from src.pipeline import CognitiveParliament
        de = parliament.debate_engine
        de.open_parliament.return_value = [_motion("M1", "动议A"), _motion("M2", "动议B")]
        # 首轮有返回 → 第二轮 None 结束辩论
        de.debate_round.side_effect = [MagicMock(topic="第1轮"), None]
        de.should_close.side_effect = [False, True]
        de.motions = [_motion("M1", "动议A")]
        de.votes = [_vote("M1", "passed")]
        de.minority_opinions = []
        de.rounds = []
        transcript_mock = MagicMock()
        de.close_parliament.return_value = transcript_mock

        # 最终总结报告走 mock（不触发 LLM）
        with patch.object(CognitiveParliament, '_generate_final_report', return_value={"one_line_takeaway": "OK"}), \
             patch.object(parliament, '_generate_final_strategies',
                          return_value={"topic": "嫦娥六号", "strategies": []}), \
             patch('src.pipeline.Pipeline') as MockPipeline:
            MockPipeline.return_value.run_with_motions.return_value = {
                "verification_results": [], "strategies": {}, "evaluation": {}, "search_sources": []}
            result = parliament.convene("嫦娥六号", science_facts={}, context_analysis={})

        assert result is transcript_mock
        # Pipeline 接驳发生在动议通过时
        MockPipeline.return_value.run_with_motions.assert_called_once()
        de.close_parliament.assert_called_once()
        transcript_mock.final_report = {"one_line_takeaway": "OK"}  # convene 内会赋值

    def test_stop_request_breaks_early(self, parliament):
        """stop_check 返回 True 时应提前结束辩论"""
        de = parliament.debate_engine
        de.open_parliament.return_value = []
        de.debate_round.return_value = MagicMock()
        calls = {"n": 0}

        def should_close():
            calls["n"] += 1
            return calls["n"] > 5  # 前 5 次 False

        de.should_close.side_effect = should_close
        parliament.stop_check = lambda: True  # 立即停止
        de.motions, de.votes, de.minority_opinions, de.rounds = [], [], [], []
        with patch('src.pipeline.CognitiveParliament._generate_final_report',
                   return_value={}), \
             patch.object(parliament, '_generate_final_strategies',
                          return_value={"strategies": []}), \
             patch.object(parliament.debate_engine, 'close_parliament',
                          return_value=MagicMock(final_strategies=None, total_rounds=0,
                                                 votes=[], motions=[], minority_opinions=[])):
            parliament.convene("议题")

        # 收到停止后 debate_round 不应被调用
        assert de.debate_round.call_count == 0


class TestGenerateFinalReport:
    """最终总结报告测试"""

    def test_llm_success_with_field_defaults(self, parliament):
        """LLM 返回合法报告时应补齐默认字段"""
        transcript = MagicMock()
        transcript.final_strategies = {"pipeline_strategies": {"strategies": []}}
        transcript.motions = [_motion("M1", "内容")]
        transcript.votes = [_vote("M1", "passed")]
        transcript.minority_opinions = []
        transcript.total_rounds = 2

        parliament.speaker.llm_client.chat_json.return_value = {
            "core_conclusion": "结论正文",
            "top_strategies": [{"rank": 1}, {"rank": 2}, {"rank": 3}, {"rank": 4}],  # 超 3 条应截断
        }
        report = parliament._generate_final_report("嫦娥六号", transcript)
        assert report["core_conclusion"] == "结论正文"
        assert report["one_line_takeaway"] == ""
        assert len(report["top_strategies"]) == 3  # 截断
        assert report["risk_warnings"] == []
        assert report["audience_recommendations"] == []

    def test_llm_failure_falls_back(self, parliament):
        """LLM 异常/结构非法时应回退规则式报告"""
        from src.pipeline import build_fallback_final_report
        transcript = MagicMock()
        transcript.final_strategies = None
        transcript.motions = [_motion("M1", "动议内容")]
        transcript.votes = [_vote("M1", "passed")]
        transcript.minority_opinions = []
        transcript.total_rounds = 3
        parliament.speaker.llm_client.chat_json.side_effect = RuntimeError("LLM down")
        with patch('src.pipeline.build_fallback_final_report', wraps=build_fallback_final_report) as mock_fb:
            report = parliament._generate_final_report("嫦娥六号", transcript)
        mock_fb.assert_called_once()
        assert report["generated_by"] == "fallback"
        assert "3 轮" in report["core_conclusion"]

    def test_invalid_report_structure_falls_back(self, parliament):
        """LLM 返回非 dict 或缺核心字段应回退"""
        transcript = MagicMock()
        transcript.final_strategies = {}
        transcript.motions, transcript.votes = [], []
        transcript.minority_opinions = []
        transcript.total_rounds = 0
        parliament.speaker.llm_client.chat_json.return_value = []  # 非 dict
        report = parliament._generate_final_report("议题", transcript)
        assert report["generated_by"] == "fallback"


class TestGenerateFinalStrategies:
    """策略整合测试"""

    def test_success(self, parliament):
        parliament.strategy_agent.run.return_value = {"topic": "T", "strategies": [{"id": "S1"}]}
        parliament.debate_engine.motions = [_motion("M1", "内容")]
        parliament.debate_engine.votes = [_vote("M1", "passed")]
        result = parliament._generate_final_strategies("议题")
        assert len(result["strategies"]) == 1

    def test_exception_returns_note(self, parliament):
        parliament.strategy_agent.run.side_effect = RuntimeError("strategy down")
        parliament.debate_engine.motions = [_motion("M1", "内容")]
        parliament.debate_engine.votes = [_vote("M1", "passed")]
        result = parliament._generate_final_strategies("议题")
        assert result["strategies"] == []
        assert "策略生成异常" in result["note"]
        assert "内容" in result["passed_motions"]


class TestFallbackFinalReport:
    """规则式兑底报告测试"""

    def test_full_report(self):
        from src.pipeline import build_fallback_final_report
        report = build_fallback_final_report(
            topic="嫦娥六号",
            passed_motions=["动议A", "动议B"],
            minority_opinions=["风险：地缘政治敏感"],
            strategies=[{
                "target_audience": "美国政策精英",
                "narrative_angle": "国际合作叙事",
                "key_messages": ["开放共享", "科学无国界"],
                "channel_recommendations": ["科技媒体", "智库报告"],
            }],
            evaluation={"factual_accuracy": 85, "strategic_actionability": 78},
            total_rounds=3,
        )
        assert report["generated_by"] == "fallback"
        assert "3 轮" in report["core_conclusion"]
        assert len(report["top_strategies"]) == 1
        assert report["top_strategies"][0]["audience"] == "美国政策精英"
        assert report["audience_recommendations"][0]["suggestion"] == "科技媒体"
        assert report["risk_warnings"] == ["风险：地缘政治敏感"]
        # 均分 = (85+78)/2 = 81.5
        assert "81.5" in report["core_conclusion"]

    def test_no_passed_motions(self):
        from src.pipeline import build_fallback_final_report
        report = build_fallback_final_report(
            topic="新议题", passed_motions=[], minority_opinions=[],
            strategies=[], evaluation={}, total_rounds=2)
        assert "未形成通过动议" in report["core_conclusion"]
        assert report["risk_warnings"] == ["暂无显著风险信号，建议持续监测舆情变化"]
        assert report["one_line_takeaway"].startswith("新议题")

    def test_malformed_strategies_skipped(self):
        from src.pipeline import build_fallback_final_report
        report = build_fallback_final_report(
            topic="T", passed_motions=["M"], minority_opinions=[],
            strategies=["不是字典", {"target_audience": "公众", "narrative_angle": "科普"}],
            evaluation={}, total_rounds=1)
        # 非 dict 策略跳过；顶层 audience_recs 不应重复同一受众
        assert len(report["top_strategies"]) == 1
        assert len(report["audience_recommendations"]) == 1
