"""
云观星传 - 辩论引擎单元测试
验证投票逻辑、闭幕判定、文本相似度、开幕动议生成（Mock Agent，不依赖 LLM）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, MagicMock

# Mock 重型依赖
for mod_name in ['faiss', 'httpx']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


class TestTextSimilarity:
    """_text_similarity 文本相似度函数"""

    def test_identical_strings(self):
        """完全相同的字符串相似度为 1"""
        from src.parliament.debate_engine import _text_similarity
        assert _text_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        """完全不同的字符串相似度为 0"""
        from src.parliament.debate_engine import _text_similarity
        result = _text_similarity("aaaa", "bbbb")
        assert result == 0.0

    def test_partial_overlap(self):
        """部分重叠的字符串相似度在 0~1 之间"""
        from src.parliament.debate_engine import _text_similarity
        result = _text_similarity("嫦娥六号发射成功", "嫦娥六号返回地球")
        assert 0.0 < result < 1.0

    def test_empty_string(self):
        """空字符串返回 0"""
        from src.parliament.debate_engine import _text_similarity
        assert _text_similarity("", "hello") == 0.0
        assert _text_similarity("hello", "") == 0.0
        assert _text_similarity("", "") == 0.0

    def test_single_char(self):
        """单字符（无 bigram）返回 0"""
        from src.parliament.debate_engine import _text_similarity
        assert _text_similarity("a", "a") == 0.0


class TestDebateEngineOpen:
    """DebateEngine.open_parliament 开幕逻辑"""

    @pytest.fixture
    def engine(self):
        """创建带 Mock Agent 的辩论引擎"""
        from src.parliament.debate_engine import DebateEngine
        mock_speaker = MagicMock()
        agents = {
            "scientist": MagicMock(),
            "humanist": MagicMock(),
            "skeptic": MagicMock(),
            "strategist": MagicMock(),
            "evaluator": MagicMock(),
        }
        return DebateEngine(speaker=mock_speaker, agents=agents, max_rounds=5)

    def test_open_with_agent_motions(self, engine):
        """Agent 正常返回动议时，应生成对应数量的动议"""
        engine.agents["scientist"].run.return_value = {
            "motions": [
                {"motion_id": "M_S001", "motion_type": "fact_claim",
                 "content": "嫦娥六号首次月背采样", "confidence": 0.9},
                {"motion_id": "M_S002", "motion_type": "fact_claim",
                 "content": "长征五号运载火箭发射", "confidence": 0.85},
            ]
        }
        engine.agents["humanist"].run.return_value = {
            "motions": [
                {"motion_id": "M_H001", "motion_type": "hypothesis",
                 "content": "月背采样具有重大国际传播价值", "confidence": 0.7},
            ]
        }

        motions = engine.open_parliament("嫦娥六号")
        assert len(motions) == 3
        assert motions[0].proposer == "scientist"
        assert motions[2].proposer == "humanist"
        assert engine.topic == "嫦娥六号"

    def test_open_with_failed_agents_creates_defaults(self, engine):
        """Agent 全部失败时应生成默认动议"""
        engine.agents["scientist"].run.side_effect = Exception("API Error")
        engine.agents["humanist"].run.side_effect = Exception("API Error")

        motions = engine.open_parliament("测试议题")
        assert len(motions) == 2
        assert "测试议题" in motions[0].content
        assert motions[0].motion_id == "M001"

    def test_open_limits_scientist_to_3(self, engine):
        """Scientist 最多取 3 条动议"""
        engine.agents["scientist"].run.return_value = {
            "motions": [
                {"content": f"动议{i}", "motion_type": "fact_claim"}
                for i in range(5)
            ]
        }
        engine.agents["humanist"].run.return_value = {"motions": []}

        motions = engine.open_parliament("议题")
        sci_motions = [m for m in motions if m.proposer == "scientist"]
        assert len(sci_motions) == 3


class TestDebateEngineVote:
    """DebateEngine.vote_on_motion 投票逻辑"""

    @pytest.fixture
    def engine(self):
        """创建带 Mock Agent 的辩论引擎"""
        from src.parliament.debate_engine import DebateEngine
        mock_speaker = MagicMock()
        mock_speaker.rule_deadlock.return_value = {
            "ruling": "amended",
            "ruling_rationale": "议长裁定：修正后通过",
        }
        agents = {
            "scientist": MagicMock(),
            "humanist": MagicMock(),
            "skeptic": MagicMock(),
            "strategist": MagicMock(),
            "evaluator": MagicMock(),
        }
        return DebateEngine(speaker=mock_speaker, agents=agents, max_rounds=5)

    def _make_motion(self):
        from src.schemas import Motion, MotionType
        return Motion(
            motion_id="M_TEST",
            motion_type=MotionType.FACT_CLAIM,
            proposer="scientist",
            content="测试动议",
            confidence=0.8,
        )

    def test_unanimous_yes_passes(self, engine):
        """全票赞成 → passed"""
        for agent in engine.agents.values():
            agent.run.return_value = {"vote": "yes", "reason": "同意"}

        motion = self._make_motion()
        weights = {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1,
                   "strategist": 0.1, "evaluator": 0.15}
        result = engine.vote_on_motion(motion, weights)

        assert result.result == "passed"
        assert result.weighted_yes == pytest.approx(1.0)
        assert result.weighted_no == pytest.approx(0.0)

    def test_majority_no_rejects(self, engine):
        """多数反对 → rejected"""
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": "同意"}
        engine.agents["humanist"].run.return_value = {"vote": "no", "reason": "反对"}
        engine.agents["skeptic"].run.return_value = {"vote": "no", "reason": "质疑"}
        engine.agents["strategist"].run.return_value = {"vote": "no", "reason": "不可行"}
        engine.agents["evaluator"].run.return_value = {"vote": "no", "reason": "评分低"}

        motion = self._make_motion()
        weights = {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1,
                   "strategist": 0.1, "evaluator": 0.15}
        result = engine.vote_on_motion(motion, weights)

        assert result.result == "rejected"
        assert result.weighted_no > result.weighted_yes

    def test_deadlock_triggers_speaker_ruling(self, engine):
        """票差 < deadlock_threshold → 议长裁定"""
        # 设置接近的投票结果
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["skeptic"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["humanist"].run.return_value = {"vote": "no", "reason": ""}
        engine.agents["strategist"].run.return_value = {"vote": "no", "reason": ""}
        engine.agents["evaluator"].run.return_value = {"vote": "yes", "reason": ""}

        motion = self._make_motion()
        # 让 yes 和 no 非常接近
        weights = {"scientist": 0.2, "skeptic": 0.2, "humanist": 0.2,
                   "strategist": 0.2, "evaluator": 0.2}
        # yes: 0.2 + 0.2 + 0.2 = 0.6, no: 0.2 + 0.2 = 0.4, diff = 0.2 > 0.15
        # 调整让 diff < 0.15
        weights = {"scientist": 0.25, "skeptic": 0.25, "humanist": 0.2,
                   "strategist": 0.2, "evaluator": 0.1}
        # yes: 0.25 + 0.25 + 0.1 = 0.6, no: 0.2 + 0.2 = 0.4, diff = 0.2
        # 需要更精确: 让 diff < 0.15
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["skeptic"].run.return_value = {"vote": "no", "reason": ""}
        engine.agents["humanist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["strategist"].run.return_value = {"vote": "no", "reason": ""}
        engine.agents["evaluator"].run.return_value = {"vote": "abstain", "reason": ""}
        weights = {"scientist": 0.3, "skeptic": 0.25, "humanist": 0.2,
                   "strategist": 0.15, "evaluator": 0.1}
        # yes: 0.3 + 0.2 = 0.5, no: 0.25 + 0.15 = 0.4, diff = 0.1 < 0.15

        result = engine.vote_on_motion(motion, weights)
        # 应触发议长裁定
        engine.speaker.rule_deadlock.assert_called_once()
        assert result.result == "amended"
        assert result.speaker_ruling != ""

    def test_agent_vote_failure_becomes_abstain(self, engine):
        """Agent 投票异常 → 记为 abstain"""
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["skeptic"].run.side_effect = Exception("网络错误")
        engine.agents["humanist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["strategist"].run.return_value = {"vote": "yes", "reason": ""}
        engine.agents["evaluator"].run.return_value = {"vote": "yes", "reason": ""}

        motion = self._make_motion()
        weights = {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1,
                   "strategist": 0.1, "evaluator": 0.15}
        result = engine.vote_on_motion(motion, weights)

        assert result.votes["skeptic"] == "abstain"
        assert result.result == "passed"

    def test_minority_opinions_recorded(self, engine):
        """反对票应被记录为少数派意见"""
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": "科学支持"}
        engine.agents["skeptic"].run.return_value = {"vote": "no", "reason": "证据不足"}
        engine.agents["humanist"].run.return_value = {"vote": "yes", "reason": "文化价值"}
        engine.agents["strategist"].run.return_value = {"vote": "yes", "reason": "可行"}
        engine.agents["evaluator"].run.return_value = {"vote": "yes", "reason": "高分"}

        motion = self._make_motion()
        weights = {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1,
                   "strategist": 0.1, "evaluator": 0.15}
        engine.vote_on_motion(motion, weights)

        # skeptic 的反对意见应被记录
        assert len(engine.minority_opinions) >= 1
        assert any(mo.agent == "skeptic" for mo in engine.minority_opinions)

    def test_below_threshold_rejected(self, engine):
        """加权赞成 < 0.65 门槛 → rejected（修复前简单多数逻辑会误判 passed）"""
        engine.agents["scientist"].run.return_value = {"vote": "yes", "reason": "同意"}
        for name in ["skeptic", "humanist", "strategist", "evaluator"]:
            engine.agents[name].run.return_value = {"vote": "no", "reason": "反对"}

        motion = self._make_motion()
        weights = {"scientist": 0.4, "skeptic": 0.25, "humanist": 0.1,
                   "strategist": 0.1, "evaluator": 0.15}
        result = engine.vote_on_motion(motion, weights)

        # yes=0.4 < 0.65，且 |diff|=0.2 > deadlock(0.15) → 不触发议长，判定 rejected
        assert result.result == "rejected"
        assert result.weighted_yes == pytest.approx(0.4)


class TestDebateEngineShouldClose:
    """DebateEngine.should_close 闭幕判定"""

    @pytest.fixture
    def engine(self):
        from src.parliament.debate_engine import DebateEngine
        from src.schemas import Motion, MotionType, VoteResult, DebateRound

        mock_speaker = MagicMock()
        agents = {"scientist": MagicMock(), "humanist": MagicMock()}
        eng = DebateEngine(speaker=mock_speaker, agents=agents, max_rounds=3)
        eng.motions = [
            Motion(motion_id="M001", motion_type=MotionType.FACT_CLAIM,
                   proposer="scientist", content="动议1", confidence=0.8),
            Motion(motion_id="M002", motion_type=MotionType.HYPOTHESIS,
                   proposer="humanist", content="动议2", confidence=0.6),
        ]
        return eng

    def test_max_rounds_reached(self, engine):
        """达到最大轮次 → 应闭幕"""
        from src.schemas import DebateRound
        engine.rounds = [MagicMock() for _ in range(3)]
        assert engine.should_close() is True

    def test_all_motions_voted(self, engine):
        """所有动议已表决 → 应闭幕"""
        from src.schemas import VoteResult
        engine.votes = [
            VoteResult(motion_id="M001", votes={}, weighted_yes=0.8,
                       weighted_no=0.1, result="passed"),
            VoteResult(motion_id="M002", votes={}, weighted_yes=0.2,
                       weighted_no=0.7, result="rejected"),
        ]
        assert engine.should_close() is True

    def test_pending_motions_continue(self, engine):
        """还有未表决动议且未达轮次上限 → 继续"""
        from src.schemas import VoteResult
        engine.votes = [
            VoteResult(motion_id="M001", votes={}, weighted_yes=0.8,
                       weighted_no=0.1, result="passed"),
        ]
        assert engine.should_close() is False

    def test_consecutive_no_improvement(self, engine):
        """连续2轮无提升 → 应闭幕"""
        engine._consecutive_no_improvement = 2
        assert engine.should_close() is True


class TestDebateEngineClose:
    """DebateEngine.close_parliament 闭幕"""

    def test_close_generates_transcript(self):
        """闭幕应生成完整的 DeliberationTranscript"""
        from src.parliament.debate_engine import DebateEngine
        from src.schemas import Motion, MotionType

        mock_speaker = MagicMock()
        mock_speaker.close_parliament.return_value = {
            "summary": "辩论总结",
            "final_recommendation": "建议",
        }
        agents = {"scientist": MagicMock()}
        eng = DebateEngine(speaker=mock_speaker, agents=agents)
        eng.topic = "嫦娥六号"
        eng.started_at = "2024-01-01T00:00:00"
        eng.motions = [
            Motion(motion_id="M001", motion_type=MotionType.FACT_CLAIM,
                   proposer="scientist", content="测试", confidence=0.8),
        ]

        transcript = eng.close_parliament()
        assert transcript.topic == "嫦娥六号"
        assert transcript.total_rounds == 0
        assert transcript.started_at == "2024-01-01T00:00:00"
        assert transcript.completed_at != ""
        mock_speaker.close_parliament.assert_called_once()


class TestWeightTemplates:
    """权重模板测试"""

    def test_all_templates_sum_to_1(self):
        """所有权重模板的权重之和应为 1"""
        from src.parliament.speaker import WEIGHT_TEMPLATES
        for name, weights in WEIGHT_TEMPLATES.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{name} 权重之和为 {total}，应为 1.0"

    def test_all_templates_have_5_agents(self):
        """每个模板应包含 5 个 Agent"""
        from src.parliament.speaker import WEIGHT_TEMPLATES
        expected_agents = {"scientist", "skeptic", "humanist", "strategist", "evaluator"}
        for name, weights in WEIGHT_TEMPLATES.items():
            assert set(weights.keys()) == expected_agents, f"{name} 缺少 Agent"
